# Firestore Security Rules Documentation

## Task 72.3: Implement Firestore Security Rules for Role-Based Access Control

### Overview

Comprehensive Firestore security rules enforcing role-based access control (RBAC) integrated with the `allowed_users` collection for authentication and authorization.

**PRD Reference:** Lines 255-259

### Architecture

The security model uses **dual-collection RBAC**:

1. **`allowed_users` collection**: Source of truth for authentication and roles
2. **`users` collection**: User profiles with organization membership

**Authentication Flow:**
```
User Request
  ↓
Check isAuthenticated() - Firebase Auth token present?
  ↓
Check isAllowedUser() - Email exists in allowed_users collection?
  ↓
Check getUserRole() - Get role from allowed_users
  ↓
Check isOrgMember() - Verify organization membership from users collection
  ↓
Allow/Deny access
```

### Role Hierarchy

| Role | Level | Permissions |
|------|-------|------------|
| `super_admin` | 3 | Full system access, user management, all organization data |
| `admin` | 2 | User management, organization management, all org data |
| `recruiter` | 1 | Search candidates, view profiles, save jobs (within org) |

### Helper Functions

#### Authentication Helpers

**`isAuthenticated()`**
```javascript
return request.auth != null;
```
Checks if user has valid Firebase Authentication token.

**`isAllowedUser()`**
```javascript
return isAuthenticated() &&
       exists(/databases/$(database)/documents/allowed_users/$(emailToDocId(getUserEmail())));
```
**Primary authentication check** - verifies user email exists in `allowed_users` collection.

**`getUserEmail()`**
```javascript
return request.auth.token.email;
```
Extracts email from authentication token.

**`emailToDocId(email)`**
```javascript
return email.lower().replace('/', '_');
```
Converts email to Firestore document ID format (matches TypeScript helper).

#### Role Checking Helpers

**`getUserRole()`**
```javascript
return getAllowedUserData().data.role;
```
Gets user's role from `allowed_users` collection.

**`isAdmin()`**
```javascript
return isAllowedUser() &&
       getUserRole() in ['admin', 'super_admin'];
```
Checks if user has admin or super_admin role.

**`isSuperAdmin()`**
```javascript
return isAllowedUser() &&
       getUserRole() == 'super_admin';
```
Checks if user has super_admin role (highest privilege).

**`isRecruiter()`**
```javascript
return isAllowedUser() &&
       getUserRole() in ['recruiter', 'admin', 'super_admin'];
```
Checks if user has recruiter role or higher.

#### Organization Helpers

**`isOrgMember(orgId)`**
```javascript
return isAllowedUser() &&
       exists(/databases/$(database)/documents/users/$(request.auth.uid)) &&
       getUserData().data.organization_id == orgId;
```
Checks if user is a member of a specific organization.

**`isOwner(userId)`**
```javascript
return isAuthenticated() && request.auth.uid == userId;
```
Checks if authenticated user owns the resource.

### Collection Rules

#### `allowed_users` Collection

**Purpose:** Authentication allowlist and role management

**Read Access:**
- Admins and super_admins only

**Write Access:**
- Admins and super_admins only
- Cloud Functions bypass via Admin SDK

**Security Notes:**
- Users cannot read or modify their own roles from client
- All CRUD operations handled by Cloud Functions
- Direct client access restricted to prevent privilege escalation

```javascript
match /allowed_users/{userKey} {
  allow read: if isAdmin();
  allow write: if isAdmin();
}
```

#### `users` Collection

**Purpose:** User profiles with organization membership

**Read Access:**
- Users can read their own profile
- Users can read profiles of other users in their organization

**Write Access:**
- Create: Users can create their own profile (must be in allowed_users)
- Update: Users can update their own profile, admins can update org members
- Delete: Super admins only

**Security Notes:**
- Role information comes from `allowed_users`, not `users`
- Organization membership enforced for cross-user reads

```javascript
match /users/{userId} {
  allow read: if isOwner(userId) ||
                 (isAllowedUser() && isOrgMember(resource.data.organization_id));
  allow create: if isOwner(userId) && isAllowedUser();
  allow update: if isOwner(userId) ||
                   (isAdmin() && isOrgMember(resource.data.organization_id));
  allow delete: if isSuperAdmin();
}
```

#### `candidates` Collection

**Purpose:** Candidate profiles (organization-scoped)

**Read Access:**
- Allowed users (recruiters+) can read candidates in their organization

**Write Access:**
- None (Cloud Functions only)

```javascript
match /candidates/{candidateId} {
  allow read: if isAllowedUser() &&
                 isOrgMember(resource.data.organization_id);
  allow write: if false;
}
```

#### `enriched_profiles` Collection

**Purpose:** AI-enriched candidate data (organization-scoped)

**Read Access:**
- Allowed users can read enriched profiles in their organization

**Write Access:**
- None (Cloud Functions/processors only)

```javascript
match /enriched_profiles/{profileId} {
  allow read: if isAllowedUser() &&
                 isOrgMember(resource.data.organization_id);
  allow write: if false;
}
```

#### `jobs` Collection

**Purpose:** Job descriptions and requirements (organization-scoped)

**Read Access:**
- Allowed users can read jobs in their organization

**Write Access:**
- None (Cloud Functions only)

```javascript
match /jobs/{jobId} {
  allow read: if isAllowedUser() &&
                 isOrgMember(resource.data.organization_id);
  allow write: if false;
}
```

#### `candidate_embeddings` Collection

**Purpose:** Vector embeddings for semantic search

**Read Access:**
- Admins only (for debugging/monitoring)

**Write Access:**
- None (backend pipelines only)

```javascript
match /candidate_embeddings/{embeddingId} {
  allow read: if isAdmin();
  allow write: if false;
}
```

#### `audit_logs` Collection

**Purpose:** System audit trail (sensitive)

**Read Access:**
- Admins only

**Write Access:**
- None (Cloud Functions only)

```javascript
match /audit_logs/{logId} {
  allow read: if isAdmin();
  allow write: if false;
}
```

#### User Subcollections

**Purpose:** Private user data

**Collections:**
- `users/{userId}/search_history` - Immutable search history
- `users/{userId}/preferences` - User settings
- `users/{userId}/saved_jobs` - Bookmarked jobs
- `users/{userId}/notifications` - User notifications

**Access:**
- Owner only (must be in allowed_users)

```javascript
match /users/{userId}/search_history/{searchId} {
  allow read: if isOwner(userId) && isAllowedUser();
  allow create: if isOwner(userId) && isAllowedUser();
  allow update: if false; // Immutable
  allow delete: if isOwner(userId) && isAllowedUser();
}
```

### Testing

#### Prerequisites

1. Firebase Emulator running:
   ```bash
   firebase emulators:start
   ```

2. Seed test users:
   ```bash
   export FIRESTORE_EMULATOR_HOST=localhost:8080
   python3 scripts/init_allowed_users.py admin@ella.com.br --role=admin
   python3 scripts/init_allowed_users.py recruiter@ella.com.br --role=recruiter
   ```

3. Install dependencies:
   ```bash
   npm install firebase firebase-admin
   ```

#### Running Tests

```bash
# Run security rules tests
node scripts/test_firestore_security_rules.js
```

#### Manual Testing

**Test 1: Unauthenticated Access**
```bash
# Should fail - no authentication
curl http://localhost:8080/v1/projects/headhunter-local/databases/(default)/documents/candidates/test
```

**Test 2: Admin Access to allowed_users**
```javascript
// Sign in as admin
const auth = getAuth();
await signInWithEmailAndPassword(auth, 'admin@ella.com.br', 'password');

// Should succeed
const allowedUsers = await getDoc(doc(db, 'allowed_users', 'admin@ella.com.br'));
```

**Test 3: Recruiter Access to allowed_users**
```javascript
// Sign in as recruiter
await signInWithEmailAndPassword(auth, 'recruiter@ella.com.br', 'password');

// Should fail - permission denied
const allowedUsers = await getDoc(doc(db, 'allowed_users', 'admin@ella.com.br'));
```

**Test 4: Organization Scoping**
```javascript
// User in org-alpha tries to read candidate in org-beta
// Should fail - different organization
const candidate = await getDoc(doc(db, 'candidates', 'candidate-from-org-beta'));
```

### Deployment

#### Deploy to Emulator

```bash
# Rules are automatically loaded when emulator starts
firebase emulators:start --only firestore
```

#### Deploy to Production

```bash
# Deploy security rules
firebase deploy --only firestore:rules

# Verify deployment
firebase firestore:rules:get
```

### Security Best Practices

1. **Defense in Depth**
   - Client-side validation in AuthContext.tsx (UX)
   - Security rules (enforcement layer)
   - Cloud Functions use Admin SDK (bypasses rules)

2. **Principle of Least Privilege**
   - Users start as 'recruiter' (minimum access)
   - Admins explicitly granted via `allowed_users`
   - Organization scoping enforced on all data

3. **Audit Trail**
   - All sensitive operations logged to `audit_logs`
   - Admin-only read access to audit logs
   - Immutable logs (write-only from Cloud Functions)

4. **Fail Secure**
   - Default deny rule catches undefined collections
   - All new collections denied by default
   - Explicit allow rules required

5. **Performance Optimization**
   - `isAllowedUser()` checks existence (fast)
   - Role lookups cached by Firestore
   - Organization checks use indexed fields

### Common Pitfalls

**❌ Don't: Check role in `users` collection**
```javascript
// WRONG - users collection doesn't have authoritative roles
function isAdmin() {
  return getUserData().data.role == 'admin';
}
```

**✅ Do: Check role in `allowed_users` collection**
```javascript
// CORRECT - allowed_users is source of truth
function isAdmin() {
  return isAllowedUser() &&
         getUserRole() in ['admin', 'super_admin'];
}
```

**❌ Don't: Allow direct writes to data collections**
```javascript
// WRONG - bypasses business logic and audit trails
match /candidates/{candidateId} {
  allow write: if isAdmin();
}
```

**✅ Do: Use Cloud Functions for writes**
```javascript
// CORRECT - Cloud Functions enforce business logic
match /candidates/{candidateId} {
  allow write: if false; // Only Cloud Functions
}
```

**❌ Don't: Forget to check `isAllowedUser()`**
```javascript
// WRONG - authenticated ≠ authorized
function isAdmin() {
  return isAuthenticated() && getUserRole() == 'admin';
}
```

**✅ Do: Always check allowlist**
```javascript
// CORRECT - must be in allowed_users
function isAdmin() {
  return isAllowedUser() && getUserRole() in ['admin', 'super_admin'];
}
```

### Troubleshooting

**Issue: "Missing or insufficient permissions"**
- Verify user exists in `allowed_users` collection
- Check user has correct role for operation
- Verify organization membership if accessing org-scoped data
- Confirm `users` profile exists with `organization_id`

**Issue: Admin cannot read `allowed_users`**
- Verify role in `allowed_users` is 'admin' or 'super_admin'
- Check that user's profile in `users` collection exists
- Ensure Firebase Auth token is valid and not expired

**Issue: User cannot read candidates in their org**
- Verify user profile has correct `organization_id`
- Check candidate document has `organization_id` field
- Confirm user is in `allowed_users` collection
- Verify role is 'recruiter', 'admin', or 'super_admin'

**Issue: Cloud Functions getting permission denied**
- Ensure using Admin SDK (bypasses security rules)
- Verify service account has correct permissions
- Check Admin SDK initialized with credentials

### Files Modified

1. `firestore.rules` - Complete rewrite with comprehensive RBAC
2. `scripts/test_firestore_security_rules.js` - Security rules test suite
3. `docs/firestore-security-rules.md` - This documentation

### Next Steps

**Task 72.4:** Build admin user management UI with Cloud Functions integration

### References

- [Firestore Security Rules Documentation](https://firebase.google.com/docs/firestore/security/get-started)
- [Security Rules Best Practices](https://firebase.google.com/docs/rules/basics)
- Task 72.1: Authentication with domain restrictions
- Task 72.2: `allowed_users` collection schema
- `docs/allowed-users-collection.md` - Collection documentation
- `docs/firebase-auth-setup.md` - Authentication setup

---

**Date:** 2025-10-09
**Task:** 72.3 - Implement Firestore Security Rules for Role-Based Access Control
**Status:** ✅ COMPLETED
