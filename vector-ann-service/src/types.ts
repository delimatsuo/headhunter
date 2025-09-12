export interface EmbeddingProvider {
  generateEmbedding(text: string): Promise<number[]>;
}

export interface PgVectorClient {
  searchANN(embedding: number[], limit: number, filters?: Record<string, unknown>): Promise<Array<{
    candidate_id: string;
    similarity_score: number;
    metadata: Record<string, unknown>;
  }>>;
}

export interface SkillRequirement {
  skill: string;
  minimum_confidence?: number;
  weight?: number;
  category?: string;
}

export interface SkillAwareSearchRequest {
  text_query: string;
  required_skills?: SkillRequirement[];
  preferred_skills?: SkillRequirement[];
  experience_level?: 'entry' | 'mid' | 'senior' | 'executive';
  minimum_overall_confidence?: number;
  filters?: Record<string, unknown>;
  limit?: number;
  ranking_weights?: {
    skill_match?: number;
    confidence?: number;
    vector_similarity?: number;
    experience_match?: number;
  };
}

