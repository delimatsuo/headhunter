const admin = require('firebase-admin');

admin.initializeApp({
    credential: admin.credential.applicationDefault(),
    projectId: 'headhunter-ai-0088'
});

const db = admin.firestore();

async function inspectCandidate() {
    try {
        console.log('Searching for "Daniel Benzi"...');
        const snapshot = await db.collection('candidates')
            .where('personal.name', '==', 'Daniel Benzi') // Try nested first
            .get();

        if (snapshot.empty) {
            console.log('Not found by personal.name. Trying top-level name...');
            const snapshot2 = await db.collection('candidates')
                .where('name', '==', 'Daniel Benzi')
                .get();

            if (snapshot2.empty) {
                console.log('Candidate not found.');
                return;
            }
            snapshot2.forEach(doc => printDoc(doc));
        } else {
            snapshot.forEach(doc => printDoc(doc));
        }

    } catch (error) {
        console.error('Error:', error);
    }
}

function printDoc(doc) {
    console.log(`\nCandidate ID: ${doc.id}`);
    const data = doc.data();
    console.log('Data keys:', Object.keys(data));

    if (data.intelligent_analysis) {
        console.log('intelligent_analysis:', JSON.stringify(data.intelligent_analysis, null, 2));
    }
    if (data.resume_analysis) {
        console.log('resume_analysis keys:', Object.keys(data.resume_analysis));
        console.log('Career Trajectory:', JSON.stringify(data.resume_analysis.career_trajectory, null, 2));
        console.log('Education:', JSON.stringify(data.resume_analysis.education, null, 2));
    } else {
        console.log('WARNING: resume_analysis is MISSING');
    }

    if (data.personal) {
        console.log('Personal:', JSON.stringify(data.personal, null, 2));
    }
}

inspectCandidate();
