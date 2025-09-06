export interface JobDescription {
  title: string;
  company: string;
  description: string;
  required_skills?: string[];
  nice_to_have?: string[];
  min_experience?: number;
  max_experience?: number;
  leadership_required?: boolean;
}

export interface CandidateProfile {
  candidate_id: string;
  name: string;
  resume_analysis: {
    career_trajectory: {
      current_level: string;
      progression_speed: string;
      trajectory_type: string;
      domain_expertise: string[];
    };
    leadership_scope?: {
      has_leadership: boolean;
      team_size?: number;
      leadership_level?: string;
    };
    company_pedigree: {
      tier_level: string;
      company_types: string[];
      recent_companies: string[];
    };
    years_experience: number;
    technical_skills: string[];
    soft_skills: string[];
    education: {
      highest_degree: string;
      institutions: string[];
    };
  };
  recruiter_insights?: {
    strengths: string[];
    key_themes: string[];
    recommendation: string;
  };
  overall_score: number;
}

export interface MatchRationale {
  strengths: string[];
  gaps: string[];
  risk_factors: string[];
  overall_assessment: string;
}

export interface CandidateMatch {
  candidate: CandidateProfile;
  score: number;
  similarity: number;
  rationale: MatchRationale;
}

export interface SearchInsights {
  total_candidates: number;
  avg_match_score: number;
  top_skills_matched: string[];
  common_gaps: string[];
  market_analysis: string;
  recommendations: string[];
}

export interface SearchResponse {
  success: boolean;
  matches: CandidateMatch[];
  insights: SearchInsights;
  query_time_ms: number;
}

export interface QuickMatchResult {
  candidate_id: string;
  name: string;
  score: number;
  summary: string;
}