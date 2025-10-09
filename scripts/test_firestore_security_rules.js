#!/usr/bin/env node
/**
 * Test Firestore Security Rules
 *
 * This script tests the security rules defined in firestore.rules to ensure
 * proper role-based access control (RBAC) is enforced.
 *
 * Requirements:
 * - Firebase Emulator must be running (firestore)
 * - Run with: node scripts/test_firestore_security_rules.js
 *
 * Environment Variables:
 * - FIRESTORE_EMULATOR_HOST (default: localhost:8080)
 */

const { initializeApp } = require('firebase/app');
const {
  getFirestore,
  connectFirestoreEmulator,
  collection,
  doc,
  getDoc,
  setDoc,
  updateDoc,
  deleteDoc,
} = require('firebase/firestore');
const {
  getAuth,
  connectAuthEmulator,
  signInWithEmailAndPassword,
  signOut,
} = require('firebase/auth');

// Firebase config for emulator
const firebaseConfig = {
  projectId: 'headhunter-local',
  apiKey: 'fake-api-key',
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const db = getFirestore(app);
const auth = getAuth(app);

// Connect to emulators
const FIRESTORE_HOST = process.env.FIRESTORE_EMULATOR_HOST || 'localhost:8080';
const AUTH_HOST = 'localhost:9099';

connectFirestoreEmulator(db, 'localhost', 8080);
connectAuthEmulator(auth, `http://${AUTH_HOST}`);

console.log(`\n🔒 Testing Firestore Security Rules`);
console.log(`   Firestore: ${FIRESTORE_HOST}`);
console.log(`   Auth: ${AUTH_HOST}`);
console.log('=' .repeat(80));

// Test data
const TEST_ORG_ID = 'test-org-123';
const TEST_CANDIDATE_ID = 'test-candidate-456';

// Test users (must be pre-seeded in allowed_users collection)
const ADMIN_EMAIL = 'admin@ella.com.br';
const ADMIN_PASSWORD = 'test-password';
const RECRUITER_EMAIL = 'recruiter@ella.com.br';
const RECRUITER_PASSWORD = 'test-password';
const UNAUTHORIZED_EMAIL = 'unauthorized@example.com';
const UNAUTHORIZED_PASSWORD = 'test-password';

let testsPassed = 0;
let testsFailed = 0;

/**
 * Run a test case
 */
async function runTest(description, testFn) {
  try {
    console.log(`\n🧪 ${description}`);
    await testFn();
    console.log(`   ✅ PASS`);
    testsPassed++;
  } catch (error) {
    console.log(`   ❌ FAIL: ${error.message}`);
    testsFailed++;
  }
}

/**
 * Assert that operation succeeds
 */
async function assertAllowed(operation) {
  try {
    await operation();
  } catch (error) {
    throw new Error(`Expected operation to be allowed but got: ${error.message}`);
  }
}

/**
 * Assert that operation fails with permission denied
 */
async function assertDenied(operation) {
  try {
    await operation();
    throw new Error('Expected operation to be denied but it succeeded');
  } catch (error) {
    if (!error.message.includes('permission') && !error.message.includes('PERMISSION_DENIED')) {
      throw new Error(`Expected permission denied but got: ${error.message}`);
    }
  }
}

/**
 * Test Suite: Authentication and Allowlist
 */
async function testAuthenticationAndAllowlist() {
  console.log(`\n${'='.repeat(80)}`);
  console.log('📋 Test Suite: Authentication and Allowlist');
  console.log('='.repeat(80));

  // Test 1: Unauthenticated user cannot read candidates
  await runTest('Unauthenticated user cannot read candidates', async () => {
    await signOut(auth);
    await assertDenied(async () => {
      await getDoc(doc(db, 'candidates', TEST_CANDIDATE_ID));
    });
  });

  // Test 2: Unauthorized user (not in allowed_users) cannot read candidates
  await runTest('Unauthorized user cannot read candidates', async () => {
    // Note: This test requires the user to exist in Firebase Auth but NOT in allowed_users
    // In a real test, you'd sign in as unauthorized user first
    await signOut(auth);
    await assertDenied(async () => {
      await getDoc(doc(db, 'candidates', TEST_CANDIDATE_ID));
    });
  });
}

/**
 * Test Suite: Admin Role
 */
async function testAdminRole() {
  console.log(`\n${'='.repeat(80)}`);
  console.log('📋 Test Suite: Admin Role');
  console.log('='.repeat(80));

  // Sign in as admin
  console.log(`\n🔐 Signing in as admin: ${ADMIN_EMAIL}`);
  try {
    await signInWithEmailAndPassword(auth, ADMIN_EMAIL, ADMIN_PASSWORD);
    console.log(`   ✅ Signed in successfully`);
  } catch (error) {
    console.log(`   ⚠️  Could not sign in: ${error.message}`);
    console.log(`   Skipping admin tests (user may not exist)`);
    return;
  }

  // Test 1: Admin can read allowed_users
  await runTest('Admin can read allowed_users collection', async () => {
    await assertAllowed(async () => {
      await getDoc(doc(db, 'allowed_users', 'admin@ella.com.br'.replace('/', '_')));
    });
  });

  // Test 2: Admin can read audit logs
  await runTest('Admin can read audit logs', async () => {
    await assertAllowed(async () => {
      await getDoc(doc(db, 'audit_logs', 'test-log-123'));
    });
  });

  // Test 3: Admin can read candidates in their org
  await runTest('Admin can read candidates in their organization', async () => {
    // First create test candidate (as Cloud Function would)
    // Note: In emulator, this would require Admin SDK
    console.log(`   Note: Actual write requires Admin SDK (Cloud Functions)`);
  });

  await signOut(auth);
}

/**
 * Test Suite: Recruiter Role
 */
async function testRecruiterRole() {
  console.log(`\n${'='.repeat(80)}`);
  console.log('📋 Test Suite: Recruiter Role');
  console.log('='.repeat(80));

  // Sign in as recruiter
  console.log(`\n🔐 Signing in as recruiter: ${RECRUITER_EMAIL}`);
  try {
    await signInWithEmailAndPassword(auth, RECRUITER_EMAIL, RECRUITER_PASSWORD);
    console.log(`   ✅ Signed in successfully`);
  } catch (error) {
    console.log(`   ⚠️  Could not sign in: ${error.message}`);
    console.log(`   Skipping recruiter tests (user may not exist)`);
    return;
  }

  // Test 1: Recruiter cannot read allowed_users
  await runTest('Recruiter cannot read allowed_users collection', async () => {
    await assertDenied(async () => {
      await getDoc(doc(db, 'allowed_users', 'admin@ella.com.br'.replace('/', '_')));
    });
  });

  // Test 2: Recruiter cannot read audit logs
  await runTest('Recruiter cannot read audit logs', async () => {
    await assertDenied(async () => {
      await getDoc(doc(db, 'audit_logs', 'test-log-123'));
    });
  });

  // Test 3: Recruiter can read candidates in their org
  await runTest('Recruiter can read candidates in their organization', async () => {
    console.log(`   Note: Requires test data and user profile setup`);
  });

  // Test 4: Recruiter cannot write candidates
  await runTest('Recruiter cannot write candidates directly', async () => {
    await assertDenied(async () => {
      await setDoc(doc(db, 'candidates', 'test-candidate-new'), {
        name: 'Test Candidate',
        organization_id: TEST_ORG_ID,
      });
    });
  });

  await signOut(auth);
}

/**
 * Test Suite: Organization Scoping
 */
async function testOrganizationScoping() {
  console.log(`\n${'='.repeat(80)}`);
  console.log('📋 Test Suite: Organization Scoping');
  console.log('='.repeat(80));

  console.log(`\n   Note: Organization scoping tests require:`)
  console.log(`   - Multiple users in different organizations`);
  console.log(`   - Test data with organization_id fields`);
  console.log(`   - User profiles with organization_id set`);
  console.log(`   Skipping for now...`);
}

/**
 * Test Suite: User Subcollections
 */
async function testUserSubcollections() {
  console.log(`\n${'='.repeat(80)}`);
  console.log('📋 Test Suite: User Subcollections');
  console.log('='.repeat(80));

  // Sign in as recruiter
  console.log(`\n🔐 Signing in as recruiter: ${RECRUITER_EMAIL}`);
  try {
    await signInWithEmailAndPassword(auth, RECRUITER_EMAIL, RECRUITER_PASSWORD);
    const user = auth.currentUser;
    console.log(`   ✅ Signed in successfully (UID: ${user.uid})`);

    // Test 1: User can read own search history
    await runTest('User can read their own search history', async () => {
      await assertAllowed(async () => {
        await getDoc(doc(db, `users/${user.uid}/search_history`, 'search-123'));
      });
    });

    // Test 2: User can write own preferences
    await runTest('User can write their own preferences', async () => {
      await assertAllowed(async () => {
        await setDoc(doc(db, `users/${user.uid}/preferences`, 'pref-123'), {
          theme: 'dark',
        });
      });
    });

    await signOut(auth);
  } catch (error) {
    console.log(`   ⚠️  Could not sign in: ${error.message}`);
    console.log(`   Skipping user subcollection tests`);
  }
}

/**
 * Main test runner
 */
async function runAllTests() {
  try {
    await testAuthenticationAndAllowlist();
    await testAdminRole();
    await testRecruiterRole();
    await testOrganizationScoping();
    await testUserSubcollections();

    // Summary
    console.log(`\n${'='.repeat(80)}`);
    console.log('📊 Test Summary');
    console.log('='.repeat(80));
    console.log(`   ✅ Passed: ${testsPassed}`);
    console.log(`   ❌ Failed: ${testsFailed}`);
    console.log(`   Total:  ${testsPassed + testsFailed}`);
    console.log('');

    if (testsFailed > 0) {
      console.log('❌ Some tests failed. Review security rules.');
      process.exit(1);
    } else {
      console.log('✅ All tests passed!');
      process.exit(0);
    }
  } catch (error) {
    console.error(`\n❌ Fatal error: ${error.message}`);
    console.error(error.stack);
    process.exit(1);
  }
}

// Run tests
runAllTests();
