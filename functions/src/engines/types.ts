/**
 * AI Engine Interface and Types
 * 
 * Defines the contract for pluggable search engines that can be swapped
 * at runtime for A/B testing and comparison.
 */

// ============================================================================
// JOB DESCRIPTION TYPES
// ============================================================================

export interface JobDescription {
    title?: string;
    description: string;
    required_skills?: string[];
    nice_to_have?: string[];
    min_experience?: number;
    max_experience?: number;
    // Sourcing strategy for tech stack context and targeting
    sourcing_strategy?: {
        tech_stack?: {
            core?: string[];    // Core tech required: ["Node.js", "TypeScript"]
            avoid?: string[];   // Tech to avoid: ["Oracle", "legacy"]
        };
        target_companies?: string[];
        target_industries?: string[];
    };
}

export interface SourcingStrategy {
    target_industries?: string[];
    target_companies?: string[];
    location_preference?: string;
    experience_level?: string;
}

// ============================================================================
// SEARCH RESULT TYPES
// ============================================================================

export interface CandidateMatch {
    candidate_id: string;
    candidate: any; // Full candidate profile
    score: number;
    rationale: {
        overall_assessment: string;
        strengths: string[];
        concerns?: string[];           // Agentic: potential red flags
        interview_questions?: string[]; // Agentic: suggested questions
        gaps?: string[];               // Identified skill/experience gaps
        risk_factors?: string[];       // Risk factors for the hire
    };
    // Metadata about how this match was computed
    match_metadata?: {
        vector_score?: number;
        raw_vector_similarity?: number;  // Preserved raw similarity from vector search
        gemini_score?: number;           // Gemini reranking score
        title_affinity_boost?: number;
        company_boost?: number;
        rerank_score?: number;
        // Multi-signal retrieval fields (v4.0+)
        sources?: string[];
        score_breakdown?: any;
        vertex_score?: number;
        target_function?: string;
        target_level?: string;
        candidate_function?: string;
        classification_score?: number;
        candidate_level?: string;
        function_match?: string;
        experience_match?: number;
        confidence_score?: number;
        skill_match_score?: number;
    };
}

export interface SearchResult {
    matches: CandidateMatch[];
    total_candidates: number;
    query_time_ms: number;
    engine_used: string;           // Track which engine produced these results
    engine_version?: string;       // For tracking improvements over time
    metadata?: {
        job_analysis?: JobAnalysis;  // Agentic: deep job understanding
        ranking_explanation?: string; // Agentic: why this specific order
        search_strategy?: string;     // What approach was used
        used_vertex_ranking?: boolean; // Whether Vertex AI Ranking was used
        target_classification?: any;   // LLM-based job classification
    };
}

// ============================================================================
// AGENTIC ENGINE SPECIFIC TYPES
// ============================================================================

export interface JobAnalysis {
    // Core understanding
    core_problem: string;          // What strategic problem is this person solving?
    success_indicators: string[];  // What does success look like in 1 year?

    // Role classification
    function: 'engineering' | 'product' | 'data' | 'sales' | 'marketing' | 'finance' | 'hr' | 'operations' | 'design' | 'general';
    level: 'c-suite' | 'vp' | 'director' | 'manager' | 'ic';
    leadership_style: 'builder' | 'scaler' | 'turnaround' | 'operator';

    // Requirements
    must_haves: string[];          // Non-negotiable requirements
    nice_to_haves: string[];       // Bonus qualifications
    red_flags: string[];           // What would disqualify a candidate

    // Context
    company_stage?: string;        // startup, growth, enterprise
    industry_context?: string;     // B2B, B2C, regulated, etc.
    ideal_trajectory?: string;     // What career path leads here
}

// ============================================================================
// AI ENGINE INTERFACE
// ============================================================================

export interface SearchOptions {
    limit?: number;
    page?: number;
    sourcingStrategy?: SourcingStrategy;
    onProgress?: (message: string) => void;
}

/**
 * IAIEngine - The contract that all search engines must implement
 * 
 * This interface defines the common API for different search strategies,
 * allowing them to be swapped at runtime for A/B testing and comparison.
 */
export interface IAIEngine {
    /**
     * Unique identifier for this engine
     * Used for tracking and comparison
     */
    getName(): string;

    /**
     * Human-readable description
     * Shown to users in the engine selector
     */
    getDescription(): string;

    /**
     * Short label for UI display
     */
    getLabel(): string;

    /**
     * Main search method
     * Takes a job description and returns ranked candidates
     */
    search(
        job: JobDescription,
        options?: SearchOptions
    ): Promise<SearchResult>;
}

// ============================================================================
// ENGINE REGISTRY
// ============================================================================

export type EngineType = 'legacy' | 'agentic';

export const ENGINE_DESCRIPTIONS: Record<EngineType, { label: string; description: string }> = {
    legacy: {
        label: '⚡ Fast Match',
        description: 'Vector similarity + Title boost + LLM reranking. Fast and reliable.'
    },
    agentic: {
        label: '🧠 Deep Analysis',
        description: 'Comparative reasoning with detailed insights. Thorough and explanatory.'
    }
};
