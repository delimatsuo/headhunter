const admin = require('firebase-admin');
const serviceAccount = require('../functions/service-account.json');

admin.initializeApp({
    credential: admin.credential.cert(serviceAccount)
});

const db = admin.firestore();

async function migrateCandidates() {
    const orgId = 'org_ella_main';
    const candidatesRef = db.collection('candidates');
    const batchSize = 500;

    let totalUpdated = 0;
    let lastDoc = null;

    while (true) {
        let query = candidatesRef.limit(batchSize);
        if (lastDoc) {
            query = query.startAfter(lastDoc);
        }

        const snapshot = await query.get();
        if (snapshot.empty) {
            break;
        }

        const batch = db.batch();
        let batchCount = 0;

        snapshot.forEach(doc => {
            const data = doc.data();
            // Only update if org_id is missing or different
            if (data.org_id !== orgId) {
                batch.update(doc.ref, { org_id: orgId });
                batchCount++;
            }
        });

        if (batchCount > 0) {
            await batch.commit();
            totalUpdated += batchCount;
            console.log(`Updated ${totalUpdated} candidates...`);
        } else {
            console.log(`Scanned ${snapshot.size} candidates, no updates needed in this batch.`);
        }

        lastDoc = snapshot.docs[snapshot.docs.length - 1];
    }

    console.log(`Migration complete. Total candidates updated: ${totalUpdated}`);
}

migrateCandidates();
