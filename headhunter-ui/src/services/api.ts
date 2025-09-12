import {
  searchCandidates,
  getCandidates,
  createCandidate,
  generateUploadUrl,
  healthCheck,
  skillAwareSearch,
  getCandidateSkillAssessment
} from '../config/firebase';
import {
  JobDescription,
  SearchResponse,
  CandidateProfile,
  ApiResponse,
  DashboardStats,
  SkillAssessment,
  SkillMatchData
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
  async searchCandidates(jobDescription: JobDescription): Promise<SearchResponse> {
    try {
      const result = await searchCandidates({
        jobDescription,
        limit: 20,
        minScore: 0.5
      });
      
      if (result.data && (result.data as any).success) {
        return result.data as SearchResponse;
      } else {
        throw new ApiError((result.data as any)?.error || 'Search failed');
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
  async generateUploadUrl(fileName: string, contentType: string): Promise<ApiResponse<{ uploadUrl: string; fileUrl: string }>> {
    try {
      const result = await generateUploadUrl({
        fileName,
        contentType
      });
      return result.data as ApiResponse<{ uploadUrl: string; fileUrl: string }>;
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
        const candidates = candidatesResult.data;
        const totalCandidates = candidates.length;
        const averageScore = candidates.reduce((sum, candidate) => 
          sum + (candidate.overall_score || 0), 0) / totalCandidates || 0;
        
        // Extract top skills
        const skillsCount = new Map<string, number>();
        candidates.forEach(candidate => {
          (candidate.resume_analysis?.technical_skills || []).forEach(skill => {
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
};

// Export the api object for backwards compatibility
export const api = apiService;