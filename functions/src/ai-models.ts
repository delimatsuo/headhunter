/**
 * Centralized AI Model Configuration
 * 
 * IMPORTANT: Update model versions here. All AI calls should import from this file.
 * This is the single source of truth for model configuration.
 * 
 * Last updated: 2025-12-05
 */

// ============================================================================
// GEMINI MODELS
// ============================================================================

/**
 * Primary Gemini model for text generation, analysis, and enrichment
 * Used by: analysis-service, search-agent, file-upload-pipeline
 */
export const GEMINI_MODEL = 'gemini-2.5-flash-001';

/**
 * Gemini model for document/image processing (PDF text extraction)
 * May need multimodal capabilities
 */
export const GEMINI_VISION_MODEL = 'gemini-2.5-flash-001';

// ============================================================================
// EMBEDDING MODELS
// ============================================================================

/**
 * Model for generating text embeddings (vector search)
 * Used by: vector-search, pgvector-client
 */
export const EMBEDDING_MODEL = 'text-embedding-004';

/**
 * Embedding vector dimensions (must match the model output)
 */
export const EMBEDDING_DIMENSIONS = 768;

// ============================================================================
// TOGETHER AI MODELS (if used for reranking)
// ============================================================================

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
