
const admin = require('firebase-admin');
const { Timestamp } = require('firebase-admin/firestore');

if (!admin.apps.length) {
    admin.initializeApp({
        projectId: 'headhunter-ai-0088'
    });
}

const db = admin.firestore();
const TARGET_ORG_ID = 'org_va2HJw2mOkOwADTbkOJXahABhYw1_1764365192051';

async function migrateCandidates() {
    console.log(`Starting migration to org: ${TARGET_ORG_ID}`);

    const candidatesRef = db.collection('candidates');
    const snapshot = await candidatesRef.get(); // Get all candidates

    if (snapshot.empty) {
        console.log('No candidates found.');
        return;
    }

    console.log(`Found ${snapshot.size} candidates. Starting bulk update...`);

    const bulkWriter = db.bulkWriter();
    let updatedCount = 0;
    let skippedCount = 0;

    snapshot.docs.forEach((doc) => {
        const data = doc.data();

        // Skip if already has the correct org_id
        if (data.org_id === TARGET_ORG_ID) {
            skippedCount++;
            return;
        }

        const updateData = {
            org_id: TARGET_ORG_ID,
        };

        // Add timestamps if missing
        if (!data.updated_at) {
            updateData.updated_at = Timestamp.now();
        }
        if (!data.created_at) {
            updateData.created_at = Timestamp.now();
        }

        // Add status if missing
        if (!data.status) {
            updateData.status = 'new';
        }

        bulkWriter.update(doc.ref, updateData);
        updatedCount++;
    });

    console.log(`Queued ${updatedCount} updates. ${skippedCount} skipped.`);

    await bulkWriter.close();
    console.log('Migration complete!');
}

migrateCandidates().catch(console.error);
