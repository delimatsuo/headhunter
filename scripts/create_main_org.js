const admin = require('firebase-admin');
const serviceAccount = require('../functions/service-account.json');

admin.initializeApp({
    credential: admin.credential.cert(serviceAccount)
});

const db = admin.firestore();

async function createMainOrg() {
    const orgId = 'org_ella_main';
    const orgRef = db.collection('organizations').doc(orgId);

    const doc = await orgRef.get();
    if (doc.exists) {
        console.log('Organization org_ella_main already exists.');
        return;
    }

    await orgRef.set({
        id: orgId,
        name: 'Ella Executive Search',
        owner_id: 'system', // System owned
        members: [], // Will be populated by onboarding
        settings: {
            max_candidates: 100000,
            max_searches_per_month: 10000,
            features: ['candidate_search', 'analytics', 'exports', 'agency_mode']
        },
        created_at: admin.firestore.FieldValue.serverTimestamp(),
        updated_at: admin.firestore.FieldValue.serverTimestamp()
    });

    console.log('Created Organization: Ella Executive Search (org_ella_main)');
}

createMainOrg();
