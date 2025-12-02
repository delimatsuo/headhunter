import { onCall } from "firebase-functions/v2/https";
import { defineSecret } from "firebase-functions/params";
import { VectorSearchService } from "./vector-search";

const dbPostgresPassword = defineSecret("db-postgres-password");

export const debugSearch = onCall(
    {
        memory: "1GiB",
        timeoutSeconds: 60,
        secrets: [dbPostgresPassword],
        vpcConnector: "svpc-us-central1",
        vpcConnectorEgressSettings: "PRIVATE_RANGES_ONLY",
    },
    async (request) => {
        process.env.PGVECTOR_PASSWORD = dbPostgresPassword.value();
        process.env.PGVECTOR_HOST = "10.159.0.2";
        process.env.PGVECTOR_USER = "postgres";
        process.env.PGVECTOR_DATABASE = "headhunter";

        const vectorService = new VectorSearchService();

        try {
            const results = await vectorService.searchCandidates({
                query_text: "User Acquisition",
                limit: 5
            });

            return {
                query: "User Acquisition",
                count: results.length,
                results: results.map(r => ({
                    id: r.candidate_id,
                    score: r.similarity_score,
                    metadata: r.metadata
                }))
            };
        } catch (error) {
            return { error: (error as Error).message };
        }
    }
);
