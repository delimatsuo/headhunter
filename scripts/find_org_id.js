
const admin = require('firebase-admin');

if (!admin.apps.length) {
    admin.initializeApp({
        projectId: 'headhunter-ai-0088'
    });
}

const db = admin.firestore();

async function findValidOrgId() {
    console.log('Finding a candidate with valid org_id...');

    const snapshot = await db.collection('candidates')
        .orderBy('org_id') // This requires an index, which we have
        .limit(1)
        .get();

    if (snapshot.empty) {
        console.log('No candidates with org_id found.');
        return;
    }

    const doc = snapshot.docs[0];
    console.log(`Found candidate with org_id: ${doc.data().org_id}`);
}

findValidOrgId().catch(console.error);
