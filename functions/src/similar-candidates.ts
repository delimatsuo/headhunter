import { onCall, HttpsError } from "firebase-functions/v2/https";
import * as admin from "firebase-admin";
import { z } from "zod";
import { VectorSearchService } from "./vector-search";

const FindSimilarInputSchema = z.object({
    candidate_id: z.string(),
    limit: z.number().min(1).max(50).optional().default(10),
});

/**
 * Find candidates similar to a specific candidate
 */
import { defineSecret } from "firebase-functions/params";

const dbPostgresPassword = defineSecret("db-postgres-password");

/**
 * Find candidates similar to a specific candidate
 */
export const findSimilarCandidates = onCall(
    {
        memory: "1GiB",
        timeoutSeconds: 60,
        secrets: [dbPostgresPassword],
        vpcConnector: "svpc-us-central1",
        vpcConnectorEgressSettings: "PRIVATE_RANGES_ONLY",
    },
    async (request) => {
        // Inject DB configuration for Cloud SQL connection
        process.env.PGVECTOR_PASSWORD = dbPostgresPassword.value();
        process.env.PGVECTOR_HOST = "10.159.0.2";
        process.env.PGVECTOR_USER = "postgres";
        process.env.PGVECTOR_DATABASE = "headhunter";

        if (!request.auth) {
            throw new HttpsError("unauthenticated", "User must be logged in to find similar candidates");
        }

        // Validate input
        let validatedInput;
        try {
            validatedInput = FindSimilarInputSchema.parse(request.data);
        } catch (error) {
            if (error instanceof z.ZodError) {
                throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
            }
            throw new HttpsError("invalid-argument", "Invalid request data");
        }

        const { candidate_id, limit } = validatedInput;

        try {
            const vectorSearchService = new VectorSearchService();
            // Fetch more candidates to account for potential orphans
            const fetchLimit = limit * 3;
            const results = await vectorSearchService.findSimilarCandidates(candidate_id, { limit: fetchLimit });

            // Hydrate results with full candidate data from Firestore
            const firestore = admin.firestore();
            console.error(`Starting hydration for ${results.length} candidates`);
            const hydratedResults = await Promise.all(results.map(async (r) => {
                try {
                    console.error(`Hydrating candidate: ${r.candidate_id}`);
                    const doc = await firestore.collection("candidates").doc(r.candidate_id).get();
                    if (doc.exists) {
                        const data = doc.data();
                        console.error(`Found candidate ${r.candidate_id}, name: ${data?.name}`);
                        return {
                            candidate_id: r.candidate_id,
                            similarity_score: r.similarity_score,
                            match_reasons: r.match_reasons,
                            metadata: r.metadata,
                            // Add hydrated fields expected by frontend
                            name: data?.name || data?.profile?.name || data?.personal_details?.name || "Unknown Candidate",
                            current_role: data?.current_role || data?.resume_analysis?.career_trajectory?.current_level || "Role not specified",
                            years_experience: data?.years_experience || data?.resume_analysis?.years_experience || 0,
                            skills: data?.skills || data?.resume_analysis?.technical_skills || [],
                            location: data?.location || "Location not specified",
                            // Include full data for flexibility
                            ...data
                        };
                    }
                } catch (e) {
                    console.error(`Error hydrating candidate ${r.candidate_id}:`, e);
                }
                return null;
            }));

            // Filter out nulls (orphaned or failed fetches) and slice to original limit
            const validResults = hydratedResults.filter(r => r !== null).slice(0, limit);

            return {
                success: true,
                candidate_id,
                results: validResults
            };
        } catch (error) {
            console.error("Error finding similar candidates:", error);
            throw new HttpsError("internal", "Failed to find similar candidates");
        }
    }
);
