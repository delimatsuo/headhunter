import * as functions from 'firebase-functions';
import * as admin from 'firebase-admin';

const db = admin.firestore();

export const initAgencyModel = functions.https.onRequest(async (req, res) => {
    try {
        const orgId = 'org_ella_main';
        const orgRef = db.collection('organizations').doc(orgId);

        const doc = await orgRef.get();
        if (doc.exists) {
            res.status(200).send('Organization org_ella_main already exists.');
            return;
        }

        await orgRef.set({
            id: orgId,
            name: 'Ella Executive Search',
            owner_id: 'system',
            members: [],
            settings: {
                max_candidates: 100000,
                max_searches_per_month: 10000,
                features: ['candidate_search', 'analytics', 'exports', 'agency_mode']
            },
            created_at: admin.firestore.FieldValue.serverTimestamp(),
            updated_at: admin.firestore.FieldValue.serverTimestamp()
        });

        res.status(200).send('Created Organization: Ella Executive Search (org_ella_main)');
    } catch (error) {
        console.error(error);
        res.status(500).send((error as any).message);
    }
});
