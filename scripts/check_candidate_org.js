const admin = require('firebase-admin');
const serviceAccount = require('../functions/service-account.json');

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount)
});

const db = admin.firestore();

async function check() {
  const snapshot = await db.collection('candidates').limit(1).get();
  if (snapshot.empty) {
    console.log('No candidates found');
    return;
  }
  const data = snapshot.docs[0].data();
  console.log('Candidate Org ID:', data.organization_id);
}

check();
