# Authentication System Testing Guide

## Overview

This guide walks through testing the complete authentication and authorization system including:
- Firebase Authentication with Google Sign-In
- Domain restrictions (@ella.com.br)
- `allowed_users` collection allowlist
- Firestore security rules with RBAC

## Prerequisites

### 1. Firebase Project Configuration

**Production Firebase Console:**
- Project: `headhunter-ai-0088`
- Go to: https://console.firebase.google.com/project/headhunter-ai-0088

**Required Configuration:**
1. **Authentication** → **Sign-in method**
   - ✅ Google provider enabled
   - ✅ Authorized domains: `localhost`, `headhunter-ai-0088.firebaseapp.com`, `ella.com.br`

2. **OAuth Consent Screen** (if testing with Google Sign-In)
   - User type: Internal (Ella organization)
   - Application name: Headhunter AI
   - Authorized domains: `ella.com.br`

### 2. Local Development Setup

**Required Services:**
- Node.js 20+
- Python 3.11+
- Firebase CLI installed: `npm install -g firebase-tools`
- Firebase emulator dependencies: `pip install firebase-admin`

## Testing Approach

We'll test in two phases:
1. **Phase 1: Emulator Testing** (local, safe, fast iteration)
2. **Phase 2: Production Testing** (real Firebase project)

## Phase 1: Emulator Testing

### Step 1: Start Firebase Emulator

```bash
# From project root
cd /Volumes/Extreme\ Pro/myprojects/headhunter

# Start emulators (Firestore + Auth)
firebase emulators:start --only firestore,auth

# Expected output:
# ┌─────────────┬────────────────┬─────────────────────────────────┐
# │ Emulator    │ Host:Port      │ View in Emulator Suite          │
# ├─────────────┼────────────────┼─────────────────────────────────┤
# │ Auth        │ localhost:9099 │ http://127.0.0.1:4000/auth      │
# │ Firestore   │ localhost:8080 │ http://127.0.0.1:4000/firestore │
# └─────────────┴────────────────┴─────────────────────────────────┘
```

**Verify Emulator UI:**
- Open: http://localhost:4000
- Should see Auth and Firestore tabs

### Step 2: Initialize Test Users

```bash
# Set emulator host
export FIRESTORE_EMULATOR_HOST=localhost:8080

# Seed admin user
python3 scripts/init_allowed_users.py admin@ella.com.br --role=super_admin

# Seed regular admin
python3 scripts/init_allowed_users.py manager@ella.com.br --role=admin

# Seed recruiter
python3 scripts/init_allowed_users.py recruiter@ella.com.br --role=recruiter

# Verify users were created
python3 scripts/init_allowed_users.py --list
```

**Expected Output:**
```
📋 Allowed Users:
--------------------------------------------------------------------------------
  admin@ella.com.br                        super_admin     created by: system
  manager@ella.com.br                      admin           created by: system
  recruiter@ella.com.br                    recruiter       created by: system
```

### Step 3: Deploy Security Rules to Emulator

Security rules are automatically loaded when emulator starts from `firestore.rules`.

**Verify rules are active:**
```bash
# Check emulator console output for:
# ✔  firestore: Firestore Emulator logging to firestore-debug.log
# i  firestore: Rules updated from firestore.rules
```

### Step 4: Start the UI Development Server

```bash
# In new terminal
cd headhunter-ui

# Install dependencies (if not already done)
npm install

# Set environment variables for emulator
export REACT_APP_USE_EMULATOR=true
export REACT_APP_FIREBASE_PROJECT_ID=headhunter-local

# Start development server
npm start

# Should open: http://localhost:3000
```

### Step 5: Test Authentication Flows

#### Test 5.1: Unauthenticated Access (Should Fail)

**Test:**
1. Open http://localhost:3000
2. Try to access any protected route without signing in

**Expected Result:**
- ❌ Redirected to login page
- ❌ Cannot access candidates, search, or admin pages

#### Test 5.2: Sign In with Allowed User (@ella.com.br)

**Test:**
1. Click "Sign In" or "Sign In with Google"
2. Use email: `admin@ella.com.br`
3. Use any password (emulator doesn't validate passwords)

**Expected Result:**
- ✅ User signs in successfully
- ✅ No error messages
- ✅ Redirected to dashboard/home page
- ✅ User profile created in Firestore

**Verification:**
```bash
# Check Auth emulator UI: http://localhost:4000/auth
# Should see user in "Authentication" tab

# Check Firestore emulator UI: http://localhost:4000/firestore
# Should see documents in:
# - allowed_users/{admin@ella.com.br}
# - users/{uid} (user profile)
```

#### Test 5.3: Sign In with Non-Allowed User (Should Fail)

**Test:**
1. Sign out if signed in
2. Try to sign in with: `unauthorized@ella.com.br`
3. Note: User is NOT in allowed_users collection

**Expected Result:**
- ❌ User is signed in briefly then immediately signed out
- ❌ Error message: "Access denied: Your email address is not authorized"
- ❌ Remains on login page

**Console Log Check:**
```javascript
// Should see in browser console:
// "Error signing in with Google: Error: Access denied..."
```

#### Test 5.4: Sign In with Wrong Domain (Should Fail)

**Test:**
1. Try to sign in with: `user@gmail.com`
2. Note: Domain is not @ella.com.br

**Expected Result:**
- ❌ Error message before authentication attempt
- ❌ "Access denied: Only @ella.com.br email addresses are allowed"
- ❌ User never signs in to Firebase Auth

#### Test 5.5: Registration Flow

**Test:**
1. Click "Sign Up" or "Register"
2. Enter email: `newuser@ella.com.br`
3. Enter password
4. Submit form

**Expected Result:**
- ✅ Firebase Auth account created
- ❌ User immediately signed out
- ❌ Message: "Registration successful! However, your account needs administrator approval"
- ❌ Cannot sign in until added to allowed_users collection

**Verification:**
```bash
# User exists in Firebase Auth but NOT in allowed_users
# Check Auth emulator: http://localhost:4000/auth
# User should be listed

# Check Firestore: http://localhost:4000/firestore
# allowed_users collection should NOT have newuser@ella.com.br
```

### Step 6: Test Security Rules Enforcement

#### Test 6.1: Run Automated Test Suite

```bash
# Make sure emulator is running
# In new terminal:
cd /Volumes/Extreme\ Pro/myprojects/headhunter

# Run security rules tests
node scripts/test_firestore_security_rules.js
```

**Expected Output:**
```
🔒 Testing Firestore Security Rules
   Firestore: localhost:8080
   Auth: localhost:9099
================================================================================

📋 Test Suite: Authentication and Allowlist
================================================================================
🧪 Unauthenticated user cannot read candidates
   ✅ PASS
...

📊 Test Summary
================================================================================
   ✅ Passed: X
   ❌ Failed: 0
   Total:  X

✅ All tests passed!
```

#### Test 6.2: Manual Firestore Access Tests

**Test with Admin User:**
```bash
# In browser console (while signed in as admin@ella.com.br):
import { getFirestore, collection, getDocs } from 'firebase/firestore';
const db = getFirestore();

// Should succeed - admin can read allowed_users
const allowedUsers = await getDocs(collection(db, 'allowed_users'));
console.log('Allowed users:', allowedUsers.docs.length);

// Should succeed - admin can read audit logs
const auditLogs = await getDocs(collection(db, 'audit_logs'));
console.log('Audit logs:', auditLogs.docs.length);
```

**Test with Recruiter User:**
```bash
# Sign in as recruiter@ella.com.br
# In browser console:

// Should FAIL - recruiter cannot read allowed_users
try {
  const allowedUsers = await getDocs(collection(db, 'allowed_users'));
} catch (error) {
  console.log('Expected error:', error.message); // permission denied
}

// Should FAIL - recruiter cannot read audit logs
try {
  const auditLogs = await getDocs(collection(db, 'audit_logs'));
} catch (error) {
  console.log('Expected error:', error.message); // permission denied
}
```

### Step 7: Test Role-Based Access

#### Admin Role Tests

**Sign in as:** `admin@ella.com.br` (role: super_admin)

**Expected Capabilities:**
- ✅ Can access admin pages
- ✅ Can view allowed_users list (when UI is built)
- ✅ Can add/remove users (when UI is built)
- ✅ Can read audit logs
- ✅ Can read candidates in their organization

#### Recruiter Role Tests

**Sign in as:** `recruiter@ella.com.br` (role: recruiter)

**Expected Capabilities:**
- ✅ Can access search/candidates pages
- ✅ Can view candidates in their organization
- ✅ Can save jobs, create search history
- ❌ Cannot access admin pages
- ❌ Cannot view allowed_users list
- ❌ Cannot read audit logs

## Phase 2: Production Testing

### Step 1: Verify Production Firebase Configuration

**Firebase Console Checks:**
1. Navigate to: https://console.firebase.google.com/project/headhunter-ai-0088
2. **Authentication** → **Sign-in method**
   - Verify Google provider is enabled
   - Check authorized domains include your deployment domain
3. **Firestore Database** → **Rules**
   - Verify rules are deployed (should match local firestore.rules)

### Step 2: Deploy Security Rules to Production

```bash
# Review rules before deploying
cat firestore.rules

# Deploy rules only (NOT data)
firebase deploy --only firestore:rules --project headhunter-ai-0088

# Verify deployment
firebase firestore:rules:get --project headhunter-ai-0088
```

### Step 3: Deploy Indexes to Production

```bash
# Deploy Firestore indexes
firebase deploy --only firestore:indexes --project headhunter-ai-0088
```

### Step 4: Initialize Production Users

```bash
# Set production credentials
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"

# Unset emulator host
unset FIRESTORE_EMULATOR_HOST

# Add production admin users (use real email addresses)
python3 scripts/init_allowed_users.py admin@ella.com.br --role=super_admin
python3 scripts/init_allowed_users.py <your-email>@ella.com.br --role=admin

# Verify
python3 scripts/init_allowed_users.py --list
```

### Step 5: Test Production Authentication

**Important:** Use real @ella.com.br email addresses only.

1. Deploy UI to production (or test with production Firebase config locally)
2. Navigate to production URL
3. Sign in with Google using @ella.com.br email
4. Verify:
   - ✅ User can sign in
   - ✅ User profile created in Firestore
   - ✅ No security rule violations
   - ✅ Correct role-based access

## Troubleshooting

### Issue: "Failed to get document because the client is offline"

**Solution:**
- Check emulator is running: `firebase emulators:start`
- Verify `FIRESTORE_EMULATOR_HOST=localhost:8080`
- Check firewall isn't blocking ports 8080, 9099

### Issue: "Missing or insufficient permissions"

**Possible Causes:**
1. User not in allowed_users collection
   - Solution: Add user with `python3 scripts/init_allowed_users.py <email>`
2. User profile missing organization_id
   - Solution: Create user profile with organization_id in Firestore
3. Security rules not loaded
   - Solution: Restart emulator, check firestore.rules syntax

### Issue: "Access denied: Only @ella.com.br email addresses are allowed"

**This is expected behavior for:**
- Users with non-ella.com.br email addresses
- Ensures domain restriction is working correctly

**If you need to test with different domain:**
- Update `ALLOWED_DOMAINS` in `headhunter-ui/src/contexts/AuthContext.tsx`
- Restart development server

### Issue: Google Sign-In popup blocked

**Solution:**
- Allow popups in browser settings
- Or use redirect instead of popup:
  ```javascript
  // In AuthContext.tsx, replace signInWithPopup with:
  import { signInWithRedirect } from 'firebase/auth';
  await signInWithRedirect(auth, googleProvider);
  ```

### Issue: Firebase emulator data persists between runs

**Solution:**
```bash
# Clear emulator data
firebase emulators:start --import=./emulator-data --export-on-exit

# Or start fresh
rm -rf .firebase/emulator-data
firebase emulators:start
```

## Testing Checklist

### Authentication Tests
- [ ] Unauthenticated user redirected to login
- [ ] Allowed user (@ella.com.br) can sign in
- [ ] Non-allowed user (@ella.com.br) denied access
- [ ] Wrong domain user (@gmail.com) denied access
- [ ] Registration creates auth account but requires approval
- [ ] Sign out works correctly

### Security Rules Tests
- [ ] Admin can read allowed_users collection
- [ ] Recruiter cannot read allowed_users collection
- [ ] Admin can read audit_logs
- [ ] Recruiter cannot read audit_logs
- [ ] Users can only access data in their organization
- [ ] Users can read/write their own subcollections
- [ ] Direct writes to data collections are denied

### Role-Based Access Tests
- [ ] super_admin has full access
- [ ] admin can manage users and read all org data
- [ ] recruiter can search candidates but not manage users
- [ ] Unauthenticated users have no access

### Integration Tests
- [ ] User profile created after first sign-in
- [ ] Organization membership enforced
- [ ] Real-time updates work correctly
- [ ] Cloud Functions can write data (bypassing rules)

## Success Criteria

✅ Authentication system working end-to-end
✅ Domain restrictions enforced (@ella.com.br only)
✅ Allowlist system functional (allowed_users collection)
✅ Security rules prevent unauthorized access
✅ Role-based access control working (admin/recruiter)
✅ Organization scoping enforced
✅ No security vulnerabilities identified

---

**Next Steps After Testing:**
- Task 72.4: Build admin user management UI
- Deploy security rules to production
- Set up monitoring for authentication failures
- Create runbook for user management operations
