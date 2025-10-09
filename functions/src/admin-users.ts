import { onCall, HttpsError } from "firebase-functions/v2/https";
import * as admin from "firebase-admin";
import {
  AddAllowedUserInput,
  SetAllowedUserRoleInput,
  RemoveAllowedUserInput,
  ListAllowedUsersResponse,
  AllowedUserCreateData,
  AllowedUserUpdateData,
  isValidRole,
  isValidEmail,
  emailToDocId,
  normalizeEmail
} from "./types/allowed-users";

const firestore = admin.firestore();
const auth = admin.auth();

/**
 * Assert that the authenticated user has admin or super_admin role
 * Uses custom claims from Firebase Auth token
 */
async function assertAdmin(uid: string) {
  const userRecord = await auth.getUser(uid);
  const role = userRecord.customClaims?.role;

  if (role !== 'admin' && role !== 'super_admin') {
    throw new HttpsError("permission-denied", "Admin role required");
  }
}

/**
 * Set custom claims on Firebase Auth user
 * This enables role-based security rules without database reads
 */
async function setUserCustomClaims(email: string, role: string, organizationId: string) {
  try {
    const userRecord = await auth.getUserByEmail(email);
    await auth.setCustomUserClaims(userRecord.uid, {
      role,
      organization_id: organizationId,
    });
  } catch (error: any) {
    // User doesn't exist in Firebase Auth yet - that's ok
    // Custom claims will be set when they first sign in
    if (error.code !== 'auth/user-not-found') {
      throw error;
    }
  }
}

/**
 * Clear custom claims from Firebase Auth user
 */
async function clearUserCustomClaims(email: string) {
  try {
    const userRecord = await auth.getUserByEmail(email);
    await auth.setCustomUserClaims(userRecord.uid, {});
  } catch (error: any) {
    // User doesn't exist in Firebase Auth - that's ok
    if (error.code !== 'auth/user-not-found') {
      throw error;
    }
  }
}

export const addAllowedUser = onCall({ memory: "256MiB", timeoutSeconds: 60 }, async (request) => {
  if (!request.auth) throw new HttpsError("unauthenticated", "Authentication required");
  await assertAdmin(request.auth.uid);

  const { email, role, organization_id } = request.data as AddAllowedUserInput || {};
  if (!email || typeof email !== 'string') {
    throw new HttpsError("invalid-argument", "email is required");
  }

  // Validate email format
  if (!isValidEmail(email)) {
    throw new HttpsError("invalid-argument", "Invalid email format");
  }

  // Validate and set role (default to 'recruiter')
  const userRole = role || 'recruiter';
  if (!isValidRole(userRole)) {
    throw new HttpsError("invalid-argument", "Invalid role. Must be 'admin', 'recruiter', or 'super_admin'");
  }

  // Get organization_id from caller's custom claims or use provided value
  // Phase I: Default to 'ella-org' for all Ella employees
  const orgId = organization_id || request.auth.token.organization_id || 'ella-org';

  const normalizedEmail = normalizeEmail(email);
  const docId = emailToDocId(normalizedEmail);
  const existingDoc = await firestore.collection('allowed_users').doc(docId).get();

  if (!existingDoc.exists) {
    // Create new document
    const data: AllowedUserCreateData = {
      email: normalizedEmail,
      role: userRole,
      created_at: admin.firestore.FieldValue.serverTimestamp(),
      created_by: request.auth.uid,
      updated_at: admin.firestore.FieldValue.serverTimestamp(),
    };
    await firestore.collection('allowed_users').doc(docId).set(data);
  } else {
    // Update existing document
    const data: AllowedUserUpdateData = {
      role: userRole,
      updated_at: admin.firestore.FieldValue.serverTimestamp(),
    };
    await firestore.collection('allowed_users').doc(docId).set(data, { merge: true });
  }

  // Set custom claims on Firebase Auth user if they exist
  await setUserCustomClaims(normalizedEmail, userRole, orgId);

  return { success: true };
});

export const removeAllowedUser = onCall({ memory: "256MiB", timeoutSeconds: 60 }, async (request) => {
  if (!request.auth) throw new HttpsError("unauthenticated", "Authentication required");
  await assertAdmin(request.auth.uid);

  const { email } = request.data as RemoveAllowedUserInput || {};
  if (!email || typeof email !== 'string') {
    throw new HttpsError("invalid-argument", "email is required");
  }

  const normalizedEmail = normalizeEmail(email);
  const docId = emailToDocId(normalizedEmail);

  // Check if user exists before deleting
  const existingDoc = await firestore.collection('allowed_users').doc(docId).get();
  if (!existingDoc.exists) {
    throw new HttpsError("not-found", "User not found in allowed_users collection");
  }

  await firestore.collection('allowed_users').doc(docId).delete();

  // Clear custom claims from Firebase Auth user
  await clearUserCustomClaims(normalizedEmail);

  return { success: true };
});

export const listAllowedUsers = onCall({ memory: "256MiB", timeoutSeconds: 60 }, async (request) => {
  if (!request.auth) throw new HttpsError("unauthenticated", "Authentication required");
  await assertAdmin(request.auth.uid);

  const snap = await firestore.collection('allowed_users').orderBy('email').get();
  const users = snap.docs.map(d => ({ id: d.id, ...(d.data() as any) }));
  return { users } as ListAllowedUsersResponse;
});

export const setAllowedUserRole = onCall({ memory: "256MiB", timeoutSeconds: 60 }, async (request) => {
  if (!request.auth) throw new HttpsError("unauthenticated", "Authentication required");
  await assertAdmin(request.auth.uid);

  const { email, role } = request.data as SetAllowedUserRoleInput || {};
  if (!email || typeof email !== 'string') {
    throw new HttpsError("invalid-argument", "email is required");
  }
  if (!role || typeof role !== 'string') {
    throw new HttpsError("invalid-argument", "role is required");
  }

  // Validate role
  if (!isValidRole(role)) {
    throw new HttpsError("invalid-argument", "Invalid role. Must be 'admin', 'recruiter', or 'super_admin'");
  }

  const normalizedEmail = normalizeEmail(email);
  const docId = emailToDocId(normalizedEmail);

  // Check if user exists in allowed_users
  const existingDoc = await firestore.collection('allowed_users').doc(docId).get();
  if (!existingDoc.exists) {
    throw new HttpsError("not-found", "User not found in allowed_users collection");
  }

  const data: AllowedUserUpdateData = {
    role,
    updated_at: admin.firestore.FieldValue.serverTimestamp(),
  };
  await firestore.collection('allowed_users').doc(docId).set(data, { merge: true });

  // Update custom claims on Firebase Auth user
  const orgId = request.auth.token.organization_id || 'ella-org';
  await setUserCustomClaims(normalizedEmail, role, orgId);

  return { success: true };
});

