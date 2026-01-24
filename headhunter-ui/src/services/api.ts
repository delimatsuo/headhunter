import {
  searchCandidates,
  searchJobCandidates,
  semanticSearch,
  getCandidates,
  createCandidate,
  generateUploadUrl,
  confirmUpload,
  healthCheck,
  skillAwareSearch,
  getCandidateSkillAssessment,
  rerankCandidates,
  saveSearch,
  getSavedSearches,
  deleteSavedSearch,
  findSimilarCandidates,
  analyzeSearchQuery,
  analyzeJob,
  getCandidateStats,
  engineSearch,
  getAvailableEngines
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

  // Analyze Job Description with AI
  async analyzeJob(jobDescription: string): Promise<any> {
    try {
      const result = await analyzeJob({ job_description: jobDescription });
      const data = result.data as any;
      return data.analysis || data; // Unwrap the analysis object if present
    } catch (error) {
      console.error("AI Analysis Failed", error);
      throw error;
    }
  },

  // Search candidates based on job description
  // Search candidates based on job description using semantic search
  async searchCandidates(
    jobDescription: JobDescription,
    onProgress?: (status: string) => void,
    page: number = 1,
    sourcingStrategy?: {
      target_companies?: string[];
      target_industries?: string[];
      tech_stack?: { core?: string[]; avoid?: string[] };
      title_variations?: string[];
    }
  ): Promise<SearchResponse> {
    try {
      if (onProgress) onProgress('Searching candidate database...');

      // Construct query text from job description
      // Append title_variations to query for better recall
      const titleVariations = sourcingStrategy?.title_variations?.join(' OR ') || '';
      const queryText = `
        Title: ${jobDescription.title} ${titleVariations ? `(${titleVariations})` : ''}
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

      // Use seniority from SearchAgent if provided, otherwise calculate from min_experience
      const experienceLevel = jobDescription.seniority || (
        minExp <= 3 ? 'entry' :
          minExp <= 7 ? 'mid' :
            minExp <= 12 ? 'senior' : 'executive'
      );

      console.log('Search experience level:', experienceLevel, '(from', jobDescription.seniority ? 'SearchAgent' : 'min_experience', ')');
      console.log('Sourcing Strategy:', sourcingStrategy ? `Target Companies: ${sourcingStrategy.target_companies?.join(', ')}` : 'None');

      // NEURAL MATCH: No Strict Filters.
      // We rely on the "Structured Semantic Anchor" to bias the vector space,
      // and the "Reasoning Judge" (Reranker) to enforce seniority.
      // This preserves serendipity (e.g. strong Principal Engineers acting as CTOs).

      // This preserves serendipity (e.g. strong Principal Engineers acting as CTOs).

      console.log('Search experience level:', experienceLevel, '-> Neural Match Mode (No Filters)');

      const result = await skillAwareSearch({
        text_query: queryText,
        required_skills: requiredSkills,
        preferred_skills: preferredSkills,
        experience_level: experienceLevel,
        limit: 300, // Recruiter-friendly: Fetch large pool for progressive loading
        offset: 0, // Always start from 0, pagination handled client-side
        filters: {
          min_years_experience: minExp,
          // current_level: Removed for Neural Match
        },
        ranking_weights: {
          // Boost experience match for executive roles to ensure seniority
          // Boost vector similarity to capture semantic context (e.g. "B2B", "Scale up")
          // Boost experience match for executive roles to ensure seniority
          // Title is the most important factor for C-Level (weight 0.5)
          // Skills are secondary (weight 0.1) because executives hire for skills
          // AI-First Strategy: Trust the Vector Embeddings (Semantic Understanding)
          // Experience match is just a sanity check (weight 0.2)
          // Vector Similarity is the primary driver (weight 0.7)
          experience_match: 0.1,
          skill_match: 0.0,
          vector_similarity: 0.1, // Low weight: Don't let fuzzy match override the "CEO" filter
          confidence: 0.8 // High weight: Trust the "Recruiter Brain" (Logic)
        }
      });

      const data = result.data as any;

      if (data && data.success) {
        let candidates = data.results.candidates || [];
        console.log(`Vector search returned ${candidates.length} candidates`);

        // ===== STEP 1: Apply Target Company Boost =====
        if (sourcingStrategy?.target_companies && sourcingStrategy.target_companies.length > 0) {
          const targetCompaniesLower = sourcingStrategy.target_companies.map(c => c.toLowerCase());
          candidates = candidates.map((c: any) => {
            const profile = c.profile || {};
            const currentCompany = (profile.current_company || '').toLowerCase();
            const isTargetCompany = targetCompaniesLower.some(tc => currentCompany.includes(tc));
            const companyBoost = isTargetCompany ? 15 : 0;
            return { ...c, overall_score: c.overall_score + companyBoost, isTargetCompanyMatch: isTargetCompany };
          });
          console.log(`Target Company boost applied to ${candidates.filter((c: any) => c.isTargetCompanyMatch).length} candidates`);
        }

        // ===== STEP 2: Apply GENERIC Title Affinity Boost to ALL candidates =====
        // Parse target role from job description
        const targetTitle = (jobDescription.title || '').toLowerCase();
        const descriptionText = (jobDescription.description || '').toLowerCase();

        // Try to extract role from title or first line of description that mentions a role
        const roleFromTitle = targetTitle;
        const roleFromDesc = descriptionText.match(/(?:role|position|title)[:\s]+([^.\n,]+)/i)?.[1]?.trim() || '';
        const targetRole = roleFromTitle || roleFromDesc || '';

        // ===== GENERIC TITLE AFFINITY SYSTEM =====
        // Parse any title into Level (1-5) and Function (engineering, product, etc.)

        const parseLevel = (title: string): number => {
          const t = title.toLowerCase();
          // C-suite = 5
          if (t.includes('chief') || t.match(/\bc[etpfo]o\b/) || t.includes('president')) return 5;
          // VP = 4
          if (t.includes('vp') || t.includes('vice president')) return 4;
          // Director / Head = 3
          if (t.includes('director') || t.includes('head of')) return 3;
          // Manager / Lead = 2
          if (t.includes('manager') || t.includes('lead') || t.includes('principal') || t.includes('staff')) return 2;
          // IC = 1
          return 1;
        };

        const parseFunction = (title: string): string => {
          const t = title.toLowerCase();

          // Handle C-suite abbreviations FIRST (these often don't include full keywords)
          if (t.includes('cto') || t.match(/chief\s+tech/)) return 'engineering';
          if (t.includes('cpo') || t.match(/chief\s+product/)) return 'product';
          if (t.includes('cdo') || t.match(/chief\s+data/)) return 'data';
          if (t.includes('cro') || t.match(/chief\s+revenue/)) return 'sales';
          if (t.includes('cmo') || t.match(/chief\s+market/)) return 'marketing';
          if (t.includes('coo') || t.match(/chief\s+operat/)) return 'operations';
          if (t.includes('chro') || t.match(/chief\s+(people|human)/)) return 'hr';
          if (t.includes('cfo') || t.match(/chief\s+finan/)) return 'finance';

          // Then check general keywords
          if (t.includes('engineer') || t.includes('software') || t.includes('devops') || t.includes('infrastructure')) return 'engineering';
          if (t.includes('product') || t.match(/\bpm\b/)) return 'product';
          if (t.includes('data') || t.includes('analytics') || t.includes('scientist')) return 'data';
          if (t.includes('sales') || t.includes('revenue') || t.includes('account')) return 'sales';
          if (t.includes('marketing') || t.includes('growth') || t.includes('brand')) return 'marketing';
          if (t.includes('finance') || t.includes('accounting')) return 'finance';
          if (t.includes('hr') || t.includes('people') || t.includes('talent') || t.includes('recruit')) return 'hr';
          if (t.includes('operations')) return 'operations';
          if (t.includes('design') || t.includes('ux') || t.includes('ui')) return 'design';
          return 'general';
        };

        const calculateTitleAffinity = (targetTitle: string, candidateTitle: string): number => {
          const targetLevel = parseLevel(targetTitle);
          const candidateLevel = parseLevel(candidateTitle);
          const targetFunction = parseFunction(targetTitle);
          const candidateFunction = parseFunction(candidateTitle);

          // Level distance penalty: 5 points per level of distance
          const levelDistance = Math.abs(targetLevel - candidateLevel);
          const levelPenalty = levelDistance * 5;

          // Function penalty: 0 = same function, 40 = different function
          // This ensures wrong function gets NEGATIVE boost (20 - 40 = -20)
          let functionPenalty = 0;
          if (targetFunction !== candidateFunction && targetFunction !== 'general' && candidateFunction !== 'general') {
            functionPenalty = 40; // Increased from 20 to ensure negative score
          }

          // Range: +20 (perfect match) to -25 (4 levels + different function)
          return 20 - levelPenalty - functionPenalty;
        };

        // Apply affinity to ALL candidates
        if (targetRole) {
          console.log(`Generic title affinity for "${targetRole}" (Level: ${parseLevel(targetRole)}, Function: ${parseFunction(targetRole)})`);
          candidates = candidates.map((c: any) => {
            const profile = c.profile || {};
            const candidateTitle = (profile.current_role || profile.current_title || c.current_role || '').toLowerCase();
            const titleBoost = calculateTitleAffinity(targetRole, candidateTitle);
            return { ...c, overall_score: c.overall_score + titleBoost, titleAffinityBoost: titleBoost };
          });
        }

        // Sort by boosted score
        candidates.sort((a: any, b: any) => b.overall_score - a.overall_score);
        console.log(`After title boost, top 5 candidates:`, candidates.slice(0, 5).map((c: any) =>
          `${c.profile?.current_role || 'Unknown'} (boost: ${c.titleAffinityBoost || 0}, score: ${c.overall_score})`));

        // ===== STEP 3: LLM Rerank only TOP 50 for quality =====
        const topCandidates = candidates.slice(0, 50);
        const remainingCandidates = candidates.slice(50);

        try {
          if (onProgress) onProgress('AI evaluating top candidates (this may take 15-30s)...');

          const rerankResult = await rerankCandidates({
            job_description: queryText,
            candidates: topCandidates.map((c: any) => ({
              candidate_id: c.candidate_id,
              profile: c.profile,
              initial_score: c.overall_score
            })),
            limit: 50
          });

          const rerankData = rerankResult.data as any;

          if (rerankData.success && rerankData.results && rerankData.results.length > 0) {
            console.log(`Reranking complete. Got ${rerankData.results.length} reranked candidates.`);

            // ===== STEP 4: Re-apply title boost AFTER reranker (so it affects final order) =====
            let rerankedCandidates = rerankData.results;
            if (targetRole) {
              rerankedCandidates = rerankedCandidates.map((c: any) => {
                const profile = c.profile || {};
                const candidateTitle = (profile.current_role || profile.current_title || '').toLowerCase();
                const titleBoost = calculateTitleAffinity(targetRole, candidateTitle);
                return { ...c, overall_score: c.overall_score + titleBoost, titleAffinityBoost: titleBoost };
              });
              rerankedCandidates.sort((a: any, b: any) => b.overall_score - a.overall_score);
              console.log(`Post-rerank title boost applied. Top 10:`, rerankedCandidates.slice(0, 10).map((c: any) =>
                `${c.profile?.current_role || 'Unknown'}: ${c.overall_score} (boost: ${c.titleAffinityBoost || 0})`));
            }

            // ===== STEP 5: Merge reranked top 50 + remaining candidates =====
            // Adjust remaining candidates' scores to be below the reranked ones
            const lowestRerankedScore = Math.min(...rerankedCandidates.map((c: any) => c.overall_score));
            const adjustedRemaining = remainingCandidates.map((c: any, i: number) => ({
              ...c,
              overall_score: Math.max(10, lowestRerankedScore - 10 - i), // Below reranked, decaying
              rationale: ['Vector match (not AI-evaluated)']
            }));

            candidates = [...rerankedCandidates, ...adjustedRemaining];

            // ===== STEP 6: Remove duplicates by candidate name =====
            const seenNames = new Set<string>();
            candidates = candidates.filter((c: any) => {
              const name = (c.profile?.name || c.name || '').toLowerCase().trim();
              if (!name || seenNames.has(name)) {
                return false;
              }
              seenNames.add(name);
              return true;
            });

            console.log(`Final list: ${candidates.length} candidates after deduplication`);
          } else {
            console.warn("Reranking returned empty results. Using vector+title scores.");
            // If reranking fails or returns empty, candidates remain as they were after initial boosts.
            // No explicit fallback needed here, as `candidates` already holds the pre-reranked list.
          }
        } catch (err) {
          console.warn("Reranking failed or returned empty, applying rule-based fallback:", err);

          // RULE-BASED FALLBACK: When AI fails, use deterministic ranking
          // This is transparent and explainable, unlike raw vector similarity
          const jobTitle = jobDescription.title?.toLowerCase() || '';
          const requiredSkills = jobDescription.required_skills || [];
          const targetLevel = experienceLevel; // 'executive', 'senior', 'mid', 'entry'

          candidates = candidates.map((c: any) => {
            const profile = c.profile || {};
            const candidateTitle = (profile.current_title || profile.job_title || '').toLowerCase();
            const candidateLevel = (profile.current_level || '').toLowerCase();
            const candidateSkills = profile.top_skills?.map((s: any) => s.skill?.toLowerCase() || s.toLowerCase()) || [];

            // Title Match: +30 if candidate title contains key words from job title
            const titleWords = jobTitle.split(/\s+/).filter((w: string) => w.length > 3);
            const titleMatch = titleWords.some((w: string) => candidateTitle.includes(w)) ? 30 : 0;

            // Level Match: +20 if levels align
            const levelMatch = (
              (targetLevel === 'executive' && ['executive', 'c-level', 'vp', 'director'].some(l => candidateLevel.includes(l))) ||
              (targetLevel === 'senior' && ['senior', 'lead', 'principal'].some(l => candidateLevel.includes(l))) ||
              (targetLevel === 'mid' && candidateLevel.includes('mid'))
            ) ? 20 : 0;

            // Skill Match: +2 per matching skill
            const skillMatchCount = requiredSkills.filter((skill: string) =>
              candidateSkills.some((cs: string) => cs.includes(skill.toLowerCase()))
            ).length;
            const skillScore = skillMatchCount * 2;

            // Calculate fallback score
            const fallbackScore = 50 + titleMatch + levelMatch + skillScore;

            return {
              ...c,
              overall_score: Math.min(fallbackScore, 95),
            };
          })
            .sort((a: any, b: any) => b.overall_score - a.overall_score);

          // Also include remaining candidates after the top 50
          const adjustedRemaining = remainingCandidates.map((c: any, i: number) => ({
            ...c,
            overall_score: Math.max(10, 40 - i), // Below fallback scores
            rationale: ['Vector match (fallback mode)']
          }));
          candidates = [...candidates, ...adjustedRemaining];

          console.log(`Fallback complete. ${candidates.length} total candidates.`);

          // Update rationale to reflect fallback status
          candidates = candidates.slice(0, 50).map((c: any) => ({
            ...c,
            rationale: c.rationale || [`⚠️ AI Ranking Unavailable. Ranked by Title/Level heuristic.`]
          })).concat(candidates.slice(50));
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
    candidate_id?: string;
    name?: string;
    email?: string;
    resume_text?: string;
    resume_url?: string;
    notes?: string;
    resumeText?: string;
    resumeUrl?: string;
    recruiterComments?: string;
  }): Promise<ApiResponse<CandidateProfile>> {
    try {
      // Build payload dynamically - only include fields with values
      // Firebase converts undefined to null, but backend Zod doesn't accept null for optional strings
      const payload: Record<string, string> = {
        name: candidateData.name || 'Unknown Candidate'
      };

      // CRITICAL: Pass candidate_id to backend so file uploads and documents use the same ID
      if (candidateData.candidate_id) {
        payload.candidate_id = candidateData.candidate_id;
      }

      const email = candidateData.email;
      if (email && email.trim()) payload.email = email.trim();

      const resumeText = candidateData.resume_text || candidateData.resumeText;
      if (resumeText && resumeText.trim()) payload.resume_text = resumeText.trim();

      const resumeUrl = candidateData.resume_url || candidateData.resumeUrl;
      if (resumeUrl && resumeUrl.trim()) payload.resume_url = resumeUrl.trim();

      const notes = candidateData.notes || candidateData.recruiterComments;
      if (notes && notes.trim()) payload.notes = notes.trim();

      console.log('Creating candidate with payload:', payload);
      const result = await createCandidate(payload);
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

  // Confirm upload to trigger processing pipeline
  async confirmUpload(uploadSessionId: string): Promise<ApiResponse<any>> {
    try {
      const result = await confirmUpload({ upload_session_id: uploadSessionId });
      return result.data as ApiResponse<any>;
    } catch (error) {
      console.error('Confirm upload error:', error);
      throw new ApiError('Failed to confirm upload');
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
      const result = await getCandidateStats();
      const data = result.data as any;

      if (data.success && data.stats) {
        const stats = data.stats;
        return {
          totalCandidates: stats.total_candidates,
          averageScore: 0, // Not currently calculated by backend
          activeSearches: 0,
          recentSearches: 0,
          topSkills: stats.top_skills || [],
          recentActivity: {
            searches: 0,
            newCandidates: stats.recent_candidates || 0,
            highMatches: 0
          },
          experienceLevels: stats.experience_levels,
          companyTiers: stats.company_tiers,
        };
      } else {
        throw new ApiError('Failed to get dashboard stats');
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
      const result = await findSimilarCandidates({ candidate_id: candidateId });
      // The backend returns { success: true, candidate_id, results: [...] }
      // We need to extract the results array
      const responseData = result.data as any;
      return {
        success: true,
        data: responseData.results || []
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
  },

  // AI Engine-based search - allows switching between Legacy and Agentic engines
  async searchWithEngine(
    engine: 'legacy' | 'agentic',
    jobDescription: JobDescription,
    options?: {
      limit?: number;
      page?: number;
      sourcingStrategy?: {
        target_companies?: string[];
        target_industries?: string[];
      };
    },
    onProgress?: (status: string) => void
  ): Promise<SearchResponse> {
    try {
      if (onProgress) {
        onProgress(`Using ${engine === 'legacy' ? '⚡ Fast Match' : '🧠 Deep Analysis'} engine...`);
      }

      const result = await engineSearch({
        engine: engine,
        job: {
          title: jobDescription.title,
          description: jobDescription.description,
          required_skills: jobDescription.required_skills,
          nice_to_have: jobDescription.nice_to_have,
          min_experience: jobDescription.min_experience,
          max_experience: jobDescription.max_experience,
        },
        options: {
          limit: options?.limit || 50,
          page: options?.page || 0,
          sourcingStrategy: options?.sourcingStrategy,
        }
      });

      const data = result.data as any;

      if (onProgress) {
        onProgress(`Found ${data.results?.length || 0} candidates`);
      }

      // Transform engine results to match SearchResponse format
      // IMPORTANT: Pass through the FULL candidate data including intelligent_analysis
      const candidates = (data.results || []).map((match: any, index: number) => {
        const rawCandidate = match.candidate || {};
        const profile = rawCandidate.profile || rawCandidate;

        // Pass through the FULL profile with all analysis data intact
        return {
          candidate_id: match.candidate_id || rawCandidate.candidate_id || `candidate-${index}`,
          overall_score: match.score || 0,
          skill_match_score: match.match_metadata?.skill_match_score || match.score,
          confidence_score: match.match_metadata?.confidence_score || 85,
          vector_similarity_score: match.match_metadata?.vector_score || match.score,
          experience_match_score: match.match_metadata?.experience_match || 80,
          // Pass through match_metadata for raw_vector_similarity access
          match_metadata: match.match_metadata || {},
          skill_breakdown: rawCandidate.skill_breakdown || {},
          ranking_factors: rawCandidate.ranking_factors || {},
          // Pass through the FULL profile, not a stripped version
          profile: profile,
          // Keep all intelligent_analysis and resume_analysis
          intelligent_analysis: profile.intelligent_analysis || rawCandidate.intelligent_analysis,
          resume_analysis: profile.resume_analysis || rawCandidate.resume_analysis,
          original_data: profile.original_data || rawCandidate.original_data,
          // Rationale from engine
          summary: match.rationale?.overall_assessment || '',
          rationale: match.rationale?.strengths || [],
          matchReasons: profile.matchReasons || rawCandidate.match_reasons || [],
          // Agentic-specific fields
          concerns: match.rationale?.concerns || [],
          interview_questions: match.rationale?.interview_questions || [],
        };
      });

      // Transform to CandidateMatch format for SearchResponse
      // Pass through the FULL candidate object
      const matches = candidates.map((c: any) => ({
        candidate: {
          ...c,
          candidate_id: c.candidate_id,
          name: c.profile?.name || 'Unknown',
          current_role: c.profile?.current_role || c.profile?.current_level,
          current_company: c.profile?.current_company,
          years_experience: c.profile?.years_experience,
          skills: c.profile?.skills || c.profile?.top_skills?.map((s: any) => s.skill) || [],
          linkedin_url: c.profile?.linkedin_url,
          resume_url: c.profile?.resume_url,
          overall_score: c.overall_score,
          // Pass through all analysis data
          intelligent_analysis: c.intelligent_analysis,
          resume_analysis: c.resume_analysis,
          original_data: c.original_data,
          // Include rationale for display
          summary: c.summary,
          rationale: c.rationale?.[0] ? {
            overall_assessment: c.summary,
            strengths: c.rationale,
            gaps: c.concerns || [],
            risk_factors: []
          } : undefined,
          matchReasons: c.matchReasons || c.rationale,
        },
        score: c.overall_score / 100, // LLM-influenced match score (0-1 scale)
        similarity: (c.match_metadata?.raw_vector_similarity || c.vector_similarity_score || 0) / 100, // Raw vector similarity (0-1 scale)
        rationale: {
          overall_assessment: c.summary || 'Matched based on profile similarity',
          strengths: c.rationale || [],
          gaps: c.concerns || [],
          risk_factors: []
        }
      }));

      // TODO: Remove after Phase 1 verification
      // Debug: Log score differentiation
      if (matches.length > 0) {
        const sampleMatch = matches[0];
        console.log(`[API Debug] searchWithEngine first result - Match: ${sampleMatch.score?.toFixed(2)}, Similarity: ${sampleMatch.similarity?.toFixed(2)}, Different: ${Math.abs((sampleMatch.score || 0) - (sampleMatch.similarity || 0)) > 0.01}`);
      }

      const avgScore = matches.length > 0
        ? matches.reduce((sum: number, m: any) => sum + m.score, 0) / matches.length
        : 0;

      return {
        success: true,
        matches,
        insights: {
          total_candidates: data.total_candidates || matches.length,
          avg_match_score: avgScore,
          top_skills_matched: [],
          common_gaps: [],
          market_analysis: `Found ${matches.length} candidates using ${data.engine_used === 'agentic' ? 'Deep Analysis' : 'Fast Match'} engine.`,
          recommendations: matches.length > 0 ? ['Review top matches'] : ['Try adjusting search terms']
        },
        query_time_ms: data.execution_time_ms || 0
      };
    } catch (error) {
      console.error('[searchWithEngine] Error:', error);
      throw new ApiError(
        error instanceof Error ? error.message : 'Engine search failed',
        500
      );
    }
  },

  // Get list of available AI engines
  async getAvailableEngines(): Promise<{ engines: Array<{ id: string; label: string; description: string }>; default: string }> {
    try {
      const result = await getAvailableEngines();
      return result.data as any;
    } catch (error) {
      console.error('[getAvailableEngines] Error:', error);
      // Return default engines if function call fails
      return {
        engines: [
          { id: 'legacy', label: '⚡ Fast Match', description: 'Vector + Title boost + LLM rerank' },
          { id: 'agentic', label: '🧠 Deep Analysis', description: 'Comparative reasoning with insights' }
        ],
        default: 'legacy'
      };
    }
  }
};

// Export the api object for backwards compatibility
export const api = apiService;