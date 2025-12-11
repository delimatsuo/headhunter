/**
 * Centralized AI Model Configuration
 * 
 * IMPORTANT: Update model versions here ONLY. All AI calls import from this file.
 * This is the single source of truth for model configuration.
 * 
 * Last updated: 2025-12-08
 * 
 * VERIFIED AVAILABLE MODELS (December 2025):
 * - gemini-2.5-flash (GA since June 17, 2025) ✅ CURRENT
 * - gemini-2.5-pro (GA since June 17, 2025)
 * - gemini-3.0-pro (latest, Nov 18, 2025)
 * 
 * DO NOT USE THESE (deprecated or non-existent):
 * - gemini-1.5-flash (deprecated)
 * - gemini-2.5-flash-001 (DOES NOT EXIST - use gemini-2.5-flash)
 * - gemini-2.0-flash (superseded by 2.5)
 */

// ============================================================================
// GEMINI MODELS
// ============================================================================

/**
 * Primary Gemini model for text generation, analysis, and enrichment
 * VERIFIED: gemini-2.5-flash is GA since June 17, 2025
 * 
 * ⚠️ DO NOT CHANGE THIS MODEL WITHOUT SEARCHING ONLINE FOR THE LATEST
 * AVAILABLE GEMINI MODEL FIRST. VERIFY IT EXISTS BEFORE DEPLOYING.
 */
export const GEMINI_MODEL = 'gemini-2.5-flash';

/**
 * Gemini model for document/image processing (PDF text extraction)
 * VERIFIED: gemini-2.5-flash supports multimodal input
 * 
 * ⚠️ DO NOT CHANGE THIS MODEL WITHOUT SEARCHING ONLINE FOR THE LATEST
 * AVAILABLE GEMINI MODEL FIRST. VERIFY IT EXISTS BEFORE DEPLOYING.
 */
export const GEMINI_VISION_MODEL = 'gemini-2.5-flash';

// ============================================================================
// EMBEDDING MODELS
// ============================================================================

/**
 * Model for generating text embeddings (vector search)
 * Used by: vector-search, pgvector-client
 * 
 * ⚠️ DO NOT CHANGE THIS MODEL WITHOUT VERIFYING THE LATEST VERSION FIRST.
 */
export const EMBEDDING_MODEL = 'text-embedding-004';

/**
 * Embedding vector dimensions (must match the model output)
 */
export const EMBEDDING_DIMENSIONS = 768;

// ============================================================================
// TOGETHER AI MODELS (if used for reranking)
// ============================================================================

// ⚠️ DO NOT CHANGE THESE MODELS WITHOUT VERIFYING THE LATEST VERSION FIRST.
export const TOGETHER_RERANK_MODEL = 'rerank-advanced-v2';
export const TOGETHER_EMBED_MODEL = 'text-embedding-3-large';

// ============================================================================
// MODEL CONFIGURATION HELPERS
// ============================================================================

/**
 * Get Gemini model configuration for GoogleGenerativeAI
 */
export const getGeminiConfig = (options?: {
    temperature?: number;
    maxOutputTokens?: number;
    responseMimeType?: string;
}) => ({
    model: GEMINI_MODEL,
    generationConfig: {
        temperature: options?.temperature ?? 0.2,
        maxOutputTokens: options?.maxOutputTokens ?? 8192,
        ...(options?.responseMimeType && { responseMimeType: options.responseMimeType }),
    },
});

/**
 * Get Vertex AI model configuration
 */
export const getVertexModelConfig = () => ({
    model: GEMINI_MODEL,
});
