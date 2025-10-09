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

async function assertAdmin(uid: string) {
  const userDoc = await firestore.collection('users').doc(uid).get();
  if (!userDoc.exists) throw new HttpsError("permission-denied", "User profile not found");
  const role = userDoc.data()?.role;
  if (role !== 'admin' && role !== 'super_admin') {
    throw new HttpsError("permission-denied", "Admin role required");
  }
}

export const addAllowedUser = onCall({ memory: "256MiB", timeoutSeconds: 60 }, async (request) => {
  if (!request.auth) throw new HttpsError("unauthenticated", "Authentication required");
  await assertAdmin(request.auth.uid);

  const { email, role } = request.data as AddAllowedUserInput || {};
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
  return { success: true };
});

