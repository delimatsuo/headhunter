
import * as admin from 'firebase-admin';
import * as fs from 'fs';

// Initialize Firebase Admin
// We need to point to the service account key if it exists, or rely on default credentials
// Assuming standard firebase setup or emulator
// For this environment, I'll try to use the project ID directly if I can find where credentials are.
// Or I can just use the existing firebase config if I can import it.
// But `functions/src/config/firebase.ts` might be better.

// Let's try to just use the `functions` directory context where admin is likely set up
// or just use a standalone script that initializes admin.

const projectId = 'headhunter-ai-0088';

admin.initializeApp({
    projectId: projectId,
    credential: admin.credential.applicationDefault()
});

const db = admin.firestore();

async function debugCandidateData() {
    console.log('Fetching candidates...');
    const args = process.argv.slice(2);
    const searchName = args[0];

    let query: admin.firestore.Query = db.collection('candidates');

    if (searchName) {
        console.log(`Searching for candidate with name: ${searchName}`);
        query = query.where('name', '==', searchName);
    } else {
        query = query.limit(5);
    }

    const snapshot = await query.get();

    if (snapshot.empty) {
        console.log('No candidates found.');
        return;
    }

    snapshot.forEach(doc => {
        const data = doc.data();
        console.log(`\n🔍 Inspecting Candidate: ${doc.id}`);
        console.log(`   Name: ${data.name}`);
        console.log(`   Resume URL: ${data.resume_url}`);
        console.log(`   LinkedIn URL: ${data.linkedin_url}`);
        console.log(`   Intelligent Analysis: ${JSON.stringify(data.intelligent_analysis, null, 2)}`);
        console.log(`   Original Data: ${JSON.stringify(data.original_data, null, 2)}`);
        console.log('-----------------------------------');
        if (data.resume_analysis?.career_trajectory) {
            console.log('Resume Analysis Level:', data.resume_analysis.career_trajectory.current_level);
            console.log('Resume Analysis Years:', data.resume_analysis.career_trajectory.years_experience);
        }
    });
}

debugCandidateData().catch(console.error);
