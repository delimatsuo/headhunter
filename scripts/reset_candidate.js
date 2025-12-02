const admin = require('firebase-admin');
const serviceAccount = require('../functions/service-account.json');

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount)
});

const db = admin.firestore();

async function reset() {
  const snapshot = await db.collection('candidates').limit(1).get();
  if (snapshot.empty) {
    console.log('No candidates found');
    return;
  }
  const doc = snapshot.docs[0];
  console.log('Resetting candidate:', doc.id);
  await doc.ref.update({
    intelligent_analysis: admin.firestore.FieldValue.delete()
  });
  console.log('Done');
}

reset();
