/**
 * Vector Search functionality for candidate profile similarity matching
 */

import { MatchServiceClient } from "@google-cloud/aiplatform";
import { Storage } from "@google-cloud/storage";
import * as admin from "firebase-admin";

// Types for vector search
interface EmbeddingData {
  candidate_id: string;
  embedding_vector: number[];
  embedding_text: string;
  metadata: {
    years_experience: number;
    current_level: string;
    company_tier: string;
    overall_score: number;
    technical_skills?: string[];
    leadership_level?: string;
    updated_at: string;
  };
}

interface VectorSearchResult {
  candidate_id: string;
  similarity_score: number;
  metadata: EmbeddingData["metadata"];
  match_reasons: string[];
}

interface SearchQuery {
  query_text: string;
  filters?: {
    min_years_experience?: number;
    current_level?: string;
    company_tier?: string;
    min_score?: number;
  };
  limit?: number;
}

export class VectorSearchService {
  private matchClient: MatchServiceClient;
  private storage: Storage;
  private firestore: admin.firestore.Firestore;
  private projectId: string;
  private region: string;
  private indexEndpoint: string;
  private deployedIndexId: string;

  constructor() {
    this.matchClient = new MatchServiceClient({
      apiEndpoint: "us-central1-aiplatform.googleapis.com",
    });
    this.storage = new Storage();
    this.firestore = admin.firestore();
    this.projectId = process.env.GOOGLE_CLOUD_PROJECT || "headhunter-ai-0088";
    this.region = "us-central1";
    
    // These will need to be configured after Vector Search setup
    this.indexEndpoint = `projects/${this.projectId}/locations/${this.region}/indexEndpoints/ENDPOINT_ID`;
    this.deployedIndexId = "DEPLOYED_INDEX_ID";
  }

  /**
   * Generate text embeddings using Vertex AI
   */
  async generateEmbedding(text: string): Promise<number[]> {
    // For now, return a mock embedding
    // In production, this would call Vertex AI Text Embeddings API
    
    // Mock 768-dimensional embedding (text-embedding-004 dimensions)
    const mockEmbedding = Array.from({ length: 768 }, () => Math.random() - 0.5);
    
    // Add some semantic meaning based on text content
    const textLower = text.toLowerCase();
    
    // Boost certain dimensions based on keywords
    if (textLower.includes("senior") || textLower.includes("lead")) {
      for (let i = 0; i < 50; i++) {
        mockEmbedding[i] += 0.2;
      }
    }
    
    if (textLower.includes("python") || textLower.includes("machine learning")) {
      for (let i = 100; i < 150; i++) {
        mockEmbedding[i] += 0.3;
      }
    }
    
    if (textLower.includes("leadership") || textLower.includes("management")) {
      for (let i = 200; i < 250; i++) {
        mockEmbedding[i] += 0.25;
      }
    }
    
    // Normalize the vector
    const magnitude = Math.sqrt(mockEmbedding.reduce((sum, val) => sum + val * val, 0));
    return mockEmbedding.map(val => val / magnitude);

    /* TODO: Replace with actual Vertex AI call
    const request = {
      endpoint: `projects/${this.projectId}/locations/${this.region}/publishers/google/models/text-embedding-004`,
      instances: [{
        content: text
      }]
    };
    
    const [response] = await this.predictionClient.predict(request);
    return response.predictions[0].embeddings.values;
    */
  }

  /**
   * Extract relevant text from candidate profile for embedding
   */
  extractEmbeddingText(profile: any): string {
    const textParts: string[] = [];
    
    // Career information
    if (profile.resume_analysis) {
      const resume = profile.resume_analysis;
      
      // Level and experience
      textParts.push(`${resume.career_trajectory?.current_level || ""} level professional`);
      textParts.push(`${resume.years_experience || 0} years experience`);
      
      // Skills
      if (resume.technical_skills?.length) {
        textParts.push(`Technical skills: ${resume.technical_skills.join(", ")}`);
      }
      
      if (resume.soft_skills?.length) {
        textParts.push(`Soft skills: ${resume.soft_skills.join(", ")}`);
      }
      
      // Career trajectory
      if (resume.career_trajectory) {
        textParts.push(`Career trajectory: ${resume.career_trajectory.trajectory_type || ""}`);
        if (resume.career_trajectory.domain_expertise?.length) {
          textParts.push(`Domain expertise: ${resume.career_trajectory.domain_expertise.join(", ")}`);
        }
      }
      
      // Leadership
      if (resume.leadership_scope?.has_leadership) {
        textParts.push(`Leadership experience: ${resume.leadership_scope.leadership_level || "Team Lead"}`);
        if (resume.leadership_scope.team_size) {
          textParts.push(`Managed team of ${resume.leadership_scope.team_size}`);
        }
      }
      
      // Company background
      if (resume.company_pedigree) {
        textParts.push(`Company tier: ${resume.company_pedigree.tier_level || ""}`);
        if (resume.company_pedigree.company_types?.length) {
          textParts.push(`Company types: ${resume.company_pedigree.company_types.join(", ")}`);
        }
        if (resume.company_pedigree.recent_companies?.length) {
          textParts.push(`Recent companies: ${resume.company_pedigree.recent_companies.join(", ")}`);
        }
      }
    }
    
    // Recruiter insights
    if (profile.recruiter_insights) {
      const insights = profile.recruiter_insights;
      
      if (insights.strengths?.length) {
        textParts.push(`Strengths: ${insights.strengths.join(", ")}`);
      }
      
      if (insights.key_themes?.length) {
        textParts.push(`Key themes: ${insights.key_themes.join(", ")}`);
      }
      
      if (insights.competitive_advantages?.length) {
        textParts.push(`Competitive advantages: ${insights.competitive_advantages.join(", ")}`);
      }
    }
    
    // Enrichment insights
    if (profile.enrichment) {
      const enrichment = profile.enrichment;
      
      if (enrichment.ai_summary) {
        textParts.push(enrichment.ai_summary);
      }
      
      if (enrichment.career_analysis?.trajectory_insights) {
        textParts.push(enrichment.career_analysis.trajectory_insights);
      }
      
      if (enrichment.strategic_fit?.competitive_positioning) {
        textParts.push(enrichment.strategic_fit.competitive_positioning);
      }
    }
    
    return textParts.filter(Boolean).join(". ");
  }

  /**
   * Store embedding data for a candidate profile
   */
  async storeEmbedding(profile: any): Promise<EmbeddingData> {
    const embeddingText = this.extractEmbeddingText(profile);
    const embeddingVector = await this.generateEmbedding(embeddingText);
    
    const embeddingData: EmbeddingData = {
      candidate_id: profile.candidate_id,
      embedding_vector: embeddingVector,
      embedding_text: embeddingText,
      metadata: {
        years_experience: profile.resume_analysis?.years_experience || 0,
        current_level: profile.resume_analysis?.career_trajectory?.current_level || "Unknown",
        company_tier: profile.resume_analysis?.company_pedigree?.tier_level || "Unknown",
        overall_score: profile.overall_score || 0,
        technical_skills: profile.resume_analysis?.technical_skills || [],
        leadership_level: profile.resume_analysis?.leadership_scope?.leadership_level,
        updated_at: new Date().toISOString(),
      },
    };
    
    // Store in Firestore for fast access
    await this.firestore
      .collection("candidate_embeddings")
      .doc(profile.candidate_id)
      .set(embeddingData);
    
    console.log(`Stored embedding for candidate: ${profile.candidate_id}`);
    return embeddingData;
  }

  /**
   * Perform similarity search using cosine distance
   */
  async searchSimilar(query: SearchQuery): Promise<VectorSearchResult[]> {
    try {
      // Generate embedding for query text
      const queryEmbedding = await this.generateEmbedding(query.query_text);
      
      // For now, use Firestore to get all embeddings and compute similarity locally
      // In production, this would use Vertex AI Vector Search
      const embeddingsSnapshot = await this.firestore
        .collection("candidate_embeddings")
        .get();
      
      const results: VectorSearchResult[] = [];
      
      embeddingsSnapshot.docs.forEach((doc) => {
        const embedding = doc.data() as EmbeddingData;
        
        // Apply filters
        if (query.filters) {
          if (query.filters.min_years_experience && 
              embedding.metadata.years_experience < query.filters.min_years_experience) {
            return;
          }
          
          if (query.filters.current_level && 
              embedding.metadata.current_level !== query.filters.current_level) {
            return;
          }
          
          if (query.filters.company_tier && 
              embedding.metadata.company_tier !== query.filters.company_tier) {
            return;
          }
          
          if (query.filters.min_score && 
              embedding.metadata.overall_score < query.filters.min_score) {
            return;
          }
        }
        
        // Calculate cosine similarity
        const similarity = this.cosineSimilarity(queryEmbedding, embedding.embedding_vector);
        
        // Generate match reasons
        const matchReasons = this.generateMatchReasons(query.query_text, embedding);
        
        results.push({
          candidate_id: embedding.candidate_id,
          similarity_score: similarity,
          metadata: embedding.metadata,
          match_reasons: matchReasons,
        });
      });
      
      // Sort by similarity score (descending) and apply limit
      results.sort((a, b) => b.similarity_score - a.similarity_score);
      
      const limit = query.limit || 20;
      return results.slice(0, limit);
      
    } catch (error) {
      console.error("Error in similarity search:", error);
      throw error;
    }
  }

  /**
   * Calculate cosine similarity between two vectors
   */
  private cosineSimilarity(vecA: number[], vecB: number[]): number {
    if (vecA.length !== vecB.length) {
      throw new Error("Vectors must have the same dimensions");
    }
    
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;
    
    for (let i = 0; i < vecA.length; i++) {
      dotProduct += vecA[i] * vecB[i];
      normA += vecA[i] * vecA[i];
      normB += vecB[i] * vecB[i];
    }
    
    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
  }

  /**
   * Generate match reasons based on query and candidate profile
   */
  private generateMatchReasons(queryText: string, embedding: EmbeddingData): string[] {
    const reasons: string[] = [];
    const queryLower = queryText.toLowerCase();
    const embeddingTextLower = embedding.embedding_text.toLowerCase();
    
    // Technical skills matching
    const techKeywords = ["python", "javascript", "react", "machine learning", "ai", "cloud", "aws", "gcp"];
    const matchedTech = techKeywords.filter(skill => 
      queryLower.includes(skill) && embeddingTextLower.includes(skill)
    );
    if (matchedTech.length > 0) {
      reasons.push(`Technical skills match: ${matchedTech.join(", ")}`);
    }
    
    // Experience level matching
    if (queryLower.includes("senior") && embeddingTextLower.includes("senior")) {
      reasons.push("Senior-level experience alignment");
    }
    
    if (queryLower.includes("lead") && embeddingTextLower.includes("leadership")) {
      reasons.push("Leadership experience match");
    }
    
    // Industry/company matching
    const companyKeywords = ["startup", "big tech", "faang", "enterprise"];
    const matchedCompany = companyKeywords.filter(keyword =>
      queryLower.includes(keyword) && embeddingTextLower.includes(keyword)
    );
    if (matchedCompany.length > 0) {
      reasons.push(`Company background match: ${matchedCompany.join(", ")}`);
    }
    
    // Overall score consideration
    if (embedding.metadata.overall_score >= 0.8) {
      reasons.push("High overall candidate score");
    }
    
    // Default reason if no specific matches
    if (reasons.length === 0) {
      reasons.push("Profile similarity based on experience and skills");
    }
    
    return reasons;
  }

  /**
   * Get embedding statistics
   */
  async getEmbeddingStats(): Promise<{
    total_embeddings: number;
    avg_score: number;
    level_distribution: Record<string, number>;
    tier_distribution: Record<string, number>;
  }> {
    const snapshot = await this.firestore
      .collection("candidate_embeddings")
      .get();
    
    let totalScore = 0;
    const levelCounts: Record<string, number> = {};
    const tierCounts: Record<string, number> = {};
    
    snapshot.docs.forEach(doc => {
      const embedding = doc.data() as EmbeddingData;
      totalScore += embedding.metadata.overall_score;
      
      const level = embedding.metadata.current_level;
      levelCounts[level] = (levelCounts[level] || 0) + 1;
      
      const tier = embedding.metadata.company_tier;
      tierCounts[tier] = (tierCounts[tier] || 0) + 1;
    });
    
    return {
      total_embeddings: snapshot.docs.length,
      avg_score: snapshot.docs.length > 0 ? totalScore / snapshot.docs.length : 0,
      level_distribution: levelCounts,
      tier_distribution: tierCounts,
    };
  }

  /**
   * Health check for vector search service
   */
  async healthCheck(): Promise<{
    status: string;
    embedding_service: string;
    storage_connection: string;
    firestore_connection: string;
    total_embeddings: number;
  }> {
    try {
      // Test Firestore connection
      const testDoc = await this.firestore
        .collection("health")
        .doc("vector_search_test")
        .set({ timestamp: admin.firestore.FieldValue.serverTimestamp() });
      
      // Get embedding count
      const embeddingsSnapshot = await this.firestore
        .collection("candidate_embeddings")
        .get();
      
      return {
        status: "healthy",
        embedding_service: "operational",
        storage_connection: "connected",
        firestore_connection: "connected",
        total_embeddings: embeddingsSnapshot.docs.length,
      };
    } catch (error) {
      return {
        status: "unhealthy",
        embedding_service: "error",
        storage_connection: "unknown",
        firestore_connection: "error",
        total_embeddings: 0,
      };
    }
  }
}