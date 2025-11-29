
const admin = require('firebase-admin');

// Initialize Firebase Admin
if (!admin.apps.length) {
    admin.initializeApp({
        projectId: 'headhunter-ai-0088'
    });
}

const db = admin.firestore();

async function inspectCandidates() {
    console.log('Inspecting candidates collection...');

    // Get total count
    const countSnapshot = await db.collection('candidates').count().get();
    console.log(`Total documents in 'candidates' collection: ${countSnapshot.data().count}`);

    // Get a sample of documents (first 5)
    const snapshot = await db.collection('candidates').limit(5).get();

    if (snapshot.empty) {
        console.log('No documents found in candidates collection.');
        return;
    }

    console.log('\nSample documents:');
    snapshot.forEach(doc => {
        const data = doc.data();
        console.log(`ID: ${doc.id}`);
        console.log(`- org_id: ${data.org_id}`);
        console.log(`- updated_at: ${data.updated_at ? data.updated_at.toDate() : 'undefined'}`);
        console.log(`- name: ${data.personal?.name || data.name || 'Unknown'}`);
        console.log('---');
    });

    // Check for documents without org_id
    const noOrgSnapshot = await db.collection('candidates')
        .where('org_id', '==', null) // This might not work if field is missing, but worth a try
        .limit(5)
        .get();

    console.log(`\nDocuments explicitly with null org_id: ${noOrgSnapshot.size}`);

    // Check for documents where org_id is missing (requires client-side filter if not indexed)
    // We'll just check the sample we got earlier.
}

inspectCandidates().catch(console.error);
