/**
 * Centralized configuration for buckets and collections
 */

export const PROJECT_ID = process.env.GOOGLE_CLOUD_PROJECT || process.env.GCLOUD_PROJECT || "project";

// Buckets
export const BUCKET_PROFILES = process.env.PROFILES_BUCKET || `${PROJECT_ID}-profiles`;
export const BUCKET_FILES = process.env.FILES_BUCKET || `${PROJECT_ID}-files`;

// Collections
export const COLLECTION_CANDIDATES = process.env.COLLECTION_CANDIDATES || "candidates";
export const COLLECTION_ENRICHED = process.env.COLLECTION_ENRICHED || "enriched_profiles";
export const COLLECTION_EMBEDDINGS = process.env.COLLECTION_EMBEDDINGS || "candidate_embeddings";

// Feature flags
export const USE_PGVECTOR = (process.env.USE_PGVECTOR || "false").toLowerCase() === "true";
export const ENABLE_GEMINI = (process.env.ENABLE_GEMINI || "false").toLowerCase() === "true";

