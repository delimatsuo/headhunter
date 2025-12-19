/**
 * Engine Search API
 * 
 * Cloud Function that exposes the modular AI Engine system.
 * Allows the frontend to select which engine to use for each search.
 */

import { onCall, HttpsError } from "firebase-functions/v2/https";
import { defineSecret } from "firebase-functions/params";
import { z } from "zod";

import { getEngine, EngineType, JobDescription, SearchOptions } from "./engines";
import { VectorSearchService } from "./vector-search";

const dbPostgresPassword = defineSecret("db-postgres-password");

// ============================================================================
// SCHEMA VALIDATION
// ============================================================================

const EngineSearchRequestSchema = z.object({
    // Engine selection
    engine: z.enum(['legacy', 'agentic']).default('legacy'),

    // Job description
    job: z.object({
        title: z.string().optional(),
        description: z.string(),
        required_skills: z.array(z.string()).optional().nullable(),
        nice_to_have: z.array(z.string()).optional().nullable(),
        min_experience: z.number().optional().nullable(),
        max_experience: z.number().optional().nullable(),
    }),

    // Search options
    options: z.object({
        limit: z.number().min(1).max(300).default(50),
        page: z.number().min(0).default(0),
        sourcingStrategy: z.object({
            target_industries: z.array(z.string()).optional().nullable(),
            target_companies: z.array(z.string()).optional().nullable(),
            location_preference: z.string().optional().nullable(),
            experience_level: z.string().optional().nullable(),
        }).optional().nullable(),
    }).optional().nullable(),
});

// ============================================================================
// CLOUD FUNCTION
// ============================================================================

export const engineSearch = onCall(
    {
        memory: "2GiB",
        timeoutSeconds: 120,
        secrets: [dbPostgresPassword],
        vpcConnector: "svpc-us-central1",
        vpcConnectorEgressSettings: "PRIVATE_RANGES_ONLY",
    },
    async (request) => {
        const startTime = Date.now();

        // Validate request
        const validationResult = EngineSearchRequestSchema.safeParse(request.data);
        if (!validationResult.success) {
            throw new HttpsError(
                "invalid-argument",
                `Invalid request: ${validationResult.error.message}`
            );
        }

        const { engine: engineType, job, options } = validationResult.data;

        console.log(`[EngineSearch] Engine: ${engineType}, Job: ${job.title || 'untitled'}`);

        try {
            // ===== Set database password from secret =====
            process.env.PGVECTOR_PASSWORD = dbPostgresPassword.value();

            // ===== STEP 1: Vector Search (shared by all engines) =====
            const vectorService = new VectorSearchService();

            // Construct query for skill-aware search
            const vectorResults = await vectorService.searchCandidatesSkillAware({
                text_query: `
          Title: ${job.title || 'Executive role'}
          Description: ${job.description}
          Required Skills: ${(job.required_skills || []).join(', ')}
          Experience: ${job.min_experience || 0}-${job.max_experience || 20} years
        `.trim(),
                limit: 300, // Fetch large pool for engine processing
            });

            console.log(`[EngineSearch] Vector search returned ${vectorResults?.length || 0} candidates`);

            // ===== STEP 2: Get Engine and Process =====
            const engine = getEngine(engineType as EngineType);

            // Cast engine to access search method with vector results
            const engineWithVectorSearch = engine as any;
            const searchResult = await engineWithVectorSearch.search(
                job as JobDescription,
                {
                    limit: options?.limit || 50,
                    page: options?.page || 0,
                    sourcingStrategy: options?.sourcingStrategy,
                },
                vectorResults // Pass vector results to engine
            );

            console.log(`[EngineSearch] Engine ${engineType} returned ${searchResult.matches.length} matches`);

            // ===== STEP 3: Return Results =====
            return {
                success: true,
                results: searchResult.matches,
                total_candidates: searchResult.total_candidates,
                engine_used: searchResult.engine_used,
                engine_version: searchResult.engine_version,
                metadata: searchResult.metadata,
                execution_time_ms: Date.now() - startTime
            };

        } catch (error: any) {
            console.error('[EngineSearch] Error:', error);
            throw new HttpsError(
                "internal",
                `Search failed: ${error.message || 'Unknown error'}`
            );
        }
    }
);

// ============================================================================
// HELPER: Get Available Engines
// ============================================================================

export const getAvailableEngines = onCall(async () => {
    return {
        engines: [
            {
                id: 'legacy',
                label: '⚡ Fast Match',
                description: 'Vector similarity + Title boost + LLM reranking. Fast and reliable.'
            },
            {
                id: 'agentic',
                label: '🧠 Deep Analysis',
                description: 'Comparative reasoning with detailed insights. Thorough and explanatory.'
            }
        ],
        default: 'legacy'
    };
});
