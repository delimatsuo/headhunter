import * as functions from 'firebase-functions';
import * as admin from 'firebase-admin';
import { AnalysisService } from './analysis-service';

const db = admin.firestore();
const analysisService = new AnalysisService();

export const batchEnrichCandidates = functions.https.onRequest(async (req, res) => {
    try {
        const batchSize = req.query.batchSize ? parseInt(req.query.batchSize as string) : 50;
        const startAfterId = req.query.startAfter as string;
        const force = req.query.force === 'true';

        const limit = Math.min(batchSize, 100);

        console.log(`Starting batch enrichment. Batch: ${limit}, StartAfter: ${startAfterId}, Force: ${force}`);

        let query = db.collection('candidates').orderBy(admin.firestore.FieldPath.documentId()).limit(limit);

        if (startAfterId) {
            const startAfterDoc = await db.collection('candidates').doc(startAfterId).get();
            if (startAfterDoc.exists) {
                query = db.collection('candidates').orderBy(admin.firestore.FieldPath.documentId()).startAfter(startAfterDoc).limit(limit);
            } else {
                // Fallback if doc doesn't exist (shouldn't happen often)
                console.warn(`StartAfter doc ${startAfterId} not found. Starting from beginning.`);
            }
        }

        const snapshot = await query.get();

        if (snapshot.empty) {
            console.log('No more candidates found.');
            res.status(200).json({ message: 'No more candidates.', processed: 0, lastDocId: null });
            return;
        }

        const lastDoc = snapshot.docs[snapshot.docs.length - 1];
        const lastDocId = lastDoc.id;

        // Filter: Process if force=true OR intelligent_analysis is missing
        const candidatesToProcess = snapshot.docs.filter(doc => {
            if (force) return true;
            return !doc.data().intelligent_analysis;
        });

        console.log(`Scanned ${snapshot.size} docs. Found ${candidatesToProcess.length} to process.`);

        let processed = 0;
        let errors = 0;

        const promises = candidatesToProcess.map(async (doc) => {
            const data = doc.data();
            try {
                console.log(`Processing ${data.name} (${doc.id})...`);
                const analysis = await analysisService.analyzeCandidate(data);

                // Create enriched profile
                const enrichedProfile = JSON.parse(JSON.stringify({
                    ...data,
                    intelligent_analysis: analysis,
                    original_data: {
                        experience: data.experience || null,
                        education: data.education || null,
                        comments: data.comments || null
                    },
                    linkedin_url: analysis.personal_details?.linkedin || data.linkedin_url || null,
                    processing_metadata: {
                        timestamp: new Date().toISOString(),
                        processor: "batch_enrich_function",
                        model: "gemini-2.5-flash"
                    }
                }));

                enrichedProfile.processing_metadata.timestamp = admin.firestore.FieldValue.serverTimestamp();

                await db.collection('enriched_profiles').doc(doc.id).set(enrichedProfile);
                await db.collection('candidates').doc(doc.id).set(enrichedProfile, { merge: true });

                processed++;
            } catch (e) {
                console.error(`Error processing ${doc.id}:`, e);
                errors++;
            }
        });

        await Promise.all(promises);

        console.log(`Batch complete. Processed: ${processed}, Errors: ${errors}`);
        res.status(200).json({
            message: 'Batch enrichment complete',
            processed,
            errors,
            lastDocId,
            scanned: snapshot.size
        });

    } catch (error) {
        console.error('Error in batchEnrichCandidates:', error);
        res.status(500).json({ error: 'Internal Server Error', details: error });
    }
});
