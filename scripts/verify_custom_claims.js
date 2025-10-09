#!/usr/bin/env node
/**
 * Verify Custom Claims in Auth Tokens
 *
 * This script signs in as test users and verifies their custom claims
 * are present in the ID token.
 */

const { initializeApp } = require('firebase/app');
const { getAuth, connectAuthEmulator, signInWithEmailAndPassword } = require('firebase/auth');

// Firebase config for emulator
const firebaseConfig = {
  projectId: 'headhunter-ai-0088',
  apiKey: 'fake-api-key',
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// Connect to emulator
connectAuthEmulator(auth, 'http://localhost:9099');

const TEST_USERS = [
  { email: 'admin@ella.com.br', password: 'test-password', expectedRole: 'super_admin' },
  { email: 'manager@ella.com.br', password: 'test-password', expectedRole: 'admin' },
  { email: 'recruiter@ella.com.br', password: 'test-password', expectedRole: 'recruiter' },
];

async function verifyCustomClaims() {
  console.log('\n🔍 Verifying Custom Claims in Auth Tokens\n');
  console.log('='.repeat(80));

  for (const user of TEST_USERS) {
    try {
      console.log(`\n👤 ${user.email}`);

      // Sign in
      const userCredential = await signInWithEmailAndPassword(auth, user.email, user.password);
      console.log(`   ✅ Signed in successfully (UID: ${userCredential.user.uid})`);

      // Get ID token
      const idToken = await userCredential.user.getIdToken(true); // Force refresh
      console.log(`   ✅ Got ID token (length: ${idToken.length})`);

      // Decode token to check claims
      const idTokenResult = await userCredential.user.getIdTokenResult(true);
      console.log(`   ✅ Token result:`, {
        role: idTokenResult.claims.role,
        organization_id: idTokenResult.claims.organization_id,
        email: idTokenResult.claims.email,
      });

      // Verify expected role
      if (idTokenResult.claims.role === user.expectedRole) {
        console.log(`   ✅ Role matches expected: ${user.expectedRole}`);
      } else {
        console.log(`   ❌ Role mismatch! Expected: ${user.expectedRole}, Got: ${idTokenResult.claims.role}`);
      }

      // Verify organization_id
      if (idTokenResult.claims.organization_id) {
        console.log(`   ✅ organization_id present: ${idTokenResult.claims.organization_id}`);
      } else {
        console.log(`   ❌ organization_id missing!`);
      }

    } catch (error) {
      console.log(`   ❌ Error: ${error.message}`);
    }
  }

  console.log('\n' + '='.repeat(80));
  console.log('✅ Custom claims verification complete!\n');
}

verifyCustomClaims()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error('\n❌ Fatal error:', error.message);
    process.exit(1);
  });
