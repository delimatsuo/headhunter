import {
  searchCandidates,
  getCandidates,
  createCandidate,
  generateUploadUrl,
  healthCheck
} from '../config/firebase';
import {
  JobDescription,
  SearchResponse,
  CandidateProfile,
  ApiResponse,
  DashboardStats
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
};