import { onCall, HttpsError } from "firebase-functions/v2/https";
import * as admin from "firebase-admin";

const firestore = admin.firestore();

async function assertAdmin(uid: string) {
  const userDoc = await firestore.collection('users').doc(uid).get();
  if (!userDoc.exists) throw new HttpsError("permission-denied", "User profile not found");
  const role = userDoc.data()?.role;
  if (role !== 'admin' && role !== 'super_admin') {
    throw new HttpsError("permission-denied", "Admin role required");
  }
}

function keyFromEmail(email: string): string {
  return email.replaceAll('/', '_');
}

export const addAllowedUser = onCall({ memory: "256MiB", timeoutSeconds: 60 }, async (request) => {
  if (!request.auth) throw new HttpsError("unauthenticated", "Authentication required");
  await assertAdmin(request.auth.uid);

  const { email, role } = request.data || {};
  if (!email || typeof email !== 'string') throw new HttpsError("invalid-argument", "email is required");
  const userRole = typeof role === 'string' ? role : 'recruiter';

  const docId = keyFromEmail(email);
  await firestore.collection('allowed_users').doc(docId).set({
    email,
    role: userRole,
    created_at: admin.firestore.FieldValue.serverTimestamp(),
    updated_at: admin.firestore.FieldValue.serverTimestamp(),
  }, { merge: true });

  return { success: true };
});

export const removeAllowedUser = onCall({ memory: "256MiB", timeoutSeconds: 60 }, async (request) => {
  if (!request.auth) throw new HttpsError("unauthenticated", "Authentication required");
  await assertAdmin(request.auth.uid);

  const { email } = request.data || {};
  if (!email || typeof email !== 'string') throw new HttpsError("invalid-argument", "email is required");
  const docId = keyFromEmail(email);
  await firestore.collection('allowed_users').doc(docId).delete();
  return { success: true };
});

export const listAllowedUsers = onCall({ memory: "256MiB", timeoutSeconds: 60 }, async (request) => {
  if (!request.auth) throw new HttpsError("unauthenticated", "Authentication required");
  await assertAdmin(request.auth.uid);

  const snap = await firestore.collection('allowed_users').orderBy('email').get();
  const users = snap.docs.map(d => ({ id: d.id, ...(d.data() as any) }));
  return { users };
});

export const setAllowedUserRole = onCall({ memory: "256MiB", timeoutSeconds: 60 }, async (request) => {
  if (!request.auth) throw new HttpsError("unauthenticated", "Authentication required");
  await assertAdmin(request.auth.uid);

  const { email, role } = request.data || {};
  if (!email || typeof email !== 'string') throw new HttpsError("invalid-argument", "email is required");
  if (!role || typeof role !== 'string') throw new HttpsError("invalid-argument", "role is required");
  const docId = keyFromEmail(email);
  await firestore.collection('allowed_users').doc(docId).set({
    email,
    role,
    updated_at: admin.firestore.FieldValue.serverTimestamp(),
  }, { merge: true });
  return { success: true };
});

