# Allowed Users Collection Schema

## Task 72.2: Create allowed_users Firestore Collection with Role Management Schema

### Overview

The `allowed_users` collection manages the email allowlist and role-based access control (RBAC) for the Headhunter application. Only users present in this collection can authenticate and access the system.

**PRD Reference:** Lines 131-132, 147-150, 258

### Collection Structure

**Collection Name:** `allowed_users`
**Document ID Format:** Email address (lowercase, with '/' replaced by '_')

### Schema Definition

```typescript
interface AllowedUserDocument {
  email: string;           // User's email address (lowercase, normalized)
  role: AllowedUserRole;   // User's role: 'admin' | 'recruiter' | 'super_admin'
  created_at: Timestamp;   // When the user was added to the allowlist
  created_by: string;      // UID of the admin who added this user
  updated_at: Timestamp;   // Last modification timestamp
}
```

### Roles

| Role | Permissions |
|------|------------|
| `recruiter` | Search candidates, view details, save/export lists (default role) |
| `admin` | Manage users, view all data, run maintenance jobs |
| `super_admin` | Full system access including user management and system configuration |

### Cloud Functions

All Cloud Functions are authenticated and require admin role. Located in `functions/src/admin-users.ts`.

#### addAllowedUser
Creates or updates a user in the allowed_users collection.

**Parameters:**
```typescript
{
  email: string;      // Required
  role?: string;      // Optional, defaults to 'recruiter'
}
```

**Validation:**
- Email format validation (regex)
- Role validation (must be 'admin', 'recruiter', or 'super_admin')
- Caller must have admin role

**Behavior:**
- If user exists: Updates role and updated_at
- If user is new: Sets email, role, created_at, created_by, updated_at
- Email is normalized to lowercase

**Example:**
```typescript
const result = await addAllowedUser({
  data: {
    email: 'recruiter@ella.com.br',
    role: 'recruiter'
  }
});
```

#### removeAllowedUser
Removes a user from the allowed_users collection.

**Parameters:**
```typescript
{
  email: string;      // Required
}
```

**Validation:**
- Email is required
- User must exist in collection
- Caller must have admin role

**Example:**
```typescript
const result = await removeAllowedUser({
  data: { email: 'user@ella.com.br' }
});
```

#### listAllowedUsers
Returns all users in the allowed_users collection.

**Parameters:** None

**Returns:**
```typescript
{
  users: Array<{
    id: string;
    email: string;
    role: string;
    created_at: Timestamp;
    created_by: string;
    updated_at: Timestamp;
  }>
}
```

**Example:**
```typescript
const result = await listAllowedUsers();
console.log(result.users);
```

#### setAllowedUserRole
Updates the role of an existing user.

**Parameters:**
```typescript
{
  email: string;      // Required
  role: string;       // Required ('admin' | 'recruiter' | 'super_admin')
}
```

**Validation:**
- Email and role are required
- User must exist in collection
- Role must be valid
- Caller must have admin role

**Example:**
```typescript
const result = await setAllowedUserRole({
  data: {
    email: 'user@ella.com.br',
    role: 'admin'
  }
});
```

### Firestore Indexes

Two composite indexes are configured for efficient queries:

**Index 1: Role + Email**
```json
{
  "collectionGroup": "allowed_users",
  "fields": [
    { "fieldPath": "role", "order": "ASCENDING" },
    { "fieldPath": "email", "order": "ASCENDING" }
  ]
}
```

**Index 2: Role + Created Date**
```json
{
  "collectionGroup": "allowed_users",
  "fields": [
    { "fieldPath": "role", "order": "ASCENDING" },
    { "fieldPath": "created_at", "order": "DESCENDING" }
  ]
}
```

### Security Rules

Located in `firestore.rules` (lines 102-106):

```javascript
match /allowed_users/{userKey} {
  allow read: if isAdmin();
  allow write: if isSuperAdmin() || isAdmin();
}
```

**Access Control:**
- **Read:** Admin or super_admin only
- **Write:** Admin or super_admin only
- **Note:** Cloud Functions bypass security rules via Admin SDK

### TypeScript Types

Comprehensive type definitions available in `functions/src/types/allowed-users.ts`:

- `AllowedUserRole` - Valid role enum type
- `AllowedUserDocument` - Firestore document structure
- `AddAllowedUserInput` - Input for addAllowedUser
- `SetAllowedUserRoleInput` - Input for setAllowedUserRole
- `RemoveAllowedUserInput` - Input for removeAllowedUser
- `ListAllowedUsersResponse` - Response from listAllowedUsers
- `AllowedUserCreateData` - Data for new documents
- `AllowedUserUpdateData` - Data for updates

**Helper Functions:**
- `isValidRole(role: string): boolean` - Validates role
- `isValidEmail(email: string): boolean` - Validates email format
- `normalizeEmail(email: string): string` - Normalizes to lowercase
- `emailToDocId(email: string): string` - Generates document ID

### Initialization Script

**Script:** `scripts/init_allowed_users.py`

Idempotent script for seeding initial admin users. Works with both Firestore emulator and production.

**Usage:**

```bash
# Using environment variable
export ADMIN_EMAILS="admin@ella.com.br,manager@ella.com.br"
python3 scripts/init_allowed_users.py

# Using command-line arguments
python3 scripts/init_allowed_users.py admin@ella.com.br manager@ella.com.br

# Specify role
python3 scripts/init_allowed_users.py --role=super_admin admin@ella.com.br

# List existing users
python3 scripts/init_allowed_users.py --list

# With custom creator
python3 scripts/init_allowed_users.py --created-by=admin-uid admin@ella.com.br
```

**Environment Variables:**
- `ADMIN_EMAILS` - Comma-separated list of admin emails
- `FIRESTORE_EMULATOR_HOST` - For local development
- `GOOGLE_APPLICATION_CREDENTIALS` - Service account key for production

### Integration with Authentication

The `allowed_users` collection is checked by the authentication flow implemented in `headhunter-ui/src/contexts/AuthContext.tsx`:

```typescript
const isUserAllowed = async (email: string): Promise<boolean> => {
  try {
    const userDoc = await getDoc(doc(db, 'allowed_users', email.toLowerCase()));
    return userDoc.exists();
  } catch (error) {
    console.error('Error checking allowed users:', error);
    return false;
  }
};
```

**Authentication Flow:**
1. User signs in with Google or email/password
2. Domain validation checks email ends with `@ella.com.br`
3. Allowlist check queries `allowed_users` collection
4. If user not found: Sign out immediately with error message
5. If user found: Complete authentication and onboarding

### Bootstrap Process

**Initial Setup:**

1. **Deploy Cloud Functions:**
   ```bash
   cd functions
   npm install
   npm run deploy
   ```

2. **Deploy Firestore indexes:**
   ```bash
   firebase deploy --only firestore:indexes
   ```

3. **Deploy Firestore rules:**
   ```bash
   firebase deploy --only firestore:rules
   ```

4. **Seed initial admin user(s):**
   ```bash
   # For production
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"
   python3 scripts/init_allowed_users.py admin@ella.com.br --role=super_admin

   # For local development
   export FIRESTORE_EMULATOR_HOST=localhost:8080
   python3 scripts/init_allowed_users.py admin@ella.com.br --role=super_admin
   ```

5. **Verify setup:**
   ```bash
   python3 scripts/init_allowed_users.py --list
   ```

### Testing Checklist

- [x] Cloud Functions deployed and callable
- [x] TypeScript types defined and imported
- [x] Firestore indexes deployed
- [x] Firestore security rules deployed
- [x] Initialization script executable and tested
- [ ] Integration test: Add user via Cloud Function
- [ ] Integration test: Remove user via Cloud Function
- [ ] Integration test: Update user role via Cloud Function
- [ ] Integration test: List users via Cloud Function
- [ ] Integration test: Authentication flow with allowed user
- [ ] Integration test: Authentication flow with non-allowed user
- [ ] Security test: Non-admin cannot call Cloud Functions
- [ ] Security test: Non-admin cannot read/write allowed_users collection

### Next Steps

**Task 72.3:** Implement comprehensive Firestore security rules for RBAC
**Task 72.4:** Build admin user management UI with Cloud Functions integration

### Files Modified

1. `functions/src/admin-users.ts` - Enhanced with validation and types
2. `functions/src/types/allowed-users.ts` - Created type definitions
3. `firestore.indexes.json` - Added indexes for allowed_users collection
4. `scripts/init_allowed_users.py` - Created initialization script
5. `docs/allowed-users-collection.md` - Created this documentation

### Security Notes

- Document IDs are email-based for fast lookups (no need to scan collection)
- Email addresses are normalized to lowercase for consistency
- Only admin roles can manage allowed_users collection
- Cloud Functions enforce role-based access control
- Client-side checks in AuthContext provide immediate feedback
- Server-side security rules enforce actual access control
- Users are immediately signed out if not in allowlist

### Data Privacy

- Email addresses are stored in plaintext (necessary for authentication)
- No other PII is stored in this collection
- Audit trail maintained via `created_at`, `created_by`, `updated_at`
- Collection is only readable by admin users

---

**Date:** 2025-10-09
**Task:** 72.2 - Create allowed_users Firestore Collection with Role Management Schema
**Status:** ✅ COMPLETED
