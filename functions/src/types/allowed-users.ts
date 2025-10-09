/**
 * Firestore schema definitions for the allowed_users collection
 *
 * This collection manages the email allowlist and role-based access control
 * for the Headhunter application. Only users in this collection can authenticate.
 *
 * Document ID: email address (lowercase, with '/' replaced by '_')
 */

import { Timestamp, FieldValue } from "firebase-admin/firestore";

/**
 * Valid user roles in the system
 * - admin: Can manage users, view all data, run maintenance jobs
 * - recruiter: Can search candidates, view details, save/export lists
 * - super_admin: Full system access including user management
 */
export type AllowedUserRole = 'admin' | 'recruiter' | 'super_admin';

/**
 * Firestore document structure for allowed_users collection
 */
export interface AllowedUserDocument {
  /** User's email address (lowercase) */
  email: string;

  /** User's role in the system */
  role: AllowedUserRole;

  /** Timestamp when the user was added to the allowlist */
  created_at: Timestamp;

  /** UID of the admin who added this user */
  created_by: string;

  /** Timestamp when the user record was last modified */
  updated_at: Timestamp;
}

/**
 * Input data for adding a new allowed user
 */
export interface AddAllowedUserInput {
  email: string;
  role?: AllowedUserRole; // Defaults to 'recruiter' if not specified
}

/**
 * Input data for updating user role
 */
export interface SetAllowedUserRoleInput {
  email: string;
  role: AllowedUserRole;
}

/**
 * Input data for removing an allowed user
 */
export interface RemoveAllowedUserInput {
  email: string;
}

/**
 * Response data for listAllowedUsers
 */
export interface ListAllowedUsersResponse {
  users: AllowedUserDocumentWithId[];
}

/**
 * Allowed user document with document ID included
 */
export interface AllowedUserDocumentWithId extends AllowedUserDocument {
  id: string;
}

/**
 * Data structure for creating a new allowed user (with FieldValue for server timestamps)
 */
export interface AllowedUserCreateData {
  email: string;
  role: AllowedUserRole;
  created_at: FieldValue;
  created_by: string;
  updated_at: FieldValue;
}

/**
 * Data structure for updating an existing allowed user
 */
export interface AllowedUserUpdateData {
  email?: string;
  role?: AllowedUserRole;
  updated_at: FieldValue;
}

/**
 * Validates if a string is a valid AllowedUserRole
 */
export function isValidRole(role: string): role is AllowedUserRole {
  return ['admin', 'recruiter', 'super_admin'].includes(role);
}

/**
 * Validates email format
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Normalizes email to lowercase (Firestore document IDs are case-sensitive)
 */
export function normalizeEmail(email: string): string {
  return email.toLowerCase();
}

/**
 * Generates the Firestore document ID from an email address
 * Replaces '/' with '_' to ensure valid document ID
 */
export function emailToDocId(email: string): string {
  return normalizeEmail(email).replaceAll('/', '_');
}
