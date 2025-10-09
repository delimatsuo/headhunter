#!/usr/bin/env node
/**
 * Set Custom Claims for Test Users
 *
 * This script uses Firebase Admin SDK to set custom claims on test users
 * in the Auth emulator. Custom claims include role and organization_id.
 *
 * Requirements:
 * - Firebase Emulator must be running (auth, firestore)
 * - Run BEFORE running test_firestore_security_rules.js
 *
 * Usage:
 * node scripts/set_test_user_custom_claims.js
 */

const admin = require('firebase-admin');

// Initialize Admin SDK for emulator
process.env.FIRESTORE_EMULATOR_HOST = 'localhost:8081';
process.env.FIREBASE_AUTH_EMULATOR_HOST = 'localhost:9099';

admin.initializeApp({
  projectId: 'headhunter-ai-0088',
});

const auth = admin.auth();
const db = admin.firestore();

const TEST_ORG_ID = 'test-org-123';

// Test users configuration
const TEST_USERS = [
  {
    email: 'admin@ella.com.br',
    password: 'test-password',
    customClaims: {
      role: 'super_admin',
      organization_id: TEST_ORG_ID,
    },
  },
  {
    email: 'manager@ella.com.br',
    password: 'test-password',
    customClaims: {
      role: 'admin',
      organization_id: TEST_ORG_ID,
    },
  },
  {
    email: 'recruiter@ella.com.br',
    password: 'test-password',
    customClaims: {
      role: 'recruiter',
      organization_id: TEST_ORG_ID,
    },
  },
];

async function setupTestUsers() {
  console.log('\n🔧 Setting up test users with custom claims\n');
  console.log('=' .repeat(80));

  for (const userData of TEST_USERS) {
    try {
      console.log(`\n👤 Processing: ${userData.email}`);

      // Create or get user
      let user;
      try {
        user = await auth.createUser({
          email: userData.email,
          password: userData.password,
          emailVerified: true,
        });
        console.log(`   ✅ Created user in Auth emulator (UID: ${user.uid})`);
      } catch (error) {
        if (error.code === 'auth/email-already-exists') {
          user = await auth.getUserByEmail(userData.email);
          console.log(`   ℹ️  User already exists (UID: ${user.uid})`);
        } else {
          throw error;
        }
      }

      // Set custom claims
      await auth.setCustomUserClaims(user.uid, userData.customClaims);
      console.log(`   ✅ Set custom claims:`, userData.customClaims);

      // Create user profile in Firestore
      await db.collection('users').doc(user.uid).set({
        email: userData.email,
        organization_id: userData.customClaims.organization_id,
        created_at: admin.firestore.FieldValue.serverTimestamp(),
      });
      console.log(`   ✅ Created user profile in Firestore`);

      // Verify custom claims
      const userRecord = await auth.getUser(user.uid);
      console.log(`   ✅ Verified custom claims:`, userRecord.customClaims);

    } catch (error) {
      console.error(`   ❌ Error processing ${userData.email}:`, error.message);
      process.exit(1);
    }
  }

  console.log('\n' + '='.repeat(80));
  console.log('✅ All test users configured successfully!');
  console.log('\n📋 Test users ready:');
  console.log(`   - admin@ella.com.br (super_admin)`);
  console.log(`   - manager@ella.com.br (admin)`);
  console.log(`   - recruiter@ella.com.br (recruiter)`);
  console.log('\n🧪 You can now run: node scripts/test_firestore_security_rules.js\n');
}

setupTestUsers()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error('\n❌ Fatal error:', error.message);
    console.error(error.stack);
    process.exit(1);
  });
