import { onRequest } from "firebase-functions/v2/https";
import * as admin from "firebase-admin";

const db = admin.firestore();

export const migrateCandidates = onRequest({
    timeoutSeconds: 540,
    memory: '1GiB'
}, async (req, res) => {
    try {
        const orgId = 'org_ella_main';
        const candidatesRef = db.collection('candidates');
        const batchSize = 500;

        let totalUpdated = 0;
        let lastDoc = null;
        let processed = 0;

        // Loop until we process all candidates or hit a safety limit
        // Note: For 29k candidates, this might time out. 
        // We'll implement a query that only finds candidates needing update.

        while (true) {
            // Query for candidates that DON'T have the correct org_id
            // Note: Firestore doesn't support != queries easily with pagination in this context without an index
            // So we'll scan, but we'll use a simple query.

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
                if (data.org_id !== orgId) {
                    batch.update(doc.ref, { org_id: orgId });
                    batchCount++;
                }
            });

            if (batchCount > 0) {
                await batch.commit();
                totalUpdated += batchCount;
                console.log(`Updated ${totalUpdated} candidates...`);
            }

            processed += snapshot.size;
            console.log(`Processed ${processed} candidates so far...`);

            lastDoc = snapshot.docs[snapshot.docs.length - 1];

            // Safety break for timeout
            if (processed > 30000) break;
        }

        res.status(200).send(`Migration complete. Total candidates updated: ${totalUpdated}. Scanned: ${processed}`);
    } catch (error) {
        console.error(error);
        res.status(500).send((error as Error).message);
    }
});
