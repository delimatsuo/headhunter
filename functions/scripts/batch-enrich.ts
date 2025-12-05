import * as admin from 'firebase-admin';
import { AnalysisService } from '../src/analysis-service';
import * as dotenv from 'dotenv';
import { resolve } from 'path';

// Load environment variables
dotenv.config({ path: resolve(__dirname, '../../.env') });

// Initialize Firebase Admin
if (!admin.apps.length) {
    admin.initializeApp({
        projectId: 'headhunter-ai-0088',
        credential: admin.credential.applicationDefault()
    });
}

const db = admin.firestore();
const BATCH_SIZE = 20;
const CONCURRENCY = 5;

async function main() {
    console.log('🚀 Starting Batch Enrichment...');

    const analysisService = new AnalysisService();

    // Get candidates missing intelligent_analysis
    // Note: Firestore doesn't support "missing field" queries efficiently without an index
    // So we'll fetch batches and filter, or use a specific flag if available.
    // For now, we'll iterate all candidates and check.

    const candidatesRef = db.collection('candidates');
    const snapshot = await candidatesRef.select('candidate_id', 'intelligent_analysis', 'name', 'experience', 'education', 'comments', 'linkedin_url').get();

    console.log(`Found ${snapshot.size} total candidates.`);

    const candidatesToProcess = snapshot.docs.filter(doc => !doc.data().intelligent_analysis);
    console.log(`Found ${candidatesToProcess.length} candidates needing enrichment.`);

    let processed = 0;
    let errors = 0;

    // Process in chunks
    for (let i = 0; i < candidatesToProcess.length; i += BATCH_SIZE * CONCURRENCY) {
        const chunk = candidatesToProcess.slice(i, i + BATCH_SIZE * CONCURRENCY);
        const promises = chunk.map(async (doc) => {
            const data = doc.data();
            try {
                console.log(`Processing ${data.name} (${doc.id})...`);
                const analysis = await analysisService.analyzeCandidate(data);

                const enrichedProfile = {
                    ...data,
                    intelligent_analysis: analysis,
                    original_data: {
                        experience: data.experience,
                        education: data.education,
                        comments: data.comments
                    },
                    linkedin_url: analysis.personal_details?.linkedin || data.linkedin_url,
                    processing_metadata: {
                        timestamp: admin.firestore.FieldValue.serverTimestamp(),
                        processor: "batch_enrich_script",
                        model: "gemini-2.5-flash-001"
                    }
                };

                await db.collection('enriched_profiles').doc(doc.id).set(enrichedProfile);
                await db.collection('candidates').doc(doc.id).set(enrichedProfile, { merge: true });

                processed++;
            } catch (e) {
                console.error(`Error processing ${doc.id}:`, e);
                errors++;
            }
        });

        await Promise.all(promises);
        console.log(`Progress: ${processed}/${candidatesToProcess.length} (Errors: ${errors})`);
    }

    console.log('✅ Batch Enrichment Complete.');
}

main().catch(console.error);
