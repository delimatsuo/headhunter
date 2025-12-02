import * as functions from 'firebase-functions';
import * as admin from 'firebase-admin';

const db = admin.firestore();

export const getMainOrgId = functions.https.onRequest(async (req, res) => {
    try {
        // Just get the org_id from the first candidate
        const snapshot = await db.collection('candidates').limit(1).get();
        if (snapshot.empty) {
            res.status(404).send('No candidates found');
            return;
        }
        const data = snapshot.docs[0].data();
        res.status(200).json(data);
    } catch (error) {
        console.error(error);
        res.status(500).send(error);
    }
});

export const addUserToOrg = functions.https.onRequest(async (req, res) => {
    try {
        const email = req.query.email as string;
        const orgId = req.query.orgId as string;

        if (!email || !orgId) {
            res.status(400).send('Missing email or orgId');
            return;
        }

        // Find user by email
        const userRecord = await admin.auth().getUserByEmail(email);
        const userId = userRecord.uid;

        // Update user doc
        await db.collection('users').doc(userId).update({
            organization_id: orgId
        });

        // Update custom claims
        const currentClaims = (await admin.auth().getUser(userId)).customClaims || {};
        await admin.auth().setCustomUserClaims(userId, {
            ...currentClaims,
            org_id: orgId
        });

        // Add to org members
        await db.collection('organizations').doc(orgId).update({
            members: admin.firestore.FieldValue.arrayUnion(userId)
        });

        res.status(200).send(`Added ${email} to ${orgId}`);
    } catch (error) {
        console.error(error);
        res.status(500).send((error as any).message);
    }
});
