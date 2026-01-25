/**
 * Skill-Aware Search API for Headhunter AI
 * Combines vector similarity with skill probability assessment
 */

import { onCall, HttpsError } from "firebase-functions/v2/https";
import * as admin from "firebase-admin";
import { z } from "zod";
import { VectorSearchService } from "./vector-search";
import { normalizeSkillName } from "./shared/skills-service";

// Types and schemas for skill-aware search
const SkillRequirementSchema = z.object({
  skill: z.string(),
  minimum_confidence: z.number().min(0).max(100).default(70),
  weight: z.number().min(0).max(1).default(1.0),
  category: z.enum(["technical", "soft", "leadership", "domain"]).optional()
});

const SearchQuerySchema = z.object({
  text_query: z.string(),
  required_skills: z.array(SkillRequirementSchema).default([]),
  preferred_skills: z.array(SkillRequirementSchema).default([]),
  experience_level: z.enum(["entry", "mid", "senior", "executive"]).optional(),
  minimum_overall_confidence: z.number().min(0).max(100).default(70),
  filters: z.object({
    min_years_experience: z.number().optional(),
    current_level: z.string().optional(),
    company_tier: z.string().optional(),
    min_score: z.number().optional(),
    location: z.string().optional()
  }).optional(),
  limit: z.number().min(1).max(300).default(20), // Increased for recruiter workflow
  offset: z.number().min(0).default(0),
  org_id: z.string().optional(),
  ranking_weights: z.object({
    skill_match: z.number().min(0).max(1).default(0.4),
    confidence: z.number().min(0).max(1).default(0.25),
    vector_similarity: z.number().min(0).max(1).default(0.2),
    experience_match: z.number().min(0).max(1).default(0.15)
  }).optional()
});

const SkillAnalysisSchema = z.object({
  skill: z.string(),
  confidence: z.number().min(0).max(100),
  evidence: z.array(z.string()).default([]),
  category: z.string().default("technical")
});

const InferredSkillSchema = z.object({
  skill: z.string(),
  confidence: z.number().min(0).max(100),
  reasoning: z.string(),
  skill_category: z.string().default("technical")
});

const ExplicitSkillsSchema = z.object({
  technical_skills: z.array(SkillAnalysisSchema).default([]),
  tools_technologies: z.array(SkillAnalysisSchema).default([]),
  soft_skills: z.array(SkillAnalysisSchema).default([]),
  certifications: z.array(SkillAnalysisSchema).default([]),
  languages: z.array(SkillAnalysisSchema).default([])
});

const InferredSkillsSchema = z.object({
  highly_probable_skills: z.array(InferredSkillSchema).default([]),
  probable_skills: z.array(InferredSkillSchema).default([]),
  likely_skills: z.array(InferredSkillSchema).default([]),
  possible_skills: z.array(InferredSkillSchema).default([])
});

type SearchQuery = z.infer<typeof SearchQuerySchema>;
type SkillRequirement = z.infer<typeof SkillRequirementSchema>;
type SkillAnalysis = z.infer<typeof SkillAnalysisSchema>;

interface CandidateScore {
  candidate_id: string;
  overall_score: number;
  skill_match_score: number;
  confidence_score: number;
  vector_similarity_score: number;
  experience_match_score: number;
  skill_breakdown: Record<string, number>;
  ranking_factors: {
    skill_match_details: Record<string, any>;
    confidence_analysis: Record<string, any>;
    experience_analysis: string;
    vector_similarity: number;
  };
  profile?: {
    name?: string;
    current_role?: string;
    current_company?: string;
    years_experience?: number;
    current_level?: string;
    analysis_confidence?: number;
    top_skills?: Array<{ skill: string; confidence: number }>;
    summary?: string;
  };
  rationale?: string[];
}

interface SearchResult {
  candidates: CandidateScore[];
  query_analysis: {
    parsed_requirements: any;
    search_strategy: Record<string, string>;
    ranking_weights: Record<string, number>;
  };
  search_metadata: {
    total_candidates_evaluated: number;
    search_time_ms: number;
    vector_search_results: number;
    skill_filtering_applied: boolean;
  };
}

class SkillAwareSearchService {
  private firestore: admin.firestore.Firestore;
  private vectorSearchService: VectorSearchService;

  constructor() {
    this.firestore = admin.firestore();
    this.vectorSearchService = new VectorSearchService();
  }


  /**
   * Extract skill profile from candidate data
   */
  private extractSkillProfile(candidateData: any): {
    skills: Record<string, { confidence: number; category: string; evidence: string[] }>;
    average_confidence: number;
    skill_categories: Record<string, number>;
  } {
    const skills: Record<string, { confidence: number; category: string; evidence: string[] }> = {};
    const skillCategories: Record<string, number> = {};

    try {
      const analysis = candidateData.recruiter_analysis;
      if (!analysis) {
        return { skills, average_confidence: 0, skill_categories: skillCategories };
      }

      // Process explicit skills
      if (analysis.explicit_skills) {
        const explicit = analysis.explicit_skills;
        const skillTypes = [
          { list: explicit.technical_skills, category: "technical" },
          { list: explicit.tools_technologies, category: "technical" },
          { list: explicit.soft_skills, category: "soft" },
          { list: explicit.certifications, category: "technical" },
          { list: explicit.languages, category: "soft" }
        ];

        for (const { list, category } of skillTypes) {
          if (Array.isArray(list)) {
            for (const skillObj of list) {
              const skillName = normalizeSkillName(skillObj.skill || skillObj);
              const confidence = skillObj.confidence || 100;
              const evidence = skillObj.evidence || [];

              skills[skillName] = { confidence, category, evidence };
              skillCategories[category] = (skillCategories[category] || 0) + 1;
            }
          }
        }
      }

      // Process inferred skills
      if (analysis.inferred_skills) {
        const inferred = analysis.inferred_skills;
        const inferredTypes = [
          analysis.inferred_skills.highly_probable_skills || [],
          analysis.inferred_skills.probable_skills || [],
          analysis.inferred_skills.likely_skills || [],
          analysis.inferred_skills.possible_skills || []
        ];

        for (const skillList of inferredTypes) {
          if (Array.isArray(skillList)) {
            for (const skillObj of skillList) {
              const skillName = normalizeSkillName(skillObj.skill);
              const confidence = skillObj.confidence;
              const category = skillObj.skill_category || "technical";

              // Only add if not already present with higher confidence
              if (!skills[skillName] || skills[skillName].confidence < confidence) {
                skills[skillName] = {
                  confidence,
                  category,
                  evidence: [skillObj.reasoning || "Inferred from profile"]
                };
                skillCategories[category] = (skillCategories[category] || 0) + 1;
              }
            }
          }
        }
      }

      // Calculate average confidence
      const confidenceValues = Object.values(skills).map(s => s.confidence);
      const avgConfidence = confidenceValues.length > 0
        ? confidenceValues.reduce((a, b) => a + b, 0) / confidenceValues.length
        : 0;

      return { skills, average_confidence: avgConfidence, skill_categories: skillCategories };
    } catch (error) {
      console.error("Error extracting skill profile:", error);
      return { skills, average_confidence: 0, skill_categories: skillCategories };
    }
  }

  /**
   * Calculate skill match score
   */
  private calculateSkillMatch(candidateSkills: Record<string, any>,
    requiredSkills: SkillRequirement[]): number {
    if (requiredSkills.length === 0) {
      return 80; // Default score when no specific skills required
    }

    let totalScore = 0;
    let totalWeight = 0;

    for (const requirement of requiredSkills) {
      const normalizedSkill = normalizeSkillName(requirement.skill);
      totalWeight += requirement.weight;

      if (candidateSkills[normalizedSkill]) {
        const skillData = candidateSkills[normalizedSkill];
        if (skillData.confidence >= requirement.minimum_confidence) {
          totalScore += skillData.confidence * requirement.weight;
        } else {
          // Penalty for below threshold
          totalScore += skillData.confidence * 0.5 * requirement.weight;
        }
      } else {
        // Check for related skills
        let relatedScore = 0;
        for (const [candidateSkill, skillData] of Object.entries(candidateSkills)) {
          if (this.areSkillsRelated(normalizedSkill, candidateSkill)) {
            relatedScore = Math.max(relatedScore, skillData.confidence * 0.7);
          }
        }
        totalScore += relatedScore * requirement.weight;
      }
    }

    return totalWeight > 0 ? totalScore / totalWeight : 0;
  }

  /**
   * Check if skills are related
   */
  private areSkillsRelated(skill1: string, skill2: string): boolean {
    const skillFamilies = [
      ["python", "django", "flask", "fastapi"],
      ["javascript", "react", "angular", "vue", "node.js"],
      ["aws", "azure", "gcp", "cloud computing"],
      ["docker", "kubernetes", "containerization"],
      ["leadership", "management", "team lead", "mentoring"]
    ];

    for (const family of skillFamilies) {
      if (family.includes(skill1) && family.includes(skill2)) {
        return true;
      }
    }

    return false;
  }

  /**
   * Calculate experience match score
   * Enhanced to include title/level matching, not just years of experience
   */
  private calculateExperienceMatch(candidateData: any,
    targetLevel?: string): number {
    if (!targetLevel) {
      return 75; // Neutral score
    }

    const experienceMapping: Record<string, { yearRange: [number, number], titleKeywords: string[], weight: number }> = {
      "entry": {
        yearRange: [0, 3],
        titleKeywords: ['junior', 'entry', 'associate', 'trainee', 'intern', 'graduate'],
        weight: 0.5
      },
      "mid": {
        yearRange: [3, 7],
        titleKeywords: ['mid', 'intermediate', 'engineer', 'developer', 'analyst', 'specialist'],
        weight: 0.5
      },
      "senior": {
        yearRange: [7, 12],
        titleKeywords: ['senior', 'sr', 'lead', 'principal', 'staff', 'architect'],
        weight: 0.5
      },
      "executive": {
        yearRange: [12, 50],
        titleKeywords: ['cto', 'ceo', 'cfo', 'coo', 'cio', 'chief', 'vp', 'vice president',
          'director', 'head of', 'president', 'founder', 'co-founder',
          'partner', 'managing', 'executive', 'evp', 'svp'],
        weight: 0.7 // Higher weight for title matching at executive level
      }
    };

    const yearsExp = candidateData.recruiter_analysis?.career_trajectory_analysis?.years_experience ||
      candidateData.intelligent_analysis?.career_trajectory_analysis?.years_experience || 0;

    // Get candidate's current title/level from multiple possible sources
    const currentLevel = (
      candidateData.intelligent_analysis?.career_trajectory_analysis?.current_level ||
      candidateData.recruiter_analysis?.career_trajectory_analysis?.current_level ||
      candidateData.resume_analysis?.career_trajectory?.current_level ||
      candidateData.current_role ||
      candidateData.professional?.current_title ||
      ''
    ).toLowerCase();

    const levelConfig = experienceMapping[targetLevel] || experienceMapping["mid"];
    const [minYears, maxYears] = levelConfig.yearRange;
    const titleKeywords = levelConfig.titleKeywords;
    const titleWeight = levelConfig.weight;

    // Calculate years-based score (0-100)
    let yearsScore = 0;
    if (minYears <= yearsExp && yearsExp <= maxYears) {
      yearsScore = 100;
    } else if (yearsExp < minYears) {
      const gap = minYears - yearsExp;
      yearsScore = Math.max(30, 100 - (gap * 15)); // Steeper penalty for under-experience
    } else {
      const excess = yearsExp - maxYears;
      yearsScore = Math.max(70, 100 - (excess * 5)); // Small penalty for over-experience
    }

    // Calculate title-based score (0-100)
    let titleScore = 0;
    if (currentLevel) {
      const matchedKeywords = titleKeywords.filter(keyword =>
        currentLevel.includes(keyword)
      );

      if (matchedKeywords.length > 0) {
        // Strong title match
        titleScore = 100;
      } else {
        // Check if candidate has a different executive title when looking for executive
        if (targetLevel === 'executive') {
          const anyExecutiveKeywords = ['cto', 'ceo', 'chief', 'vp', 'vice president', 'director', 'head', 'president', 'founder'];
          const hasAnyExecutiveTitle = anyExecutiveKeywords.some(kw => currentLevel.includes(kw));
          titleScore = hasAnyExecutiveTitle ? 80 : 20; // Low score for non-executive titles
        } else {
          titleScore = 50; // Neutral for non-executive searches
        }
      }
    } else {
      titleScore = 40; // Unknown title
    }

    // Weighted combination - for executive searches, title is MORE important than years
    const yearsWeight = 1 - titleWeight;
    const finalScore = (yearsScore * yearsWeight) + (titleScore * titleWeight);

    return Math.round(finalScore);
  }

  /**
   * Score a candidate against search query
   */
  private scoreCandidateAgainstQuery(candidateData: any,
    searchQuery: SearchQuery,
    vectorSimilarity: number): CandidateScore {
    const skillProfile = this.extractSkillProfile(candidateData);
    const weights = searchQuery.ranking_weights || {
      skill_match: 0.4,
      confidence: 0.25,
      vector_similarity: 0.2,
      experience_match: 0.15
    };

    // Calculate component scores
    const skillMatchScore = this.calculateSkillMatch(skillProfile.skills, searchQuery.required_skills);
    const confidenceScore = Math.min(100, skillProfile.average_confidence);
    const experienceScore = this.calculateExperienceMatch(candidateData, searchQuery.experience_level);

    // Calculate skill breakdown
    const skillBreakdown: Record<string, number> = {};
    for (const requirement of searchQuery.required_skills) {
      const normalizedSkill = normalizeSkillName(requirement.skill);
      const candidateSkill = skillProfile.skills[normalizedSkill];
      skillBreakdown[requirement.skill] = candidateSkill ? candidateSkill.confidence : 0;
    }

    // Calculate overall score
    const overallScore = (
      skillMatchScore * weights.skill_match +
      confidenceScore * weights.confidence +
      vectorSimilarity * weights.vector_similarity +
      experienceScore * weights.experience_match
    );

    return {
      candidate_id: candidateData.candidate_id,
      overall_score: overallScore,
      skill_match_score: skillMatchScore,
      confidence_score: confidenceScore,
      vector_similarity_score: vectorSimilarity,
      experience_match_score: experienceScore,
      skill_breakdown: skillBreakdown,
      ranking_factors: {
        skill_match_details: {
          required_skills_found: Object.keys(skillBreakdown).filter(skill => skillBreakdown[skill] > 0).length,
          total_required_skills: searchQuery.required_skills.length,
          avg_skill_confidence: Object.values(skillBreakdown).reduce((a, b) => a + b, 0) / Math.max(1, Object.values(skillBreakdown).length)
        },
        confidence_analysis: {
          total_skills: Object.keys(skillProfile.skills).length,
          average_confidence: skillProfile.average_confidence,
          skill_categories: skillProfile.skill_categories
        },
        experience_analysis: candidateData.recruiter_analysis?.career_trajectory_analysis?.years_experience
          ? `${candidateData.recruiter_analysis.career_trajectory_analysis.years_experience} years experience`
          : "Experience not specified",
        vector_similarity: vectorSimilarity
      }
    };
  }

  /**
   * Perform skill-aware candidate search using enhanced VectorSearchService
   */
  async searchCandidates(searchQuery: SearchQuery): Promise<SearchResult> {
    const startTime = Date.now();

    try {
      // Convert to VectorSearchService format
      const skillAwareQuery = {
        text_query: searchQuery.text_query,
        required_skills: searchQuery.required_skills,
        preferred_skills: searchQuery.preferred_skills,
        experience_level: searchQuery.experience_level,
        minimum_overall_confidence: searchQuery.minimum_overall_confidence,
        filters: searchQuery.filters,
        limit: searchQuery.limit,
        offset: searchQuery.offset,
        ranking_weights: searchQuery.ranking_weights,
        org_id: searchQuery.org_id
      };

      // Use the enhanced skill-aware search from VectorSearchService
      const vectorResults = await this.vectorSearchService.searchCandidatesSkillAware(skillAwareQuery);

      console.log(`Enhanced skill-aware search returned ${vectorResults.length} candidates`);

      // Convert VectorSearchService results to our SearchResult format
      const candidateScores: CandidateScore[] = vectorResults.map(result => ({
        candidate_id: result.candidate_id,
        overall_score: result.overall_score,
        skill_match_score: result.skill_match_score,
        confidence_score: result.confidence_score,
        vector_similarity_score: result.vector_similarity_score,
        experience_match_score: result.experience_match_score,
        skill_breakdown: result.skill_breakdown,
        ranking_factors: {
          skill_match_details: {
            required_skills_found: result.ranking_factors.required_skills_matched,
            total_required_skills: result.ranking_factors.total_required_skills,
            avg_skill_confidence: result.ranking_factors.average_skill_confidence
          },
          confidence_analysis: {
            total_skills: Object.keys(result.skill_breakdown).length,
            average_confidence: result.ranking_factors.average_skill_confidence,
            skill_categories: {} // Will be filled from skill breakdown categories
          },
          experience_analysis: result.ranking_factors.experience_alignment,
          vector_similarity: result.ranking_factors.vector_similarity
        },
        profile: result.profile,
        rationale: result.match_reasons
      }));

      const endTime = Date.now();

      const result: SearchResult = {
        candidates: candidateScores,
        query_analysis: {
          parsed_requirements: {
            required_skills: searchQuery.required_skills,
            experience_level: searchQuery.experience_level,
            minimum_confidence: searchQuery.minimum_overall_confidence
          },
          search_strategy: {
            approach: "Enhanced hybrid vector + skill confidence analysis",
            vector_query: searchQuery.text_query,
            skill_focus: searchQuery.required_skills.length > 0
              ? `Prioritizing ${searchQuery.required_skills.map(s => s.skill).join(", ")}`
              : "General skill assessment with confidence scoring"
          },
          ranking_weights: searchQuery.ranking_weights || {
            skill_match: 0.4,
            confidence: 0.25,
            vector_similarity: 0.25,
            experience_match: 0.1
          }
        },
        search_metadata: {
          total_candidates_evaluated: candidateScores.length,
          search_time_ms: endTime - startTime,
          vector_search_results: candidateScores.length,
          skill_filtering_applied: searchQuery.required_skills.length > 0 || searchQuery.minimum_overall_confidence > 0
        }
      };

      return result;

    } catch (error) {
      console.error("Error in enhanced skill-aware search:", error);
      throw error;
    }
  }
}

import { defineSecret } from "firebase-functions/params";

const dbPostgresPassword = defineSecret("db-postgres-password");

/**
 * Main skill-aware search endpoint
 */
export const skillAwareSearch = onCall(
  {
    memory: "2GiB",
    timeoutSeconds: 60,
    secrets: [dbPostgresPassword],
    vpcConnector: "svpc-us-central1",
    vpcConnectorEgressSettings: "PRIVATE_RANGES_ONLY",
  },
  async (request) => {
    // Inject DB configuration for Cloud SQL connection
    process.env.PGVECTOR_PASSWORD = dbPostgresPassword.value();
    process.env.PGVECTOR_HOST = "10.159.0.2";
    process.env.PGVECTOR_USER = "postgres";
    process.env.PGVECTOR_DATABASE = "headhunter";

    try {
      // Validate request data
      const searchQuery = SearchQuerySchema.parse(request.data);

      console.log(`Skill-aware search request:`, {
        text_query: searchQuery.text_query,
        required_skills: searchQuery.required_skills.length,
        experience_level: searchQuery.experience_level,
        limit: searchQuery.limit,
        offset: searchQuery.offset
      });

      // Perform search
      const searchService = new SkillAwareSearchService();
      const results = await searchService.searchCandidates(searchQuery);

      return {
        success: true,
        results: results,
        debug_info: {
          query_processed: true,
          candidates_found: results.candidates.length,
          search_time_ms: results.search_metadata.search_time_ms
        }
      };

    } catch (error) {
      console.error("Error in skillAwareSearch:", error);

      if (error instanceof z.ZodError) {
        throw new HttpsError("invalid-argument", `Invalid search query: ${error.message}`);
      }

      throw new HttpsError("internal", "Failed to perform skill-aware search");
    }
  }
);

/**
 * Endpoint to get skill assessment for a specific candidate
 */
export const getCandidateSkillAssessment = onCall(
  {
    memory: "256MiB",
    timeoutSeconds: 30,
  },
  async (request) => {
    const { candidate_id } = request.data;

    if (!candidate_id) {
      throw new HttpsError("invalid-argument", "candidate_id is required");
    }

    try {
      const candidateDoc = await admin.firestore()
        .collection("enriched_profiles")
        .doc(candidate_id)
        .get();

      if (!candidateDoc.exists) {
        throw new HttpsError("not-found", `Candidate ${candidate_id} not found`);
      }

      const candidateData = candidateDoc.data();
      const searchService = new SkillAwareSearchService();
      const skillProfile = (searchService as any).extractSkillProfile(candidateData);

      return {
        success: true,
        candidate_id: candidate_id,
        skill_assessment: {
          total_skills: Object.keys(skillProfile.skills).length,
          average_confidence: skillProfile.average_confidence,
          skill_categories: skillProfile.skill_categories,
          skills: skillProfile.skills,
          high_confidence_skills: Object.entries(skillProfile.skills)
            .filter(([_, data]: [string, any]) => data.confidence >= 85)
            .map(([skill, _]) => skill),
          medium_confidence_skills: Object.entries(skillProfile.skills)
            .filter(([_, data]: [string, any]) => data.confidence >= 70 && data.confidence < 85)
            .map(([skill, _]) => skill),
          low_confidence_skills: Object.entries(skillProfile.skills)
            .filter(([_, data]: [string, any]) => data.confidence < 70)
            .map(([skill, _]) => skill)
        }
      };

    } catch (error) {
      console.error("Error getting candidate skill assessment:", error);
      throw new HttpsError("internal", "Failed to get skill assessment");
    }
  }
);
