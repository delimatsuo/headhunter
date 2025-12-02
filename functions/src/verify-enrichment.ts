import * as functions from 'firebase-functions';
import * as admin from 'firebase-admin';

const db = admin.firestore();

export const verifyEnrichment = functions.https.onRequest(async (req, res) => {
    try {
        const docId = req.query.docId as string || '142560148';
        const doc = await db.collection('enriched_profiles').doc(docId).get();
        if (!doc.exists) {
            res.status(404).send('Profile not found');
            return;
        }
        const data = doc.data();
        console.log('Enriched Data:', JSON.stringify(data?.intelligent_analysis, null, 2));
        res.status(200).json(data?.intelligent_analysis);
    } catch (error) {
        console.error(error);
        res.status(500).send(error);
    }
});
