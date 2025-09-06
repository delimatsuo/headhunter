/**
 * Job Search Service for intelligent candidate matching
 */

import * as admin from "firebase-admin";
import { VectorSearchService } from "./vector-search";

// Types for job search
export interface JobDescription {
  title: string;
  description: string;
  required_skills?: string[];
  preferred_skills?: string[];
  years_experience?: number;
  education_level?: string;
  company_type?: string;
  team_size?: number;
  location?: string;
  salary_range?: {
    min: number;
    max: number;
    currency: string;
  };
}

export interface CandidateMatch {
  candidate_id: string;
  name: string;
  match_score: number;
  similarity_score: number;
  ranking_score: number;
  match_rationale: {
    summary: string;
    strengths: string[];
    gaps: string[];
    risk_factors: string[];
  };
  key_qualifications: {
    years_experience: number;
    current_level: string;
    company_tier: string;
    technical_skills: string[];
    leadership_experience: boolean;
  };
  recommendation_level: "perfect_match" | "strong_match" | "good_match" | "possible_match" | "weak_match";
  availability: string;
  contact_priority: number;
}

export interface SearchResponse {
  success: boolean;
  job_title: string;
  search_timestamp: string;
  total_candidates_evaluated: number;
  matches: CandidateMatch[];
  search_insights: {
    top_skills_found: string[];
    common_gaps: string[];
    market_insights: string;
    recommendation: string;
  };
}

export class JobSearchService {
  private firestore: admin.firestore.Firestore;
  private vectorSearch: VectorSearchService;

  constructor() {
    this.firestore = admin.firestore();
    this.vectorSearch = new VectorSearchService();
  }

  /**
   * Parse job description to extract key requirements
   */
  parseJobDescription(jobDesc: JobDescription): {
    searchQuery: string;
    requirements: {
      must_have: string[];
      nice_to_have: string[];
      experience_level: string;
      leadership_required: boolean;
    };
  } {
    const parts: string[] = [];
    
    // Add job title
    parts.push(jobDesc.title);
    
    // Add description
    parts.push(jobDesc.description);
    
    // Add required skills
    if (jobDesc.required_skills?.length) {
      parts.push(`Required skills: ${jobDesc.required_skills.join(", ")}`);
    }
    
    // Add preferred skills
    if (jobDesc.preferred_skills?.length) {
      parts.push(`Preferred skills: ${jobDesc.preferred_skills.join(", ")}`);
    }
    
    // Add experience requirement
    if (jobDesc.years_experience) {
      parts.push(`${jobDesc.years_experience}+ years experience`);
    }
    
    // Add education requirement
    if (jobDesc.education_level) {
      parts.push(`Education: ${jobDesc.education_level}`);
    }
    
    // Add company context
    if (jobDesc.company_type) {
      parts.push(`Company type: ${jobDesc.company_type}`);
    }
    
    // Add team context
    if (jobDesc.team_size) {
      parts.push(`Team size: ${jobDesc.team_size}`);
    }
    
    // Determine experience level from years and title
    let experienceLevel = "Mid";
    if (jobDesc.years_experience) {
      if (jobDesc.years_experience >= 10) {
        experienceLevel = "Principal";
      } else if (jobDesc.years_experience >= 7) {
        experienceLevel = "Senior";
      } else if (jobDesc.years_experience >= 3) {
        experienceLevel = "Mid";
      } else {
        experienceLevel = "Entry";
      }
    }
    
    // Check for leadership requirements
    const leadershipKeywords = ["lead", "manager", "head", "director", "principal", "staff", "architect"];
    const titleLower = jobDesc.title.toLowerCase();
    const descLower = jobDesc.description.toLowerCase();
    const leadershipRequired = leadershipKeywords.some(keyword => 
      titleLower.includes(keyword) || descLower.includes(keyword)
    );
    
    return {
      searchQuery: parts.filter(Boolean).join(". "),
      requirements: {
        must_have: jobDesc.required_skills || [],
        nice_to_have: jobDesc.preferred_skills || [],
        experience_level: experienceLevel,
        leadership_required: leadershipRequired || (jobDesc.team_size ? jobDesc.team_size > 0 : false)
      }
    };
  }

  /**
   * Calculate comprehensive match score
   */
  calculateMatchScore(
    candidate: any,
    jobDesc: JobDescription,
    similarityScore: number
  ): {
    matchScore: number;
    rankingScore: number;
    skillsMatch: number;
    experienceMatch: number;
    leadershipMatch: number;
    educationMatch: number;
  } {
    let skillsMatch = 0;
    let experienceMatch = 0;
    let leadershipMatch = 0;
    let educationMatch = 0;
    
    // Skills matching (40% weight)
    if (jobDesc.required_skills && candidate.technical_skills) {
      const candidateSkills = (candidate.technical_skills || []).map((s: string) => s.toLowerCase());
      const requiredSkills = jobDesc.required_skills.map(s => s.toLowerCase());
      const preferredSkills = (jobDesc.preferred_skills || []).map(s => s.toLowerCase());
      
      // Required skills matching
      const requiredMatches = requiredSkills.filter(skill => 
        candidateSkills.some((cs: string) => cs.includes(skill) || skill.includes(cs))
      ).length;
      
      // Preferred skills matching
      const preferredMatches = preferredSkills.filter(skill =>
        candidateSkills.some((cs: string) => cs.includes(skill) || skill.includes(cs))
      ).length;
      
      if (requiredSkills.length > 0) {
        skillsMatch = (requiredMatches / requiredSkills.length) * 0.7;
      }
      
      if (preferredSkills.length > 0) {
        skillsMatch += (preferredMatches / preferredSkills.length) * 0.3;
      }
      
      // Cap at 1.0
      skillsMatch = Math.min(1.0, skillsMatch);
    } else {
      // If no specific skills required, base on similarity
      skillsMatch = similarityScore;
    }
    
    // Experience matching (30% weight)
    const candidateYears = candidate.years_experience || 0;
    const requiredYears = jobDesc.years_experience || 0;
    
    if (candidateYears >= requiredYears) {
      // Meets or exceeds requirement
      experienceMatch = 1.0;
    } else if (candidateYears >= requiredYears - 2) {
      // Close to requirement (within 2 years)
      experienceMatch = 0.8;
    } else if (candidateYears >= requiredYears - 4) {
      // Somewhat below requirement
      experienceMatch = 0.6;
    } else {
      // Significantly below requirement
      experienceMatch = 0.3;
    }
    
    // Leadership matching (20% weight)
    const { requirements } = this.parseJobDescription(jobDesc);
    if (requirements.leadership_required) {
      const hasLeadership = candidate.leadership_level && 
                          candidate.leadership_level !== "None" && 
                          candidate.leadership_level !== "Individual Contributor";
      leadershipMatch = hasLeadership ? 1.0 : 0.3;
    } else {
      // Leadership not required, neutral score
      leadershipMatch = 0.8;
    }
    
    // Education matching (10% weight)
    if (jobDesc.education_level) {
      const educationLevels = ["BS", "MS", "PhD"];
      const requiredIndex = educationLevels.findIndex(level => 
        jobDesc.education_level?.includes(level)
      );
      
      // Check candidate's education
      const candidateEducation = candidate.enrichment_summary || "";
      let candidateIndex = -1;
      
      if (candidateEducation.includes("PhD") || candidateEducation.includes("Ph.D")) {
        candidateIndex = 2;
      } else if (candidateEducation.includes("MS") || candidateEducation.includes("Master")) {
        candidateIndex = 1;
      } else if (candidateEducation.includes("BS") || candidateEducation.includes("Bachelor")) {
        candidateIndex = 0;
      }
      
      if (candidateIndex >= requiredIndex) {
        educationMatch = 1.0;
      } else if (candidateIndex === requiredIndex - 1) {
        educationMatch = 0.7;
      } else {
        educationMatch = 0.5;
      }
    } else {
      // Education not specified, neutral score
      educationMatch = 0.9;
    }
    
    // Calculate weighted match score
    const matchScore = (
      skillsMatch * 0.4 +
      experienceMatch * 0.3 +
      leadershipMatch * 0.2 +
      educationMatch * 0.1
    );
    
    // Combine with similarity score for final ranking
    const rankingScore = (matchScore * 0.6) + (similarityScore * 0.4);
    
    return {
      matchScore,
      rankingScore,
      skillsMatch,
      experienceMatch,
      leadershipMatch,
      educationMatch
    };
  }

  /**
   * Generate match rationale with AI-powered insights
   */
  generateMatchRationale(
    candidate: any,
    jobDesc: JobDescription,
    scores: any
  ): CandidateMatch["match_rationale"] {
    const strengths: string[] = [];
    const gaps: string[] = [];
    const riskFactors: string[] = [];
    
    // Analyze skills match
    if (scores.skillsMatch >= 0.8) {
      strengths.push("Excellent technical skills alignment with requirements");
    } else if (scores.skillsMatch >= 0.6) {
      strengths.push("Good technical skills coverage");
    } else if (scores.skillsMatch < 0.5) {
      gaps.push("Limited match on required technical skills");
    }
    
    // Analyze experience
    const candidateYears = candidate.years_experience || 0;
    const requiredYears = jobDesc.years_experience || 0;
    
    if (candidateYears >= requiredYears + 3) {
      strengths.push(`Strong experience with ${candidateYears} years (exceeds requirement)`);
    } else if (candidateYears >= requiredYears) {
      strengths.push(`Meets experience requirement with ${candidateYears} years`);
    } else if (candidateYears < requiredYears - 2) {
      gaps.push(`Experience gap: ${candidateYears} years vs ${requiredYears} required`);
    }
    
    // Analyze leadership
    const { requirements } = this.parseJobDescription(jobDesc);
    if (requirements.leadership_required) {
      if (candidate.leadership_level && candidate.leadership_level !== "None") {
        strengths.push(`Proven ${candidate.leadership_level} leadership experience`);
      } else {
        gaps.push("No demonstrated leadership experience for leadership role");
      }
    }
    
    // Analyze company background
    if (candidate.company_tier === "Tier1") {
      strengths.push("Premium company pedigree (Tier 1 companies)");
    }
    
    // Analyze cultural fit and soft factors
    if (candidate.enrichment_summary?.includes("excellent cultural")) {
      strengths.push("Strong cultural alignment indicators");
    }
    
    // Risk assessment
    if (candidateYears > requiredYears + 5) {
      riskFactors.push("May be overqualified - retention risk");
    }
    
    if (scores.matchScore < 0.5) {
      riskFactors.push("Significant gaps in core requirements");
    }
    
    if (candidate.recommendation === "no_hire") {
      riskFactors.push("Previous negative assessment on record");
    }
    
    // Generate summary
    let summary = "";
    if (scores.rankingScore >= 0.8) {
      summary = `Excellent match with ${Math.round(scores.rankingScore * 100)}% alignment. Strong technical and experience fit.`;
    } else if (scores.rankingScore >= 0.6) {
      summary = `Good match with ${Math.round(scores.rankingScore * 100)}% alignment. Meets most key requirements.`;
    } else if (scores.rankingScore >= 0.4) {
      summary = `Possible match with ${Math.round(scores.rankingScore * 100)}% alignment. Some gaps but potential fit.`;
    } else {
      summary = `Weak match with ${Math.round(scores.rankingScore * 100)}% alignment. Significant requirement gaps.`;
    }
    
    return {
      summary,
      strengths: strengths.length > 0 ? strengths : ["General professional experience"],
      gaps: gaps.length > 0 ? gaps : ["No significant gaps identified"],
      risk_factors: riskFactors.length > 0 ? riskFactors : ["Low risk profile"]
    };
  }

  /**
   * Determine recommendation level based on scores
   */
  getRecommendationLevel(rankingScore: number): CandidateMatch["recommendation_level"] {
    if (rankingScore >= 0.9) return "perfect_match";
    if (rankingScore >= 0.75) return "strong_match";
    if (rankingScore >= 0.6) return "good_match";
    if (rankingScore >= 0.4) return "possible_match";
    return "weak_match";
  }

  /**
   * Main search method - process job description and return ranked candidates
   */
  async searchCandidates(jobDesc: JobDescription, limit: number = 20): Promise<SearchResponse> {
    try {
      // Parse job description
      const { searchQuery, requirements } = this.parseJobDescription(jobDesc);
      
      // Perform semantic search
      const searchResults = await this.vectorSearch.searchSimilar({
        query_text: searchQuery,
        filters: {
          min_years_experience: jobDesc.years_experience ? jobDesc.years_experience - 2 : undefined,
          current_level: requirements.experience_level !== "Entry" ? requirements.experience_level : undefined
        },
        limit: limit * 2 // Get more candidates for better ranking
      });
      
      // Enhance results with full candidate data and scoring
      const enhancedMatches: CandidateMatch[] = [];
      
      for (const result of searchResults) {
        try {
          // Get full candidate profile
          const candidateDoc = await this.firestore
            .collection("candidates")
            .doc(result.candidate_id)
            .get();
          
          if (!candidateDoc.exists) continue;
          
          const candidateData = candidateDoc.data();
          
          // Calculate comprehensive scores
          const scores = this.calculateMatchScore(
            candidateData,
            jobDesc,
            result.similarity_score
          );
          
          // Generate match rationale
          const rationale = this.generateMatchRationale(
            candidateData,
            jobDesc,
            scores
          );
          
          // Create candidate match object
          const match: CandidateMatch = {
            candidate_id: result.candidate_id,
            name: candidateData?.name || "Unknown",
            match_score: scores.matchScore,
            similarity_score: result.similarity_score,
            ranking_score: scores.rankingScore,
            match_rationale: rationale,
            key_qualifications: {
              years_experience: candidateData?.years_experience || 0,
              current_level: candidateData?.current_level || "Unknown",
              company_tier: candidateData?.company_tier || "Unknown",
              technical_skills: candidateData?.technical_skills || [],
              leadership_experience: Boolean(candidateData?.leadership_level && 
                                           candidateData.leadership_level !== "None")
            },
            recommendation_level: this.getRecommendationLevel(scores.rankingScore),
            availability: candidateData?.readiness_level || "Unknown",
            contact_priority: Math.round(scores.rankingScore * 10)
          };
          
          enhancedMatches.push(match);
        } catch (error) {
          console.error(`Error processing candidate ${result.candidate_id}:`, error);
        }
      }
      
      // Sort by ranking score
      enhancedMatches.sort((a, b) => b.ranking_score - a.ranking_score);
      
      // Limit to requested number
      const topMatches = enhancedMatches.slice(0, limit);
      
      // Generate search insights
      const searchInsights = this.generateSearchInsights(topMatches, jobDesc);
      
      return {
        success: true,
        job_title: jobDesc.title,
        search_timestamp: new Date().toISOString(),
        total_candidates_evaluated: searchResults.length,
        matches: topMatches,
        search_insights: searchInsights
      };
    } catch (error) {
      console.error("Error in job search:", error);
      throw error;
    }
  }

  /**
   * Generate insights about the search results
   */
  private generateSearchInsights(
    matches: CandidateMatch[],
    jobDesc: JobDescription
  ): SearchResponse["search_insights"] {
    // Analyze top skills found
    const skillsFrequency: Record<string, number> = {};
    matches.forEach(match => {
      match.key_qualifications.technical_skills.forEach(skill => {
        skillsFrequency[skill] = (skillsFrequency[skill] || 0) + 1;
      });
    });
    
    const topSkillsFound = Object.entries(skillsFrequency)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([skill]) => skill);
    
    // Identify common gaps
    const gapsFrequency: Record<string, number> = {};
    matches.forEach(match => {
      match.match_rationale.gaps.forEach(gap => {
        const normalizedGap = gap.toLowerCase().includes("leadership") ? "Leadership experience" :
                             gap.toLowerCase().includes("skill") ? "Technical skills" :
                             gap.toLowerCase().includes("experience") ? "Years of experience" :
                             gap;
        gapsFrequency[normalizedGap] = (gapsFrequency[normalizedGap] || 0) + 1;
      });
    });
    
    const commonGaps = Object.entries(gapsFrequency)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([gap]) => gap);
    
    // Generate market insights
    let marketInsights = "";
    const avgScore = matches.reduce((sum, m) => sum + m.ranking_score, 0) / matches.length;
    
    if (avgScore >= 0.7) {
      marketInsights = "Strong candidate pool available. Multiple well-qualified candidates found.";
    } else if (avgScore >= 0.5) {
      marketInsights = "Moderate candidate availability. Some qualified candidates with minor gaps.";
    } else {
      marketInsights = "Limited exact matches. Consider adjusting requirements or timeline.";
    }
    
    // Generate recommendation
    let recommendation = "";
    const topMatch = matches[0];
    
    if (topMatch && topMatch.ranking_score >= 0.8) {
      recommendation = `Proceed with top ${Math.min(3, matches.filter(m => m.ranking_score >= 0.75).length)} candidates immediately. Strong matches available.`;
    } else if (topMatch && topMatch.ranking_score >= 0.6) {
      recommendation = "Review top candidates carefully. Consider additional screening for requirement gaps.";
    } else {
      recommendation = "Expand search criteria or consider alternative sourcing strategies.";
    }
    
    return {
      top_skills_found: topSkillsFound,
      common_gaps: commonGaps.length > 0 ? commonGaps : ["No significant gaps"],
      market_insights: marketInsights,
      recommendation: recommendation
    };
  }

  /**
   * Cache search results for performance
   */
  async cacheSearchResults(
    jobDesc: JobDescription,
    results: SearchResponse
  ): Promise<void> {
    const cacheKey = this.generateCacheKey(jobDesc);
    
    await this.firestore
      .collection("search_cache")
      .doc(cacheKey)
      .set({
        job_description: jobDesc,
        results: results,
        cached_at: admin.firestore.FieldValue.serverTimestamp(),
        expires_at: new Date(Date.now() + 3600000) // 1 hour cache
      });
  }

  /**
   * Retrieve cached search results
   */
  async getCachedResults(jobDesc: JobDescription): Promise<SearchResponse | null> {
    const cacheKey = this.generateCacheKey(jobDesc);
    
    const cacheDoc = await this.firestore
      .collection("search_cache")
      .doc(cacheKey)
      .get();
    
    if (!cacheDoc.exists) return null;
    
    const cached = cacheDoc.data();
    const expiresAt = cached?.expires_at?.toDate();
    
    if (cached && expiresAt && expiresAt > new Date()) {
      return cached.results as SearchResponse;
    }
    
    return null;
  }

  /**
   * Generate cache key from job description
   */
  private generateCacheKey(jobDesc: JobDescription): string {
    const keyParts = [
      jobDesc.title,
      jobDesc.required_skills?.join(",") || "",
      jobDesc.years_experience?.toString() || "",
      jobDesc.company_type || ""
    ];
    
    // Simple hash function
    const hash = keyParts.join("|").split("").reduce((a, b) => {
      a = ((a << 5) - a) + b.charCodeAt(0);
      return a & a;
    }, 0);
    
    return `search_${Math.abs(hash)}`;
  }
}