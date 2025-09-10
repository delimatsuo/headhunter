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
  id?: string;
  candidate_id?: string;
  name: string;
  title?: string;
  company?: string;
  location?: string;
  skills?: string[];
  experience?: string | number;
  education?: string;
  summary?: string;
  matchScore?: number;
  strengths?: string[];
  fitReasons?: string[];
  availability?: string;
  desiredSalary?: string;
  profileUrl?: string;
  lastUpdated?: string;
  resume_analysis?: {
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

// Authentication types
export interface User {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
}

export interface AuthContextType {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

// API Response types
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

// File upload types
export interface UploadProgress {
  progress: number;
  status: 'idle' | 'uploading' | 'completed' | 'error';
  error?: string;
}

// Dashboard analytics types
export interface DashboardStats {
  totalCandidates: number;
  averageScore?: number;
  avgMatchScore?: number;
  activeSearches: number;
  recentSearches?: number;
  topSkills: Array<{ skill: string; count: number }>;
  topCompanies?: Array<{ company: string; count: number }>;
  recentActivity?: {
    searches: number;
    newCandidates: number;
    highMatches: number;
  };
}

// Navigation types
export interface NavItem {
  name: string;
  path: string;
  icon: string;
}