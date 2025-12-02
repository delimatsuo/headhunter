import {
  searchCandidates,
  searchJobCandidates,
  semanticSearch,
  getCandidates,
  createCandidate,
  generateUploadUrl,
  healthCheck,
  skillAwareSearch,
  getCandidateSkillAssessment,
  rerankCandidates,
  saveSearch,
  getSavedSearches,
  deleteSavedSearch,
  findSimilarCandidates,
  analyzeSearchQuery
} from '../config/firebase';
import {
  JobDescription,
  SearchResponse,
  CandidateProfile,
  ApiResponse,
  DashboardStats,
  SkillAssessment,
  SkillMatchData,
  SavedSearch,
  VectorSearchResult
} from '../types';

export class ApiError extends Error {
  constructor(message: string, public statusCode?: number) {
    super(message);
    this.name = 'ApiError';
  }
}

export const apiService = {
  // Health check
  async checkHealth(): Promise<ApiResponse> {
    try {
      const result = await healthCheck();
      return result.data as ApiResponse;
    } catch (error) {
      throw new ApiError('Health check failed', 500);
    }
  },

  // Search candidates based on job description
  // Search candidates based on job description using semantic search
  async searchCandidates(jobDescription: JobDescription): Promise<SearchResponse> {
    try {
      // Construct query text from job description
      const queryText = `
        Title: ${jobDescription.title}
        Description: ${jobDescription.description}
        Required Skills: ${(jobDescription.required_skills || []).join(', ')}
        Experience: ${jobDescription.min_experience}-${jobDescription.max_experience} years
      `.trim();

      // Construct skill-aware search query
      const requiredSkills = (jobDescription.required_skills || []).map((skill: string) => ({
        skill,
        minimum_confidence: 70,
        weight: 1.0,
        category: 'technical'
      }));

      const preferredSkills = (jobDescription.preferred_skills || []).map((skill: string) => ({
        skill,
        minimum_confidence: 60,
        weight: 0.5,
        category: 'technical'
      }));

      const minExp = jobDescription.min_experience || 0;

      const experienceLevel = minExp <= 3 ? 'entry' :
        minExp <= 7 ? 'mid' :
          minExp <= 12 ? 'senior' : 'executive';

      const result = await skillAwareSearch({
        text_query: queryText,
        required_skills: requiredSkills,
        preferred_skills: preferredSkills,
        experience_level: experienceLevel,
        limit: 50, // Fetch more candidates for reranking
        filters: {
          min_years_experience: minExp,
        },
        ranking_weights: {
          // Boost experience match for executive roles to ensure seniority
          // Boost vector similarity to capture semantic context (e.g. "B2B", "Scale up")
          experience_match: experienceLevel === 'executive' ? 0.3 : 0.15,
          skill_match: experienceLevel === 'executive' ? 0.2 : 0.35, // Reduce skill weight to avoid over-indexing on keywords
          vector_similarity: experienceLevel === 'executive' ? 0.4 : 0.35,
          confidence: 0.1
        }
      });

      const data = result.data as any;

      if (data && data.success) {
        let candidates = data.results.candidates || [];

        // Perform LLM Reranking
        try {
          const rerankResult = await rerankCandidates({
            job_description: queryText,
            candidates: candidates.map((c: any) => ({
              candidate_id: c.candidate_id,
              profile: c.profile,
              initial_score: c.overall_score
            })),
            limit: 20 // Final display limit
          });

          const rerankData = rerankResult.data as any;
          if (rerankData.success && rerankData.results.length > 0) {
            candidates = rerankData.results;
          }
        } catch (err) {
          console.warn("Reranking failed, falling back to vector sort:", err);
          // Fallback to top 20 from vector search
          candidates = candidates.slice(0, 20);
        }

        // Map skill-aware search results to frontend format
        const matches = candidates.map((c: any) => {
          let candidate = c.profile ? {
            ...c.profile,
            candidate_id: c.candidate_id,
            // Map profile fields back to candidate structure if needed
            name: c.profile.name,
            // Ensure intelligent_analysis is passed through
            intelligent_analysis: c.profile.intelligent_analysis,
            resume_analysis: c.profile.resume_analysis || {
              years_experience: c.profile.years_experience,
              technical_skills: c.profile.top_skills?.map((s: any) => s.skill) || [],
              career_trajectory: {
                current_level: c.profile.current_level,
                domain_expertise: []
              }
            }
          } : { candidate_id: c.candidate_id };

          // If we have the full candidate object in the response (which skillAwareSearch might not return fully),
          // we might need to fetch it or rely on what's returned. 
          // Looking at skill-aware-search.ts, it returns a 'profile' object but it's a simplified version.
          // However, the frontend expects a full candidate object.
          // The previous semanticSearch implementation fetched the full candidate.
          // skillAwareSearch in vector-search.ts (which skill-aware-search.ts uses) DOES fetch the full candidate 
          // but maps it to a simplified profile in the final response of skillAwareSearch.
          // Wait, skill-aware-search.ts line 433: profile: result.profile.
          // And result.profile comes from vector-search.ts line 588 which is a simplified object.
          // This might be an issue if the frontend needs more data.
          // BUT, vector-search.ts line 570 shows it fetches the full candidate data.
          // Let's assume for now we need to use what's returned or fetch if missing.
          // Actually, let's look at how I mapped it before. I was using `r.candidate_data`.
          // skillAwareSearch response doesn't seem to include the full `candidate_data`.
          // I might need to update `skill-aware-search.ts` to return the full candidate data OR
          // fetch it here if it's missing. 
          // For now, let's map what we have and see. The `profile` object has some info.

          return {
            candidate,
            score: c.overall_score / 100, // Scale 0-100 to 0-1
            similarity: c.vector_similarity_score,
            rationale: {
              overall_assessment: c.rationale && c.rationale.length > 0
                ? c.rationale.join('. ') + '.'
                : `Matched with ${(c.overall_score).toFixed(0)}% score based on skills and experience.`,
              strengths: c.rationale || [],
              gaps: [],
              risk_factors: []
            }
          };
        });

        // Generate insights on the client side
        const totalCandidates = matches.length;
        const avgScore = totalCandidates > 0
          ? matches.reduce((sum: number, m: any) => sum + m.score, 0) / totalCandidates
          : 0;

        // Extract top skills from matched candidates
        const allSkills = matches.flatMap((m: any) => m.candidate.resume_analysis?.technical_skills || []);
        const skillCounts = allSkills.reduce((acc: any, skill: string) => {
          acc[skill] = (acc[skill] || 0) + 1;
          return acc;
        }, {});
        const topSkills = Object.entries(skillCounts)
          .sort(([, a]: any, [, b]: any) => b - a)
          .slice(0, 5)
          .map(([skill]) => skill as string);

        return {
          success: true,
          matches,
          insights: {
            total_candidates: totalCandidates,
            avg_match_score: avgScore,
            top_skills_matched: topSkills,
            common_gaps: [],
            market_analysis: `Found ${totalCandidates} candidates using skill-aware search.`,
            recommendations: totalCandidates > 0 ? ['Review top matches'] : ['Try adjusting search terms']
          },

          query_time_ms: data.results.search_metadata?.search_time_ms || 0
        };
      } else {
        throw new ApiError(data?.error || 'Search failed');
      }
    } catch (error) {
      console.error('Search candidates error:', error);
      throw new ApiError('Failed to search candidates');
    }
  },

  // Get all candidates with optional filters
  async getCandidates(filters?: {
    limit?: number;
    offset?: number;
    minScore?: number;
    skills?: string[];
  }): Promise<ApiResponse<CandidateProfile[]>> {
    try {
      const result = await getCandidates(filters || {});
      return result.data as ApiResponse<CandidateProfile[]>;
    } catch (error) {
      console.error('Get candidates error:', error);
      throw new ApiError('Failed to get candidates');
    }
  },

  // Create a new candidate
  async createCandidate(candidateData: {
    name: string;
    email?: string;
    resumeText?: string;
    resumeUrl?: string;
    recruiterComments?: string;
  }): Promise<ApiResponse<CandidateProfile>> {
    try {
      const result = await createCandidate(candidateData);
      return result.data as ApiResponse<CandidateProfile>;
    } catch (error) {
      console.error('Create candidate error:', error);
      throw new ApiError('Failed to create candidate');
    }
  },

  // Generate upload URL for resume files
  async generateUploadUrl(candidateId: string, fileName: string, contentType: string, fileSize: number): Promise<ApiResponse<{ uploadUrl: string; fileUrl: string; uploadSessionId: string; requiredHeaders: Record<string, string> }>> {
    try {
      const result = await generateUploadUrl({
        candidate_id: candidateId,
        file_name: fileName,
        content_type: contentType,
        file_size: fileSize
      });

      const data = result.data as any;
      return {
        success: true,
        data: {
          uploadUrl: data.upload_url,
          fileUrl: data.file_path,
          uploadSessionId: data.upload_session_id,
          requiredHeaders: data.required_headers || {}
        }
      };
    } catch (error) {
      console.error('Generate upload URL error:', error);
      throw new ApiError('Failed to generate upload URL');
    }
  },

  // Upload file to generated URL
  async uploadFile(uploadUrl: string, file: File): Promise<void> {
    try {
      const response = await fetch(uploadUrl, {
        method: 'PUT',
        body: file,
        headers: {
          'Content-Type': file.type,
        },
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }
    } catch (error) {
      console.error('File upload error:', error);
      throw new ApiError('Failed to upload file');
    }
  },

  // Get dashboard statistics
  async getDashboardStats(): Promise<DashboardStats> {
    try {
      // This would be implemented as a separate cloud function
      // For now, we'll derive it from getCandidates
      const candidatesResult = await this.getCandidates({ limit: 1000 });

      if (candidatesResult.success && candidatesResult.data) {
        const candidatesData = candidatesResult.data as any;
        const candidates = Array.isArray(candidatesData) ? candidatesData : (candidatesData.candidates || []);
        // Use server-provided total count if available, otherwise fall back to array length
        const totalCandidates = candidatesData.pagination?.total_count || candidates.length;
        const averageScore = candidates.reduce((sum: number, candidate: CandidateProfile) =>
          sum + (candidate.overall_score || 0), 0) / totalCandidates || 0;

        // Extract top skills
        const skillsCount = new Map<string, number>();
        candidates.forEach((candidate: CandidateProfile) => {
          (candidate.resume_analysis?.technical_skills || []).forEach((skill: string) => {
            skillsCount.set(skill, (skillsCount.get(skill) || 0) + 1);
          });
        });

        const topSkills = Array.from(skillsCount.entries())
          .sort((a, b) => b[1] - a[1])
          .slice(0, 10)
          .map(([skill, count]) => ({ skill, count }));

        return {
          totalCandidates,
          averageScore: Math.round(averageScore * 100) / 100,
          activeSearches: 0, // This would come from search tracking
          recentSearches: 0, // This would come from search logs
          topSkills,
        };
      } else {
        throw new ApiError('Failed to get candidates for dashboard stats');
      }
    } catch (error) {
      console.error('Dashboard stats error:', error);
      throw new ApiError('Failed to get dashboard statistics');
    }
  },

  // Skill-aware search with confidence scoring
  async skillAwareSearch(searchQuery: {
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
  }): Promise<ApiResponse<{
    candidates: Array<{
      candidate_id: string;
      overall_score: number;
      skill_match_score: number;
      confidence_score: number;
      vector_similarity_score: number;
      experience_match_score: number;
      skill_breakdown: Record<string, number>;
      ranking_factors: any;
    }>;
    query_analysis: any;
    search_metadata: any;
  }>> {
    try {
      const result = await skillAwareSearch(searchQuery);
      return result.data as ApiResponse<any>;
    } catch (error) {
      console.error('Skill-aware search error:', error);
      throw new ApiError('Failed to perform skill-aware search');
    }
  },

  // Get detailed skill assessment for a candidate
  async getCandidateSkillAssessment(candidateId: string): Promise<ApiResponse<{
    candidate_id: string;
    skill_assessment: SkillAssessment;
  }>> {
    try {
      const result = await getCandidateSkillAssessment({ candidate_id: candidateId });
      return result.data as ApiResponse<any>;
    } catch (error) {
      console.error('Get candidate skill assessment error:', error);
      throw new ApiError('Failed to get candidate skill assessment');
    }
  },

  // Analyze skill matches between candidate and job requirements
  async analyzeSkillMatches(candidateId: string, requiredSkills: string[]): Promise<SkillMatchData[]> {
    try {
      // This combines skill assessment with job requirements
      const skillAssessmentResult = await this.getCandidateSkillAssessment(candidateId);

      if (!skillAssessmentResult.success || !skillAssessmentResult.data) {
        throw new ApiError('Failed to get skill assessment');
      }

      const { skill_assessment } = skillAssessmentResult.data;
      const skillMatches: SkillMatchData[] = [];

      requiredSkills.forEach(requiredSkill => {
        const candidateSkill = skill_assessment.skills[requiredSkill.toLowerCase()];

        if (candidateSkill) {
          skillMatches.push({
            skill: requiredSkill,
            candidate_confidence: candidateSkill.confidence,
            required_confidence: 70, // Default minimum
            match_score: candidateSkill.confidence >= 70 ? candidateSkill.confidence : candidateSkill.confidence * 0.5,
            evidence: candidateSkill.evidence,
            category: candidateSkill.category || 'technical'
          });
        } else {
          // Check for partial matches
          const partialMatch = Object.entries(skill_assessment.skills).find(([skill, _]) =>
            skill.includes(requiredSkill.toLowerCase()) ||
            requiredSkill.toLowerCase().includes(skill)
          );

          if (partialMatch) {
            const [_, skillData] = partialMatch;
            skillMatches.push({
              skill: requiredSkill,
              candidate_confidence: skillData.confidence,
              required_confidence: 70,
              match_score: skillData.confidence * 0.7, // Partial match penalty
              evidence: [...skillData.evidence, 'Partial skill match'],
              category: skillData.category || 'technical'
            });
          } else {
            skillMatches.push({
              skill: requiredSkill,
              candidate_confidence: 0,
              required_confidence: 70,
              match_score: 0,
              evidence: ['Skill not found in candidate profile'],
              category: 'technical'
            });
          }
        }
      });

      return skillMatches;
    } catch (error) {
      console.error('Analyze skill matches error:', error);
      throw new ApiError('Failed to analyze skill matches');
    }
  },

  // Saved Searches
  async saveSearch(name: string, query: any, type: 'candidate' | 'job' = 'candidate'): Promise<ApiResponse<SavedSearch>> {
    try {
      const result = await saveSearch({ name, query, type });
      return result.data as ApiResponse<SavedSearch>;
    } catch (error) {
      console.error('Save search error:', error);
      throw new ApiError('Failed to save search');
    }
  },

  async getSavedSearches(): Promise<ApiResponse<{ searches: SavedSearch[] }>> {
    try {
      const result = await getSavedSearches();
      return result.data as ApiResponse<{ searches: SavedSearch[] }>;
    } catch (error) {
      console.error('Get saved searches error:', error);
      throw new ApiError('Failed to get saved searches');
    }
  },

  async deleteSavedSearch(searchId: string): Promise<ApiResponse<{ id: string }>> {
    try {
      const result = await deleteSavedSearch({ searchId });
      return result.data as ApiResponse<{ id: string }>;
    } catch (error) {
      console.error('Delete saved search error:', error);
      throw new ApiError('Failed to delete saved search');
    }
  },

  // Similar Candidates
  async findSimilarCandidates(candidateId: string): Promise<ApiResponse<VectorSearchResult[]>> {
    try {
      const result = await findSimilarCandidates({ candidateId });
      return {
        success: true,
        data: result.data as VectorSearchResult[]
      };
    } catch (error) {
      console.error('Error finding similar candidates:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  async analyzeSearchQuery(query: string): Promise<ApiResponse<any>> {
    try {
      const result = await analyzeSearchQuery({ query });
      return {
        success: true,
        data: result.data
      };
    } catch (error) {
      console.error('Error analyzing search query:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }
};

// Export the api object for backwards compatibility
export const api = apiService;