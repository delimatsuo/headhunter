const admin = require('firebase-admin');
const serviceAccount = require('../functions/service-account.json');

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount)
});

const db = admin.firestore();

async function verify() {
  const doc = await db.collection('enriched_profiles').doc('142560148').get();
  if (!doc.exists) {
    console.log('Profile not found');
    return;
  }
  const data = doc.data();
  console.log(JSON.stringify(data.intelligent_analysis, null, 2));
}

verify();
