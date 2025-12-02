import * as functions from 'firebase-functions';
import * as admin from 'firebase-admin';

const db = admin.firestore();

export const resetCandidate = functions.https.onRequest(async (req, res) => {
    try {
        const snapshot = await db.collection('candidates').limit(1).get();
        if (snapshot.empty) {
            res.status(404).send('No candidates found');
            return;
        }
        const doc = snapshot.docs[0];
        await doc.ref.update({
            intelligent_analysis: admin.firestore.FieldValue.delete()
        });
        res.status(200).send(`Reset candidate ${doc.id}`);
    } catch (error) {
        console.error(error);
        res.status(500).send(error);
    }
});
