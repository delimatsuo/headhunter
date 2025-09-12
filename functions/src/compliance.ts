import { onCall, HttpsError } from "firebase-functions/v2/https";
import * as admin from "firebase-admin";
import { auditLogger, AuditAction } from "./audit-logger";

const firestore = admin.firestore();

export const getAuditReport = onCall({ memory: "512MiB", timeoutSeconds: 120 }, async (request) => {
  if (!request.auth) throw new HttpsError("unauthenticated", "Authentication required");
  const user = await firestore.collection('users').doc(request.auth.uid).get();
  const role = user.data()?.role;
  if (role !== 'admin' && role !== 'super_admin') {
    throw new HttpsError("permission-denied", "Admin role required");
  }

  const { startDate, endDate } = request.data || {};
  const start = startDate ? new Date(startDate) : new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const end = endDate ? new Date(endDate) : new Date();

  const report = await auditLogger.generateReport(start, end);
  return { report, start: start.toISOString(), end: end.toISOString() };
});

export const getSecuritySummary = onCall({ memory: "512MiB", timeoutSeconds: 120 }, async (request) => {
  if (!request.auth) throw new HttpsError("unauthenticated", "Authentication required");
  const user = await firestore.collection('users').doc(request.auth.uid).get();
  const role = user.data()?.role;
  if (role !== 'admin' && role !== 'super_admin') {
    throw new HttpsError("permission-denied", "Admin role required");
  }

  // Basic compliance snapshot
  const [allowedUsersSnap, auditCountSnap] = await Promise.all([
    firestore.collection('allowed_users').get(),
    firestore.collection('audit_logs').limit(1).get(),
  ]);

  return {
    allowed_users_count: allowedUsersSnap.size,
    audit_logging_enabled: !auditCountSnap.empty,
    rules_version: 'v2',
  };
});


