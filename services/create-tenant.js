#!/usr/bin/env node
/**
 * Create tenant-alpha organization in Firestore
 */

const { initializeApp } = require('firebase-admin/app');
const { getFirestore } = require('firebase-admin/firestore');

// Initialize Firebase Admin (uses GOOGLE_APPLICATION_CREDENTIALS or ADC)
initializeApp({
  projectId: 'headhunter-ai-0088'
});

const db = getFirestore();

async function createTenant() {
  const tenantId = 'tenant-alpha';
  const tenantData = {
    id: tenantId,
    name: 'Alpha Test Organization',
    displayName: 'Alpha Test Org',
    status: 'active',
    isActive: true,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    tier: 'standard',
    settings: {
      searchEnabled: true,
      rerankEnabled: true,
      embeddingsEnabled: true
    },
    metadata: {
      environment: 'production',
      createdBy: 'admin-script',
      purpose: 'testing'
    }
  };

  try {
    console.log(`Creating tenant: ${tenantId}...`);

    const docRef = db.collection('organizations').doc(tenantId);
    await docRef.set(tenantData);

    console.log('✅ Tenant created successfully!');
    console.log('\nTenant Details:');
    console.log(`  ID: ${tenantData.id}`);
    console.log(`  Name: ${tenantData.name}`);
    console.log(`  Status: ${tenantData.status}`);
    console.log(`  Active: ${tenantData.isActive}`);

    // Verify by reading it back
    const doc = await docRef.get();
    if (doc.exists) {
      console.log('\n✅ Verification: Tenant exists in Firestore');
      console.log('\nDocument data:');
      console.log(JSON.stringify(doc.data(), null, 2));
    } else {
      console.log('\n❌ Verification failed: Could not read tenant');
    }

    process.exit(0);
  } catch (error) {
    console.error('❌ Error creating tenant:', error);
    process.exit(1);
  }
}

createTenant();
