import { onCall, HttpsError } from "firebase-functions/v2/https";
import { z } from "zod";
import { VectorSearchService } from "./vector-search";

const FindSimilarInputSchema = z.object({
    candidate_id: z.string(),
    limit: z.number().min(1).max(50).optional().default(10),
});

/**
 * Find candidates similar to a specific candidate
 */
export const findSimilarCandidates = onCall(
    {
        memory: "1GiB",
        timeoutSeconds: 60,
    },
    async (request) => {
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
            const results = await vectorSearchService.findSimilarCandidates(candidate_id, { limit });

            return {
                success: true,
                candidate_id,
                results: results.map(r => ({
                    candidate_id: r.candidate_id,
                    similarity_score: r.similarity_score,
                    match_reasons: r.match_reasons,
                    metadata: r.metadata
                }))
            };
        } catch (error) {
            console.error("Error finding similar candidates:", error);
            throw new HttpsError("internal", "Failed to find similar candidates");
        }
    }
);
