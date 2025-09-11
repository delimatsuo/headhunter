/**
 * Vector Search functionality for candidate profile similarity matching
 */

// import { MatchServiceClient } from "@google-cloud/aiplatform";
// import { Storage } from "@google-cloud/storage";
import * as admin from "firebase-admin";
import { getEmbeddingProvider } from "./embedding-provider";
import { getPgVectorClient, PgVectorClient } from "./pgvector-client";

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
  org_id?: string;
}

interface SkillAwareSearchQuery {
  text_query: string;
  required_skills?: Array<{
    skill: string;
    minimum_confidence?: number;
    weight?: number;
    category?: string;
  }>;
  preferred_skills?: Array<{
    skill: string;
    minimum_confidence?: number;
    weight?: number;
    category?: string;
  }>;
  experience_level?: 'entry' | 'mid' | 'senior' | 'executive';
  minimum_overall_confidence?: number;
  filters?: {
    min_years_experience?: number;
    current_level?: string;
    company_tier?: string;
    min_score?: number;
    location?: string;
  };
  limit?: number;
  ranking_weights?: {
    skill_match?: number;
    confidence?: number;
    vector_similarity?: number;
    experience_match?: number;
  };
  org_id?: string;
}

interface SkillAwareSearchResult {
  candidate_id: string;
  overall_score: number;
  skill_match_score: number;
  confidence_score: number;
  vector_similarity_score: number;
  experience_match_score: number;
  skill_breakdown: Record<string, number>;
  ranking_factors: {
    required_skills_matched: number;
    total_required_skills: number;
    preferred_skills_matched: number;
    total_preferred_skills: number;
    average_skill_confidence: number;
    experience_alignment: string;
    vector_similarity: number;
  };
  metadata: EmbeddingData["metadata"];
  match_reasons: string[];
}

export class VectorSearchService {
  // private matchClient: MatchServiceClient;
  // private storage: Storage;
  private firestore: admin.firestore.Firestore;
  private pgVectorClient: PgVectorClient | null = null;
  private usePgVector: boolean;
  // private indexEndpoint: string;
  // private deployedIndexId: string;

  constructor() {
    // this.matchClient = new MatchServiceClient({
    //   apiEndpoint: "us-central1-aiplatform.googleapis.com",
    // });
    // this.storage = new Storage();
    this.firestore = admin.firestore();
    
    // Feature flag for gradual migration to pgvector
    this.usePgVector = process.env.USE_PGVECTOR === 'true';
    
    // Project and region can be provided via environment to the provider if needed
    
    // These will need to be configured after Vector Search setup
    // this.indexEndpoint = `projects/${this.projectId}/locations/${this.region}/indexEndpoints/ENDPOINT_ID`;
    // this.deployedIndexId = "DEPLOYED_INDEX_ID";
  }

  /**
   * Initialize pgvector client if needed
   */
  private async initializePgVectorClient(): Promise<void> {
    if (this.usePgVector && !this.pgVectorClient) {
      this.pgVectorClient = await getPgVectorClient();
    }
  }

  /**
   * Generate text embeddings using Vertex AI
   */
  async generateEmbedding(text: string): Promise<number[]> {
    const provider = getEmbeddingProvider();
    return provider.generateEmbedding(text);
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
    
    if (this.usePgVector) {
      // Use pgvector for storage
      await this.initializePgVectorClient();
      if (this.pgVectorClient) {
        await this.pgVectorClient.storeEmbedding(
          profile.candidate_id,
          embeddingVector,
          'vertex-ai-textembedding-004',
          'full_profile',
          embeddingData.metadata
        );
        console.log(`Stored embedding in pgvector for candidate: ${profile.candidate_id}`);
      }
    } else {
      // Store in Firestore for fast access (legacy behavior)
      await this.firestore
        .collection("candidate_embeddings")
        .doc(profile.candidate_id)
        .set(embeddingData);
      console.log(`Stored embedding in Firestore for candidate: ${profile.candidate_id}`);
    }
    
    return embeddingData;
  }

  /**
   * Search candidates using semantic similarity
   */
  async searchCandidates(query: SearchQuery): Promise<VectorSearchResult[]> {
    try {
      // Generate embedding for query text
      const queryEmbedding = await this.generateEmbedding(query.query_text);
      
      if (this.usePgVector) {
        // Use pgvector for optimized similarity search
        await this.initializePgVectorClient();
        if (this.pgVectorClient) {
          const similarityThreshold = 0.7; // Default threshold
          const limit = query.limit || 20;
          
          const pgResults = await this.pgVectorClient.searchSimilar(
            queryEmbedding,
            similarityThreshold,
            limit,
            'vertex-ai-textembedding-004',
            'full_profile'
          );
          
          // Convert pgvector results to VectorSearchResult format
          const results: VectorSearchResult[] = [];
          
          for (const pgResult of pgResults) {
            // Apply additional filters
            if (query.filters?.min_years_experience && 
                pgResult.metadata.years_experience < query.filters.min_years_experience) {
              continue;
            }
            
            if (query.filters?.current_level && 
                pgResult.metadata.current_level !== query.filters.current_level) {
              continue;
            }
            
            if (query.filters?.company_tier && 
                pgResult.metadata.company_tier !== query.filters.company_tier) {
              continue;
            }
            
            if (query.filters?.min_score && 
                pgResult.metadata.overall_score < query.filters.min_score) {
              continue;
            }
            
            // Organization filter - check if candidate belongs to the requested org
            if (query.org_id) {
              const candidateDoc = await this.firestore
                .collection('candidates')
                .doc(pgResult.candidate_id)
                .get();
              
              if (!candidateDoc.exists || candidateDoc.data()?.org_id !== query.org_id) {
                continue;
              }
            }
            
            // Generate match reasons based on metadata
            const embeddingData: EmbeddingData = {
              candidate_id: pgResult.candidate_id,
              embedding_vector: [], // Not needed for match reasons
              embedding_text: '',   // Not needed for match reasons
              metadata: {
                years_experience: pgResult.metadata.years_experience || 0,
                current_level: pgResult.metadata.current_level || "Unknown",
                company_tier: pgResult.metadata.company_tier || "Unknown",
                overall_score: pgResult.metadata.overall_score || 0,
                technical_skills: pgResult.metadata.technical_skills || [],
                leadership_level: pgResult.metadata.leadership_level,
                updated_at: pgResult.metadata.updated_at || new Date().toISOString(),
              }
            };
            const matchReasons = this.generateMatchReasons(embeddingData, pgResult.similarity);
            
            results.push({
              candidate_id: pgResult.candidate_id,
              similarity_score: pgResult.similarity,
              metadata: embeddingData.metadata,
              match_reasons: matchReasons
            });
          }
          
          return results.slice(0, limit);
        }
      }
      
      // Fallback to Firestore-based search (legacy behavior)
      return this.searchCandidatesFirestore(query, queryEmbedding);
      
    } catch (error) {
      console.error("Error in searchCandidates:", error);
      throw error;
    }
  }

  /**
   * Legacy Firestore-based search for backward compatibility
   */
  private async searchCandidatesFirestore(query: SearchQuery, queryEmbedding: number[]): Promise<VectorSearchResult[]> {
    // Get all embeddings from Firestore with organization filter
    let embeddingsQuery = this.firestore.collection("candidate_embeddings");
    
    if (query.org_id) {
      // We need to join with candidates collection to filter by org_id
      // For now, get all embeddings and filter in memory
    }
    
    const snapshot = await embeddingsQuery.get();
    const embeddings: EmbeddingData[] = [];
    
    for (const doc of snapshot.docs) {
      const data = doc.data() as EmbeddingData;
      
      // If org_id filter is provided, check candidate's organization
      if (query.org_id) {
        const candidateDoc = await this.firestore
          .collection('candidates')
          .doc(data.candidate_id)
          .get();
        
        if (!candidateDoc.exists || candidateDoc.data()?.org_id !== query.org_id) {
          continue;
        }
      }
      
      embeddings.push(data);
    }
    
    // Calculate similarity scores
    const results: VectorSearchResult[] = [];
    
    for (const embedding of embeddings) {
      // Apply filters
      if (query.filters?.min_years_experience && 
          embedding.metadata.years_experience < query.filters.min_years_experience) {
        continue;
      }
      
      if (query.filters?.current_level && 
          embedding.metadata.current_level !== query.filters.current_level) {
        continue;
      }
      
      if (query.filters?.company_tier && 
          embedding.metadata.company_tier !== query.filters.company_tier) {
        continue;
      }
      
      if (query.filters?.min_score && 
          embedding.metadata.overall_score < query.filters.min_score) {
        continue;
      }
      
      // Calculate cosine similarity
      const similarity = this.calculateCosineSimilarity(queryEmbedding, embedding.embedding_vector);
      
      // Generate match reasons
      const matchReasons = this.generateMatchReasons(embedding, similarity);
      
      results.push({
        candidate_id: embedding.candidate_id,
        similarity_score: similarity,
        metadata: embedding.metadata,
        match_reasons: matchReasons
      });
    }
    
    // Sort by similarity score and apply limit
    results.sort((a, b) => b.similarity_score - a.similarity_score);
    
    const limit = query.limit || 20;
    return results.slice(0, limit);
  }

  /**
   * Find candidates similar to a reference candidate
   */
  async findSimilarCandidates(candidateId: string, options: { 
    limit?: number; 
    org_id?: string; 
  } = {}): Promise<VectorSearchResult[]> {
    try {
      // Get the reference candidate's embedding
      const embeddingDoc = await this.firestore
        .collection("candidate_embeddings")
        .doc(candidateId)
        .get();
      
      if (!embeddingDoc.exists) {
        throw new Error(`Embedding not found for candidate: ${candidateId}`);
      }
      
      const referenceEmbedding = embeddingDoc.data() as EmbeddingData;
      
      // Search for similar candidates using the reference embedding
      const query: SearchQuery = {
        query_text: referenceEmbedding.embedding_text,
        limit: (options.limit || 10) + 1, // +1 to exclude the reference candidate
        org_id: options.org_id
      };
      
      const results = await this.searchCandidates(query);
      
      // Remove the reference candidate from results
      const filteredResults = results.filter(result => result.candidate_id !== candidateId);
      
      // Return up to the requested limit
      return filteredResults.slice(0, options.limit || 10);
      
    } catch (error) {
      console.error("Error in findSimilarCandidates:", error);
      throw error;
    }
  }

  /**
   * Perform similarity search using cosine distance (legacy method)
   */
  async searchSimilar(query: SearchQuery): Promise<VectorSearchResult[]> {
    // Delegate to the new searchCandidates method for backward compatibility
    return this.searchCandidates(query);
  }

  /**
   * Skill-aware search with confidence scoring and intelligent ranking
   */
  async searchCandidatesSkillAware(query: SkillAwareSearchQuery): Promise<SkillAwareSearchResult[]> {
    try {
      // First, perform traditional vector similarity search
      const traditionalQuery: SearchQuery = {
        query_text: query.text_query,
        filters: query.filters,
        limit: (query.limit || 20) * 2, // Get more results for re-ranking
        org_id: query.org_id
      };

      const vectorResults = await this.searchCandidates(traditionalQuery);
      
      // Get detailed candidate data including skill assessments
      const enrichedResults: SkillAwareSearchResult[] = [];
      
      for (const vectorResult of vectorResults) {
        // Fetch full candidate profile with skill assessments
        const candidateDoc = await this.firestore
          .collection('candidates')
          .doc(vectorResult.candidate_id)
          .get();
          
        if (!candidateDoc.exists) {
          continue;
        }
        
        const candidateData = candidateDoc.data();
        
        // Calculate skill-aware scores
        const skillScores = this.calculateSkillAwareScores(candidateData, query);
        
        // Apply minimum confidence filter
        if (query.minimum_overall_confidence && 
            skillScores.confidence_score < query.minimum_overall_confidence) {
          continue;
        }
        
        // Calculate composite ranking score
        const overallScore = this.calculateCompositeRankingScore(
          skillScores, 
          vectorResult.similarity_score, 
          query.ranking_weights || {}
        );
        
        // Generate enhanced match reasons
        const matchReasons = this.generateSkillAwareMatchReasons(
          candidateData, 
          vectorResult, 
          skillScores,
          query
        );
        
        enrichedResults.push({
          candidate_id: vectorResult.candidate_id,
          overall_score: overallScore,
          skill_match_score: skillScores.skill_match_score,
          confidence_score: skillScores.confidence_score,
          vector_similarity_score: vectorResult.similarity_score * 100,
          experience_match_score: skillScores.experience_match_score,
          skill_breakdown: skillScores.skill_breakdown,
          ranking_factors: skillScores.ranking_factors,
          metadata: vectorResult.metadata,
          match_reasons: matchReasons
        });
      }
      
      // Sort by overall score and return top results
      enrichedResults.sort((a, b) => b.overall_score - a.overall_score);
      
      return enrichedResults.slice(0, query.limit || 20);
      
    } catch (error) {
      console.error("Error in searchCandidatesSkillAware:", error);
      throw error;
    }
  }

  /**
   * Calculate skill-aware scoring for a candidate
   */
  private calculateSkillAwareScores(candidateData: any, query: SkillAwareSearchQuery): {
    skill_match_score: number;
    confidence_score: number;
    experience_match_score: number;
    skill_breakdown: Record<string, number>;
    ranking_factors: SkillAwareSearchResult['ranking_factors'];
  } {
    const candidateSkills = this.extractCandidateSkills(candidateData);
    const requiredSkills = query.required_skills || [];
    const preferredSkills = query.preferred_skills || [];
    
    // Calculate required skills match
    let requiredSkillsMatched = 0;
    let totalRequiredWeight = 0;
    let weightedRequiredScore = 0;
    const skillBreakdown: Record<string, number> = {};
    
    for (const requiredSkill of requiredSkills) {
      const weight = requiredSkill.weight || 1.0;
      totalRequiredWeight += weight;
      
      const candidateSkill = this.findMatchingSkill(candidateSkills, requiredSkill.skill);
      
      if (candidateSkill) {
        const confidence = candidateSkill.confidence;
        const meetsMinimum = confidence >= (requiredSkill.minimum_confidence || 70);
        
        if (meetsMinimum) {
          requiredSkillsMatched++;
          weightedRequiredScore += confidence * weight;
          skillBreakdown[requiredSkill.skill] = confidence;
        } else {
          skillBreakdown[requiredSkill.skill] = confidence * 0.5; // Partial credit
          weightedRequiredScore += confidence * 0.5 * weight;
        }
      } else {
        skillBreakdown[requiredSkill.skill] = 0;
      }
    }
    
    // Calculate preferred skills match  
    let preferredSkillsMatched = 0;
    let totalPreferredWeight = 0;
    let weightedPreferredScore = 0;
    
    for (const preferredSkill of preferredSkills) {
      const weight = preferredSkill.weight || 0.5;
      totalPreferredWeight += weight;
      
      const candidateSkill = this.findMatchingSkill(candidateSkills, preferredSkill.skill);
      
      if (candidateSkill && candidateSkill.confidence >= (preferredSkill.minimum_confidence || 60)) {
        preferredSkillsMatched++;
        weightedPreferredScore += candidateSkill.confidence * weight;
        skillBreakdown[preferredSkill.skill] = candidateSkill.confidence;
      } else if (candidateSkill) {
        skillBreakdown[preferredSkill.skill] = candidateSkill.confidence;
        weightedPreferredScore += candidateSkill.confidence * 0.3 * weight; // Partial credit
      } else {
        skillBreakdown[preferredSkill.skill] = 0;
      }
    }
    
    // Calculate overall skill match score
    const totalWeight = totalRequiredWeight + totalPreferredWeight;
    const skillMatchScore = totalWeight > 0 
      ? ((weightedRequiredScore + weightedPreferredScore) / totalWeight)
      : 0;
    
    // Calculate average confidence across all candidate skills
    const allConfidences = candidateSkills.map(s => s.confidence);
    const averageConfidence = allConfidences.length > 0 
      ? allConfidences.reduce((sum, conf) => sum + conf, 0) / allConfidences.length
      : 0;
    
    // Calculate experience match score
    const experienceMatchScore = this.calculateExperienceMatch(candidateData, query);
    
    return {
      skill_match_score: skillMatchScore,
      confidence_score: averageConfidence,
      experience_match_score: experienceMatchScore,
      skill_breakdown: skillBreakdown,
      ranking_factors: {
        required_skills_matched: requiredSkillsMatched,
        total_required_skills: requiredSkills.length,
        preferred_skills_matched: preferredSkillsMatched,
        total_preferred_skills: preferredSkills.length,
        average_skill_confidence: averageConfidence,
        experience_alignment: this.getExperienceAlignment(candidateData, query),
        vector_similarity: 0 // Will be set later
      }
    };
  }

  /**
   * Extract skills from candidate data with confidence scores
   */
  private extractCandidateSkills(candidateData: any): Array<{skill: string, confidence: number, source: string, category: string}> {
    const skills: Array<{skill: string, confidence: number, source: string, category: string}> = [];
    
    // Check for intelligent analysis first (new skill assessment format)
    if (candidateData.intelligent_analysis) {
      const analysis = candidateData.intelligent_analysis;
      
      // Extract explicit skills
      if (analysis.explicit_skills) {
        const explicitSkills = analysis.explicit_skills;
        
        // Technical skills
        if (explicitSkills.technical_skills) {
          for (const skillItem of explicitSkills.technical_skills) {
            const skill = typeof skillItem === 'string' ? skillItem : skillItem.skill;
            const confidence = typeof skillItem === 'object' ? skillItem.confidence || 100 : 100;
            skills.push({
              skill: skill.toLowerCase(),
              confidence,
              source: 'explicit',
              category: 'technical'
            });
          }
        }
        
        // Tools and technologies
        if (explicitSkills.tools_technologies) {
          for (const skillItem of explicitSkills.tools_technologies) {
            const skill = typeof skillItem === 'string' ? skillItem : skillItem.skill;
            const confidence = typeof skillItem === 'object' ? skillItem.confidence || 100 : 100;
            skills.push({
              skill: skill.toLowerCase(),
              confidence,
              source: 'explicit',
              category: 'technical'
            });
          }
        }
        
        // Soft skills
        if (explicitSkills.soft_skills) {
          for (const skillItem of explicitSkills.soft_skills) {
            const skill = typeof skillItem === 'string' ? skillItem : skillItem.skill;
            const confidence = typeof skillItem === 'object' ? skillItem.confidence || 100 : 100;
            skills.push({
              skill: skill.toLowerCase(),
              confidence,
              source: 'explicit',
              category: 'soft'
            });
          }
        }
      }
      
      // Extract inferred skills
      if (analysis.inferred_skills) {
        const inferred = analysis.inferred_skills;
        
        // Highly probable skills
        if (inferred.highly_probable_skills) {
          for (const skillItem of inferred.highly_probable_skills) {
            skills.push({
              skill: skillItem.skill.toLowerCase(),
              confidence: skillItem.confidence || 85,
              source: 'inferred',
              category: skillItem.skill_category || 'technical'
            });
          }
        }
        
        // Probable skills
        if (inferred.probable_skills) {
          for (const skillItem of inferred.probable_skills) {
            skills.push({
              skill: skillItem.skill.toLowerCase(),
              confidence: skillItem.confidence || 75,
              source: 'inferred',
              category: skillItem.skill_category || 'technical'
            });
          }
        }
        
        // Likely skills  
        if (inferred.likely_skills) {
          for (const skillItem of inferred.likely_skills) {
            skills.push({
              skill: skillItem.skill.toLowerCase(),
              confidence: skillItem.confidence || 65,
              source: 'inferred',
              category: skillItem.skill_category || 'technical'
            });
          }
        }
      }
    }
    
    // Fallback to basic resume analysis format
    if (skills.length === 0 && candidateData.resume_analysis) {
      const resume = candidateData.resume_analysis;
      
      // Technical skills (100% confidence for explicitly listed)
      if (resume.technical_skills) {
        for (const skill of resume.technical_skills) {
          skills.push({
            skill: skill.toLowerCase(),
            confidence: 90, // High confidence for resume-listed skills
            source: 'explicit',
            category: 'technical'
          });
        }
      }
      
      // Soft skills
      if (resume.soft_skills) {
        for (const skill of resume.soft_skills) {
          skills.push({
            skill: skill.toLowerCase(),
            confidence: 85,
            source: 'explicit',
            category: 'soft'
          });
        }
      }
    }
    
    return skills;
  }

  /**
   * Find matching skill with fuzzy matching
   */
  private findMatchingSkill(candidateSkills: Array<{skill: string, confidence: number, source: string, category: string}>, targetSkill: string): {skill: string, confidence: number} | null {
    const target = targetSkill.toLowerCase();
    
    // Exact match first
    const exactMatch = candidateSkills.find(s => s.skill === target);
    if (exactMatch) {
      return { skill: exactMatch.skill, confidence: exactMatch.confidence };
    }
    
    // Partial match (skill contains target or vice versa)
    const partialMatch = candidateSkills.find(s => 
      s.skill.includes(target) || target.includes(s.skill)
    );
    if (partialMatch) {
      return { 
        skill: partialMatch.skill, 
        confidence: partialMatch.confidence * 0.8 // Penalty for partial match
      };
    }
    
    // Synonym matching (basic)
    const synonyms: Record<string, string[]> = {
      'javascript': ['js', 'ecmascript', 'node.js', 'nodejs'],
      'python': ['py', 'python3'],
      'kubernetes': ['k8s'],
      'docker': ['containerization', 'containers'],
      'aws': ['amazon web services'],
      'machine learning': ['ml', 'ai', 'artificial intelligence']
    };
    
    for (const [canonical, alts] of Object.entries(synonyms)) {
      if (target === canonical || alts.includes(target)) {
        const synonymMatch = candidateSkills.find(s => 
          s.skill === canonical || alts.includes(s.skill)
        );
        if (synonymMatch) {
          return { skill: synonymMatch.skill, confidence: synonymMatch.confidence };
        }
      }
    }
    
    return null;
  }

  /**
   * Calculate experience level match score
   */
  private calculateExperienceMatch(candidateData: any, query: SkillAwareSearchQuery): number {
    if (!query.experience_level) {
      return 100; // No preference specified
    }
    
    const candidateYears = candidateData.resume_analysis?.years_experience || 0;
    const candidateLevel = candidateData.resume_analysis?.career_trajectory?.current_level?.toLowerCase() || '';
    
    const experienceLevels: Record<string, {minYears: number, maxYears: number, keywords: string[]}> = {
      'entry': { minYears: 0, maxYears: 3, keywords: ['junior', 'entry', 'associate'] },
      'mid': { minYears: 2, maxYears: 7, keywords: ['mid', 'intermediate', 'regular'] },
      'senior': { minYears: 5, maxYears: 12, keywords: ['senior', 'sr', 'lead'] },
      'executive': { minYears: 8, maxYears: 50, keywords: ['principal', 'staff', 'director', 'vp', 'executive', 'head'] }
    };
    
    const targetLevel = experienceLevels[query.experience_level];
    if (!targetLevel) {
      return 100;
    }
    
    let score = 0;
    
    // Years experience match
    if (candidateYears >= targetLevel.minYears && candidateYears <= targetLevel.maxYears) {
      score += 60;
    } else if (candidateYears >= targetLevel.minYears - 1 && candidateYears <= targetLevel.maxYears + 2) {
      score += 40; // Close match
    } else {
      score += 20; // Some experience
    }
    
    // Level keyword match
    const levelKeywordMatch = targetLevel.keywords.some(keyword => 
      candidateLevel.includes(keyword)
    );
    if (levelKeywordMatch) {
      score += 40;
    }
    
    return Math.min(score, 100);
  }

  /**
   * Get experience alignment description
   */
  private getExperienceAlignment(candidateData: any, query: SkillAwareSearchQuery): string {
    const experienceScore = this.calculateExperienceMatch(candidateData, query);
    
    if (experienceScore >= 90) return 'excellent';
    if (experienceScore >= 70) return 'good';
    if (experienceScore >= 50) return 'fair';
    return 'limited';
  }

  /**
   * Calculate composite ranking score using weighted factors
   */
  private calculateCompositeRankingScore(
    skillScores: any, 
    vectorSimilarity: number, 
    weights: SkillAwareSearchQuery['ranking_weights']
  ): number {
    const defaultWeights = {
      skill_match: 0.4,
      confidence: 0.25,
      vector_similarity: 0.25,
      experience_match: 0.1
    };
    
    const finalWeights = { ...defaultWeights, ...weights };
    
    const score = 
      (skillScores.skill_match_score * finalWeights.skill_match) +
      (skillScores.confidence_score * finalWeights.confidence) +
      (vectorSimilarity * 100 * finalWeights.vector_similarity) +
      (skillScores.experience_match_score * finalWeights.experience_match);
    
    return Math.round(score * 100) / 100; // Round to 2 decimal places
  }

  /**
   * Generate enhanced match reasons for skill-aware search
   */
  private generateSkillAwareMatchReasons(
    candidateData: any,
    vectorResult: VectorSearchResult,
    skillScores: any,
    query: SkillAwareSearchQuery
  ): string[] {
    const reasons: string[] = [];
    
    // Overall match quality
    if (skillScores.skill_match_score >= 90) {
      reasons.push("Exceptional skill match");
    } else if (skillScores.skill_match_score >= 80) {
      reasons.push("Strong skill alignment");
    } else if (skillScores.skill_match_score >= 70) {
      reasons.push("Good skill match");
    }
    
    // Required skills
    const requiredMatched = skillScores.ranking_factors.required_skills_matched;
    const totalRequired = skillScores.ranking_factors.total_required_skills;
    if (totalRequired > 0) {
      if (requiredMatched === totalRequired) {
        reasons.push(`Has all ${totalRequired} required skills`);
      } else if (requiredMatched > 0) {
        reasons.push(`Has ${requiredMatched}/${totalRequired} required skills`);
      }
    }
    
    // High confidence skills
    const highConfidenceSkills = Object.entries(skillScores.skill_breakdown)
      .filter(([_, confidence]) => (confidence as number) >= 90)
      .map(([skill]) => skill);
    
    if (highConfidenceSkills.length > 0) {
      reasons.push(`Expert level: ${highConfidenceSkills.slice(0, 3).join(", ")}`);
    }
    
    // Experience alignment
    const expAlignment = skillScores.ranking_factors.experience_alignment;
    if (expAlignment === 'excellent') {
      reasons.push("Perfect experience level match");
    } else if (expAlignment === 'good') {
      reasons.push("Good experience level match");
    }
    
    // Vector similarity context
    if (vectorResult.similarity_score > 0.85) {
      reasons.push("Excellent profile similarity");
    } else if (vectorResult.similarity_score > 0.75) {
      reasons.push("Strong profile match");
    }
    
    return reasons;
  }

  /**
   * Calculate cosine similarity between two vectors
   */
  private calculateCosineSimilarity(vectorA: number[], vectorB: number[]): number {
    if (vectorA.length !== vectorB.length) {
      throw new Error("Vector dimensions must match");
    }
    
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;
    
    for (let i = 0; i < vectorA.length; i++) {
      dotProduct += vectorA[i] * vectorB[i];
      normA += vectorA[i] * vectorA[i];
      normB += vectorB[i] * vectorB[i];
    }
    
    normA = Math.sqrt(normA);
    normB = Math.sqrt(normB);
    
    if (normA === 0 || normB === 0) {
      return 0;
    }
    
    return dotProduct / (normA * normB);
  }

  /**
   * Generate match reasons based on embedding metadata and similarity
   */
  private generateMatchReasons(embedding: EmbeddingData, similarity: number): string[] {
    const reasons: string[] = [];
    
    if (similarity > 0.9) {
      reasons.push("Excellent overall match");
    } else if (similarity > 0.8) {
      reasons.push("Strong overall alignment");
    } else if (similarity > 0.7) {
      reasons.push("Good profile match");
    }
    
    if (embedding.metadata.technical_skills && embedding.metadata.technical_skills.length > 0) {
      reasons.push(`Technical skills: ${embedding.metadata.technical_skills.slice(0, 3).join(", ")}`);
    }
    
    if (embedding.metadata.years_experience > 5) {
      reasons.push(`${embedding.metadata.years_experience} years experience`);
    }
    
    if (embedding.metadata.leadership_level) {
      reasons.push(`Leadership: ${embedding.metadata.leadership_level}`);
    }
    
    if (embedding.metadata.company_tier && embedding.metadata.company_tier !== "Unknown") {
      reasons.push(`${embedding.metadata.company_tier} company background`);
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
    pgvector_connection?: string;
    pgvector_enabled: boolean;
    total_embeddings: number;
  }> {
    try {
      let pgvectorStatus = "not_enabled";
      let totalEmbeddings = 0;
      
      if (this.usePgVector) {
        // Test pgvector connection
        try {
          await this.initializePgVectorClient();
          if (this.pgVectorClient) {
            const pgHealth = await this.pgVectorClient.healthCheck();
            pgvectorStatus = pgHealth.status === "healthy" ? "connected" : "error";
            totalEmbeddings = pgHealth.total_embeddings || 0;
          }
        } catch (error) {
          pgvectorStatus = "error";
        }
      } else {
        // Test Firestore connection for legacy mode
        await this.firestore
          .collection("health")
          .doc("vector_search_test")
          .set({ timestamp: new Date().toISOString() });
        
        // Get embedding count from Firestore
        const embeddingsSnapshot = await this.firestore
          .collection("candidate_embeddings")
          .get();
        totalEmbeddings = embeddingsSnapshot.docs.length;
      }
      
      return {
        status: "healthy",
        embedding_service: "operational",
        storage_connection: "connected",
        firestore_connection: "connected",
        pgvector_connection: this.usePgVector ? pgvectorStatus : undefined,
        pgvector_enabled: this.usePgVector,
        total_embeddings: totalEmbeddings,
      };
    } catch (error) {
      return {
        status: "unhealthy",
        embedding_service: "error",
        storage_connection: "unknown",
        firestore_connection: "error",
        pgvector_connection: this.usePgVector ? "error" : undefined,
        pgvector_enabled: this.usePgVector,
        total_embeddings: 0,
      };
    }
  }
}
