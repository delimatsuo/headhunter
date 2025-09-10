/**
 * Job Search Service for matching candidates to job descriptions
 */

import * as admin from "firebase-admin";

export interface JobDescription {
  title: string;
  description: string;
  required_skills: string[];
  preferred_skills?: string[];
  years_experience?: number;
  education_level?: string;
  company_type?: string;
  team_size?: number;
  location?: string;
  salary_range?: {
    min?: number;
    max?: number;
  };
}

export interface CandidateMatch {
  candidate: any;
  score: number;
  similarity: number;
  rationale: {
    overall_assessment: string;
    strengths: string[];
    gaps: string[];
    risk_factors: string[];
  };
}

export interface SearchInsights {
  total_candidates: number;
  avg_match_score: number;
  top_skills_matched: string[];
  market_analysis: string;
  recommendations: string[];
}

export interface SearchResults {
  matches: CandidateMatch[];
  insights: SearchInsights;
  query_time: number;
}

export class JobSearchService {
  private firestore: admin.firestore.Firestore;
  private cache: Map<string, SearchResults> = new Map();

  constructor() {
    this.firestore = admin.firestore();
  }

  /**
   * Search for candidates matching a job description
   */
  async searchCandidates(jobDesc: JobDescription, limit: number = 20): Promise<SearchResults> {
    const startTime = Date.now();
    
    try {
      // Get all candidate profiles
      const candidatesSnapshot = await this.firestore
        .collection("candidates")
        .limit(100) // Reasonable limit for processing
        .get();

      const candidates = candidatesSnapshot.docs.map(doc => ({
        candidate_id: doc.id,
        ...doc.data()
      }));

      // Calculate match scores for each candidate
      const matches: CandidateMatch[] = [];
      
      for (const candidate of candidates) {
        try {
          const score = this.calculateMatchScore(candidate, jobDesc);
          const similarity = Math.random() * 0.4 + 0.6; // Mock similarity for now
          
          if (score > 30) { // Only include reasonable matches
            matches.push({
              candidate,
              score,
              similarity,
              rationale: this.generateRationale(candidate, jobDesc, score)
            });
          }
        } catch (error) {
          console.warn(`Error processing candidate ${candidate.candidate_id}:`, error);
        }
      }

      // Sort by score and limit results
      matches.sort((a, b) => b.score - a.score);
      const topMatches = matches.slice(0, limit);

      // Generate insights
      const insights = this.generateInsights(topMatches, jobDesc);
      
      const queryTime = Date.now() - startTime;

      return {
        matches: topMatches,
        insights,
        query_time: queryTime
      };
    } catch (error) {
      console.error("Error in searchCandidates:", error);
      throw error;
    }
  }

  /**
   * Calculate match score for a candidate
   */
  private calculateMatchScore(candidate: any, jobDesc: JobDescription): number {
    let totalScore = 0;
    
    // Skills matching (40% weight)
    const skillsScore = this.calculateSkillsMatch(candidate, jobDesc);
    totalScore += skillsScore * 0.4;

    // Experience matching (30% weight)  
    const experienceScore = this.calculateExperienceMatch(candidate, jobDesc);
    totalScore += experienceScore * 0.3;

    // Leadership matching (20% weight)
    const leadershipScore = this.calculateLeadershipMatch(candidate, jobDesc);
    totalScore += leadershipScore * 0.2;

    // Education matching (10% weight)
    const educationScore = this.calculateEducationMatch(candidate, jobDesc);
    totalScore += educationScore * 0.1;

    return Math.round(totalScore);
  }

  private calculateSkillsMatch(candidate: any, jobDesc: JobDescription): number {
    if (!candidate.resume_analysis?.technical_skills) return 0;
    
    const candidateSkills = candidate.resume_analysis.technical_skills.map((s: string) => s.toLowerCase());
    const requiredSkills = jobDesc.required_skills.map(s => s.toLowerCase());
    const preferredSkills = (jobDesc.preferred_skills || []).map(s => s.toLowerCase());
    
    let matchedRequired = 0;
    let matchedPreferred = 0;
    
    for (const skill of candidateSkills) {
      if (requiredSkills.some(req => skill.includes(req) || req.includes(skill))) {
        matchedRequired++;
      }
      if (preferredSkills.some(pref => skill.includes(pref) || pref.includes(skill))) {
        matchedPreferred++;
      }
    }
    
    const requiredScore = requiredSkills.length > 0 ? (matchedRequired / requiredSkills.length) * 80 : 80;
    const preferredScore = preferredSkills.length > 0 ? (matchedPreferred / preferredSkills.length) * 20 : 20;
    
    return Math.min(100, requiredScore + preferredScore);
  }

  private calculateExperienceMatch(candidate: any, jobDesc: JobDescription): number {
    if (!candidate.resume_analysis?.years_experience || !jobDesc.years_experience) return 70;
    
    const candidateExp = candidate.resume_analysis.years_experience;
    const requiredExp = jobDesc.years_experience;
    
    if (candidateExp >= requiredExp) {
      // Bonus for more experience, but diminishing returns
      const bonus = Math.min(20, (candidateExp - requiredExp) * 2);
      return Math.min(100, 80 + bonus);
    } else {
      // Penalty for less experience
      const penalty = (requiredExp - candidateExp) * 10;
      return Math.max(0, 80 - penalty);
    }
  }

  private calculateLeadershipMatch(candidate: any, jobDesc: JobDescription): number {
    const hasLeadership = candidate.resume_analysis?.leadership_scope?.has_leadership || false;
    
    if (jobDesc.title?.toLowerCase().includes('lead') || 
        jobDesc.title?.toLowerCase().includes('manager') ||
        jobDesc.title?.toLowerCase().includes('director')) {
      return hasLeadership ? 100 : 30;
    }
    
    return hasLeadership ? 80 : 60; // Leadership is generally positive
  }

  private calculateEducationMatch(candidate: any, jobDesc: JobDescription): number {
    if (!jobDesc.education_level) return 80;
    
    const candidateEducation = candidate.resume_analysis?.education?.highest_degree?.toLowerCase() || '';
    const requiredEducation = jobDesc.education_level.toLowerCase();
    
    if (candidateEducation.includes('phd') || candidateEducation.includes('doctorate')) {
      return 100;
    }
    if (candidateEducation.includes('master') && !requiredEducation.includes('phd')) {
      return 95;
    }
    if (candidateEducation.includes('bachelor')) {
      return requiredEducation.includes('bachelor') ? 100 : 80;
    }
    
    return 60; // Some penalty for not meeting education requirements
  }

  private generateRationale(candidate: any, jobDesc: JobDescription, score: number): {
    overall_assessment: string;
    strengths: string[];
    gaps: string[];
    risk_factors: string[];
  } {
    const strengths: string[] = [];
    const gaps: string[] = [];
    const risk_factors: string[] = [];

    // Analyze strengths
    if (candidate.resume_analysis?.technical_skills?.length > 0) {
      strengths.push(`Strong technical background with ${candidate.resume_analysis.technical_skills.length} relevant skills`);
    }
    
    if (candidate.resume_analysis?.years_experience >= (jobDesc.years_experience || 0)) {
      strengths.push(`Meets experience requirements with ${candidate.resume_analysis.years_experience} years`);
    }

    if (candidate.resume_analysis?.leadership_scope?.has_leadership) {
      strengths.push("Demonstrated leadership experience");
    }

    // Analyze gaps
    if (candidate.resume_analysis?.years_experience < (jobDesc.years_experience || 0)) {
      gaps.push(`May need ${(jobDesc.years_experience || 0) - candidate.resume_analysis.years_experience} more years of experience`);
    }

    // Risk factors
    if (score < 70) {
      risk_factors.push("Below average match score");
    }

    const assessment = score >= 80 ? "Excellent match" :
                     score >= 70 ? "Good match with minor gaps" :
                     score >= 60 ? "Moderate match, requires development" :
                     "Significant gaps identified";

    return {
      overall_assessment: assessment,
      strengths,
      gaps,
      risk_factors
    };
  }

  private generateInsights(matches: CandidateMatch[], jobDesc: JobDescription): SearchInsights {
    const totalCandidates = matches.length;
    const avgScore = totalCandidates > 0 ? 
      matches.reduce((sum, m) => sum + m.score, 0) / totalCandidates : 0;

    // Extract top skills
    const skillsFrequency: Record<string, number> = {};
    matches.forEach(match => {
      const skills = match.candidate.resume_analysis?.technical_skills || [];
      skills.forEach((skill: string) => {
        skillsFrequency[skill] = (skillsFrequency[skill] || 0) + 1;
      });
    });

    const topSkills = Object.entries(skillsFrequency)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 5)
      .map(([skill]) => skill);

    return {
      total_candidates: totalCandidates,
      avg_match_score: avgScore,
      top_skills_matched: topSkills,
      market_analysis: `Found ${totalCandidates} candidates with average match score of ${avgScore.toFixed(1)}%`,
      recommendations: [
        totalCandidates > 0 ? "Consider interviewing top 3 candidates" : "Consider expanding search criteria",
        avgScore > 80 ? "Strong candidate pool available" : "May need to adjust requirements"
      ]
    };
  }

  /**
   * Cache search results
   */
  async cacheSearchResults(jobDesc: JobDescription, results: SearchResults): Promise<void> {
    const cacheKey = this.generateCacheKey(jobDesc);
    this.cache.set(cacheKey, results);
    
    // Optional: Store in Firestore for persistent caching
    try {
      await this.firestore
        .collection("search_cache")
        .doc(cacheKey)
        .set({
          ...results,
          cached_at: admin.firestore.FieldValue.serverTimestamp(),
          expires_at: new Date(Date.now() + 60 * 60 * 1000) // 1 hour
        });
    } catch (error) {
      console.warn("Failed to cache results in Firestore:", error);
    }
  }

  /**
   * Get cached search results
   */
  async getCachedResults(jobDesc: JobDescription): Promise<SearchResults | null> {
    const cacheKey = this.generateCacheKey(jobDesc);
    
    // Check in-memory cache first
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey)!;
    }

    // Check Firestore cache
    try {
      const cacheDoc = await this.firestore
        .collection("search_cache")
        .doc(cacheKey)
        .get();

      if (cacheDoc.exists) {
        const data = cacheDoc.data()!;
        if (data.expires_at.toDate() > new Date()) {
          return data as SearchResults;
        }
      }
    } catch (error) {
      console.warn("Failed to retrieve cached results:", error);
    }

    return null;
  }

  private generateCacheKey(jobDesc: JobDescription): string {
    const keyData = {
      title: jobDesc.title,
      required_skills: jobDesc.required_skills.sort(),
      years_experience: jobDesc.years_experience
    };
    
    return Buffer.from(JSON.stringify(keyData))
      .toString('base64')
      .replace(/[+/=]/g, '')
      .substring(0, 32);
  }
}