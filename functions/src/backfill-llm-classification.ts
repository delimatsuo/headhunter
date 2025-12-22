/**
 * Backfill LLM Classification
 * 
 * Re-classifies all existing candidates using the new LLM-based
 * multi-function classification system.
 */

import * as admin from 'firebase-admin';
import { onCall, HttpsError } from 'firebase-functions/v2/https';
import { getLLMClassificationService, LLMClassificationService, CandidateClassification } from './llm-classification-service';

const db = admin.firestore();

interface BackfillStats {
    total: number;
    processed: number;
    success: number;
    errors: number;
    skipped: number;
}

/**
 * Backfill LLM classifications for all candidates
 * Call with force=true to reclassify already-classified candidates
 */
export const backfillLLMClassifications = onCall(
    {
        timeoutSeconds: 540,  // 9 minutes max
        memory: '1GiB',
    },
    async (request) => {
        // Auth check - only admins should run this
        if (!request.auth) {
            throw new HttpsError('unauthenticated', 'Must be authenticated');
        }

        const force = request.data?.force === true;
        const batchSize = request.data?.batchSize || 50;  // Process 50 at a time (for 29K candidates)
        const startAfter = request.data?.startAfter || null;

        console.log(`[BackfillLLM] Starting backfill. force=${force}, batchSize=${batchSize}`);

        const classificationService = getLLMClassificationService();
        const stats: BackfillStats = {
            total: 0,
            processed: 0,
            success: 0,
            errors: 0,
            skipped: 0
        };

        try {
            // Get total count
            const countSnapshot = await db.collection('candidates').count().get();
            stats.total = countSnapshot.data().count;

            // Build query
            let query = db.collection('candidates')
                .orderBy('__name__')
                .limit(batchSize);

            if (startAfter) {
                const startDoc = await db.collection('candidates').doc(startAfter).get();
                if (startDoc.exists) {
                    query = query.startAfter(startDoc);
                }
            }

            const snapshot = await query.get();
            console.log(`[BackfillLLM] Processing batch of ${snapshot.size} candidates`);

            // Process each candidate
            for (const doc of snapshot.docs) {
                stats.processed++;
                const candidateId = doc.id;
                const data = doc.data();

                try {
                    // Skip if already classified with v2.0 and not forcing
                    if (!force && data.searchable?.classification_version === '2.0') {
                        console.log(`[BackfillLLM] Skipping ${candidateId} - already classified v2.0`);
                        stats.skipped++;
                        continue;
                    }

                    // Build profile for classification
                    const profile = data.profile || {};
                    const originalData = data.original_data || {};

                    const candidateProfile = {
                        name: profile.name || data.name || 'Unknown',
                        current_role: profile.current_role || data.searchable?.title_keywords?.[0] || '',
                        experience: originalData.experience || profile.experience || [],
                        skills: profile.skills || profile.top_skills?.map((s: any) => s.skill || s) || [],
                        summary: profile.summary || ''
                    };

                    // Get LLM classification
                    const classification = await classificationService.classifyCandidate(candidateProfile);

                    // Update candidate document
                    await doc.ref.update({
                        'searchable.functions': classification.functions,
                        'searchable.function': classification.primary_function,  // Backward compatibility
                        'searchable.level': classification.primary_level,
                        'searchable.classification_version': classification.classification_version,
                        'searchable.classified_at': classification.classified_at,
                        'searchable.classification_model': classification.model_used,
                    });

                    console.log(`[BackfillLLM] Classified ${candidateProfile.name}: ${classification.primary_function}/${classification.primary_level} (${classification.functions.length} functions)`);
                    stats.success++;

                    // Rate limit to avoid quota issues (100ms delay between candidates)
                    await new Promise(resolve => setTimeout(resolve, 100));

                } catch (error: any) {
                    console.error(`[BackfillLLM] Error processing ${candidateId}:`, error.message);
                    stats.errors++;
                }
            }

            // Return stats and continuation token
            const lastDoc = snapshot.docs[snapshot.docs.length - 1];
            const hasMore = snapshot.size === batchSize;

            return {
                success: true,
                stats,
                continuation: hasMore ? {
                    startAfter: lastDoc?.id,
                    hasMore: true
                } : {
                    hasMore: false
                },
                message: hasMore
                    ? `Processed ${stats.processed}/${stats.total}. Call again with startAfter: "${lastDoc?.id}" to continue.`
                    : `Completed! Processed ${stats.processed} candidates.`
            };

        } catch (error: any) {
            console.error('[BackfillLLM] Fatal error:', error);
            throw new HttpsError('internal', error.message);
        }
    }
);

/**
 * Get statistics on current classification coverage
 */
export const getLLMClassificationStats = onCall(
    {
        timeoutSeconds: 60,
        memory: '512MiB',
    },
    async (request) => {
        if (!request.auth) {
            throw new HttpsError('unauthenticated', 'Must be authenticated');
        }

        // Count total candidates
        const totalSnapshot = await db.collection('candidates').count().get();
        const total = totalSnapshot.data().count;

        // Sample to check classification versions
        const sampleSnapshot = await db.collection('candidates')
            .limit(500)
            .get();

        let v2Count = 0;
        let v1Count = 0;
        let unclassified = 0;
        const functionCounts: Record<string, number> = {};

        sampleSnapshot.docs.forEach(doc => {
            const data = doc.data();
            const version = data.searchable?.classification_version;

            if (version === '2.0') {
                v2Count++;
            } else if (data.searchable?.function) {
                v1Count++;
            } else {
                unclassified++;
            }

            // Count functions
            const func = data.searchable?.function || 'unknown';
            functionCounts[func] = (functionCounts[func] || 0) + 1;
        });

        const sampleSize = sampleSnapshot.size;

        return {
            total,
            sampleSize,
            classification: {
                v2_llm: v2Count,
                v1_rules: v1Count,
                unclassified
            },
            percentages: {
                v2_llm: ((v2Count / sampleSize) * 100).toFixed(1) + '%',
                v1_rules: ((v1Count / sampleSize) * 100).toFixed(1) + '%',
                unclassified: ((unclassified / sampleSize) * 100).toFixed(1) + '%'
            },
            functionDistribution: functionCounts,
            estimatedV2Total: Math.round((v2Count / sampleSize) * total)
        };
    }
);
