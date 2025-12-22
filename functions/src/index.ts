/**
 * Cloud Functions for Headhunter AI
 * Data management pipeline using local Llama 3.1 8b processing
 */

import { onObjectFinalized } from "firebase-functions/v2/storage";
import { onCall, HttpsError } from "firebase-functions/v2/https";
import { setGlobalOptions } from "firebase-functions/v2";
import * as admin from "firebase-admin";
import { Storage } from "@google-cloud/storage";
// Local processing - no external AI dependencies
import { z } from "zod";
import { VectorSearchService } from "./vector-search";
import { AnalysisService } from "./analysis-service";
import { BUCKET_PROFILES } from "./config";
import { JobSearchService, JobDescription } from "./job-search";
// Temporarily comment out until modules are properly exported
// import { errorHandler } from "./error-handler";
import { getAuditLogger, AuditAction } from "./audit-logger";

// Initialize Firebase Admin
admin.initializeApp();

// Set global options
// setGlobalOptions({
//   region: "us-central1",
//   maxInstances: 10,
// });

// Initialize clients
const storage = new Storage();
const firestore = admin.firestore();

// Local processing client - data management only

// Vector Search service
const vectorSearchService = new VectorSearchService();

// Job Search service
const jobSearchService = new JobSearchService();

// Types and schemas
const CandidateProfileSchema = z.object({
  candidate_id: z.string(),
  name: z.string().optional(),
  resume_analysis: z.object({
    career_trajectory: z.object({
      current_level: z.string(),
      progression_speed: z.string(),
      trajectory_type: z.string(),
      career_changes: z.number().optional(),
      domain_expertise: z.array(z.string()).optional(),
    }),
    leadership_scope: z.object({
      has_leadership: z.boolean(),
      team_size: z.number().optional(),
      leadership_level: z.string().optional(),
      leadership_style: z.array(z.string()).optional(),
      mentorship_experience: z.boolean().optional(),
    }),
    company_pedigree: z.object({
      tier_level: z.string(),
      company_types: z.array(z.string()).optional(),
      brand_recognition: z.string().optional(),
      recent_companies: z.array(z.string()).optional(),
    }),
    years_experience: z.number(),
    technical_skills: z.array(z.string()),
    soft_skills: z.array(z.string()).optional(),
    education: z.object({
      highest_degree: z.string().optional(),
      institutions: z.array(z.string()).optional(),
      fields_of_study: z.array(z.string()).optional(),
    }).optional(),
    cultural_signals: z.array(z.string()).optional(),
  }).optional(),
  recruiter_insights: z.object({
    sentiment: z.string(),
    strengths: z.array(z.string()),
    concerns: z.array(z.string()).optional(),
    red_flags: z.array(z.string()).optional(),
    leadership_indicators: z.array(z.string()).optional(),
    cultural_fit: z.object({
      cultural_alignment: z.string(),
      work_style: z.array(z.string()).optional(),
      values_alignment: z.array(z.string()).optional(),
      team_fit: z.string().optional(),
      communication_style: z.string().optional(),
      adaptability: z.string().optional(),
      cultural_add: z.array(z.string()).optional(),
    }).optional(),
    recommendation: z.string(),
    readiness_level: z.string(),
    key_themes: z.array(z.string()).optional(),
    development_areas: z.array(z.string()).optional(),
    competitive_advantages: z.array(z.string()).optional(),
  }).optional(),
  overall_score: z.number().optional(),
  recommendation: z.string().optional(),
  processing_timestamp: z.string().optional(),
});

type CandidateProfile = z.infer<typeof CandidateProfileSchema>;

interface EnrichedProfile extends CandidateProfile {
  enrichment: {
    career_analysis: {
      trajectory_insights: string;
      growth_potential: string;
      leadership_readiness: string;
      market_positioning: string;
    };
    strategic_fit: {
      role_alignment_score: number;
      cultural_match_indicators: string[];
      development_recommendations: string[];
      competitive_positioning: string;
    };
    ai_summary: string;
    enrichment_timestamp: string;
    enrichment_version: string;
  };
}

/**
 * Enhanced career analysis using local processing results
 */
// Gemini enrichment removed. Enrichment is handled by Python Together processors.

/**
 * Storage trigger: Process uploaded candidate profiles
 */
export const processUploadedProfile = onObjectFinalized(
  {
    bucket: BUCKET_PROFILES,
    memory: "1GiB",
    timeoutSeconds: 540, // 9 minutes
    retry: true,
  },
  async (event) => {
    const filePath = event.data.name;
    const bucket = event.data.bucket;

    console.log(`Processing uploaded file: ${filePath} in bucket: ${bucket}`);

    // Only process JSON files in the profiles/ directory
    if (!filePath.endsWith(".json") || !filePath.startsWith("profiles/")) {
      console.log(`Skipping file: ${filePath} - not a profile JSON`);
      return;
    }

    try {
      // Download the file from Cloud Storage
      const file = storage.bucket(bucket).file(filePath);
      const [fileContents] = await file.download();
      const profileData = JSON.parse(fileContents.toString());

      // Validate the profile data
      const profile = CandidateProfileSchema.parse(profileData);

      console.log(`Processing candidate: ${profile.candidate_id}`);

      // Check if already enriched
      const existingDoc = await firestore
        .collection("enriched_profiles")
        .doc(profile.candidate_id)
        .get();

      if (existingDoc.exists) {
        console.log(`Profile ${profile.candidate_id} already enriched, skipping`);
        return;
      }

      // Perform intelligent analysis using Vertex AI
      console.log(`Starting intelligent analysis for: ${profile.candidate_id}`);
      const analysisService = new AnalysisService();

      try {
        const analysis = await analysisService.analyzeCandidate(profileData);

        // Create enriched profile
        const enrichedProfile = {
          ...profile,
          intelligent_analysis: analysis,
          // Ensure original data is preserved
          original_data: {
            experience: profileData.experience,
            education: profileData.education,
            comments: profileData.comments
          },
          // Map extracted fields to top-level for easier access
          linkedin_url: analysis.personal_details?.linkedin || (profile as any).linkedin_url,
          processing_metadata: {
            timestamp: admin.firestore.FieldValue.serverTimestamp(),
            processor: "cloud_functions_vertex_ai",
            model: "gemini-2.5-flash-001"
          }
        };

        // Store in enriched_profiles
        await firestore
          .collection("enriched_profiles")
          .doc(profile.candidate_id)
          .set(enrichedProfile);

        // Also update the main candidates collection for search
        await firestore
          .collection("candidates")
          .doc(profile.candidate_id)
          .set(enrichedProfile, { merge: true });

        console.log(`Successfully enriched and stored profile for: ${profile.candidate_id}`);

      } catch (analysisError: any) {
        console.error(`Error analyzing profile ${profile.candidate_id}:`, analysisError);
        // Fallback: store without analysis but with original data
        await firestore
          .collection("candidates")
          .doc(profile.candidate_id)
          .set({
            ...profile,
            original_data: {
              experience: profileData.experience,
              education: profileData.education
            },
            processing_error: analysisError.message
          }, { merge: true });
      }
    } catch (error) {
      console.error(`Error processing profile ${filePath}:`, error);
      throw error; // This will trigger retry if retry is enabled
    }
  }
);

/**
 * Health check endpoint
 */
export const healthCheck = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    try {
      // Test Firestore connection
      await firestore.collection("health").doc("test").set({
        timestamp: admin.firestore.FieldValue.serverTimestamp(),
      });

      // Test Storage connection
      const bucket = storage.bucket(BUCKET_PROFILES);
      const [exists] = await bucket.exists();

      const resp = {
        status: "healthy",
        timestamp: new Date().toISOString(),
        services: {
          firestore: "connected",
          storage: exists ? "bucket_exists" : "bucket_missing",
          vertex_ai: "configured",
        },
        project: process.env.GOOGLE_CLOUD_PROJECT,
        region: "us-central1",
      };

      await getAuditLogger().logApiCall("healthCheck", request.auth?.uid, {}, "success");
      return resp;
    } catch (error) {
      console.error("Health check failed:", error);
      await getAuditLogger().logApiCall("healthCheck", request.auth?.uid, {}, "error");
      throw new HttpsError("internal", "Health check failed");
    }
  }
);

/**
 * Manual enrichment endpoint for testing
 */
export const enrichProfile = onCall(
  {
    memory: "1GiB",
    timeoutSeconds: 300,
  },
  async (request) => {
    const { profile } = request.data;

    if (!profile || !profile.candidate_id) {
      throw new HttpsError("invalid-argument", "Profile data with candidate_id is required");
    }

    try {
      console.log(`Manual enrichment requested for: ${profile.candidate_id}`);
      const analysisService = new AnalysisService();
      const analysis = await analysisService.analyzeCandidate(profile);

      // Create enriched profile
      const enrichedProfile = {
        ...profile,
        intelligent_analysis: analysis,
        // Ensure original data is preserved
        original_data: {
          experience: profile.experience || profile.original_data?.experience,
          education: profile.education || profile.original_data?.education,
          comments: profile.comments || profile.original_data?.comments
        },
        // Map extracted fields to top-level
        linkedin_url: analysis.personal_details?.linkedin || profile.linkedin_url,
        processing_metadata: {
          timestamp: admin.firestore.FieldValue.serverTimestamp(),
          processor: "cloud_functions_manual_trigger",
          model: "gemini-2.5-flash-001"
        }
      };

      // Store in enriched_profiles
      await firestore
        .collection("enriched_profiles")
        .doc(profile.candidate_id)
        .set(enrichedProfile);

      // Also update the main candidates collection for search
      await firestore
        .collection("candidates")
        .doc(profile.candidate_id)
        .set(enrichedProfile, { merge: true });

      return { success: true, candidate_id: profile.candidate_id };

    } catch (error: any) {
      console.error("Error enriching profile:", error);
      throw new HttpsError("internal", error.message || "Enrichment failed");
    }
  }
);

// Removed duplicate searchCandidates function - using the one from candidates-crud.ts

// Input validation schema for semantic search
const SemanticSearchInputSchema = z.object({
  query_text: z.string().min(1).max(1000),
  filters: z.object({
    min_years_experience: z.number().min(0).max(50).optional(),
    current_level: z.string().max(100).optional(),
    company_tier: z.string().max(100).optional(),
    min_score: z.number().min(0).max(1).optional(),
  }).optional(),
  limit: z.number().min(1).max(100).optional().default(20),
});

import { defineSecret } from "firebase-functions/params";

const dbPostgresPassword = defineSecret("db-postgres-password");

/**
 * Semantic search endpoint using vector similarity
 */
export const semanticSearch = onCall(
  {
    memory: "1GiB",
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

    // Validate input
    let validatedInput;
    try {
      validatedInput = SemanticSearchInputSchema.parse(request.data);
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
      }
      throw new HttpsError("invalid-argument", "Invalid request data");
    }

    const { query_text, filters, limit } = validatedInput;

    try {
      console.log(`Performing semantic search for: "${query_text}"`);

      const searchQuery = {
        query_text,
        filters,
        limit,
      };

      const results = await vectorSearchService.searchSimilar(searchQuery);

      // Enhance results with full candidate data
      const enhancedResults = await Promise.all(
        results.map(async (result) => {
          try {
            const candidateDoc = await firestore
              .collection("candidates")
              .doc(result.candidate_id)
              .get();

            const candidateData = candidateDoc.exists ? candidateDoc.data() : null;

            return {
              candidate_id: result.candidate_id,
              similarity_score: Math.round(result.similarity_score * 100) / 100,
              match_reasons: result.match_reasons,
              candidate_data: candidateData,
              metadata: result.metadata,
            };
          } catch (error) {
            console.error(`Error fetching candidate ${result.candidate_id}:`, error);
            return {
              candidate_id: result.candidate_id,
              similarity_score: result.similarity_score,
              match_reasons: result.match_reasons,
              candidate_data: null,
              metadata: result.metadata,
            };
          }
        })
      );

      return {
        success: true,
        query: query_text,
        results: enhancedResults,
        total: enhancedResults.length,
        search_type: "semantic",
      };
    } catch (error) {
      console.error("Error in semantic search:", error);
      throw new HttpsError("internal", "Failed to perform semantic search");
    }
  }
);

// Input validation schema for generate embedding
const GenerateEmbeddingInputSchema = z.object({
  candidate_id: z.string().min(1).max(100).regex(/^[a-zA-Z0-9_-]+$/, "Invalid candidate ID format"),
});

/**
 * Generate embedding for a single profile (manual/testing)
 */
export const generateEmbedding = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 120,
  },
  async (request) => {
    // Validate input
    let validatedInput;
    try {
      validatedInput = GenerateEmbeddingInputSchema.parse(request.data);
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
      }
      throw new HttpsError("invalid-argument", "Invalid request data");
    }

    const { candidate_id } = validatedInput;

    try {
      // Get the enriched profile
      const profileDoc = await firestore
        .collection("enriched_profiles")
        .doc(candidate_id)
        .get();

      if (!profileDoc.exists) {
        throw new HttpsError("not-found", "Candidate profile not found");
      }

      const profile = profileDoc.data();
      const embedding = await vectorSearchService.storeEmbedding(profile);

      return {
        success: true,
        candidate_id,
        embedding_generated: true,
        embedding_text_length: embedding.embedding_text.length,
        vector_dimensions: embedding.embedding_vector.length,
        metadata: embedding.metadata,
      };
    } catch (error) {
      console.error(`Error generating embedding for ${candidate_id}:`, error);
      throw new HttpsError("internal", "Failed to generate embedding");
    }
  }
);

/**
 * Vector search statistics endpoint
 */
export const vectorSearchStats = onCall(
  {
    memory: "1GiB",
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
      const vectorService = new VectorSearchService();
      // Only run health check to avoid OOM from stats queries
      const healthCheck = await vectorService.healthCheck();

      return {
        healthCheck,
        message: "Stats disabled temporarily due to OOM"
      };
    } catch (error) {
      console.error("Error getting vector search stats:", error);
      throw new HttpsError("internal", "Failed to get statistics");
    }
  }
);

/**
 * Main job search endpoint - accepts job descriptions and returns ranked candidates
 */
// Input validation schema for job search
const JobSearchInputSchema = z.object({
  job_description: z.object({
    title: z.string().min(1).max(200),
    description: z.string().max(5000).optional(),
    required_skills: z.array(z.string().max(100)).max(20).optional(),
    preferred_skills: z.array(z.string().max(100)).max(20).optional(),
    years_experience: z.number().min(0).max(50).optional(),
    education_level: z.string().max(100).optional(),
    company_type: z.string().max(100).optional(),
    team_size: z.number().min(0).max(10000).optional(),
    location: z.string().max(200).optional(),
    salary_range: z.object({
      min: z.number().min(0).max(1000000).optional(),
      max: z.number().min(0).max(1000000).optional(),
    }).optional(),
  }),
  limit: z.number().min(1).max(100).optional().default(20),
  use_cache: z.boolean().optional().default(true),
});

export const searchJobCandidates = onCall(
  {
    memory: "1GiB",
    timeoutSeconds: 120,
  },
  async (request) => {
    // const startTime = Date.now();

    // Check if user is authenticated
    if (!request.auth) {
      // await auditLogger.logAuth("failed", undefined, undefined, "No authentication provided");
      throw new HttpsError("unauthenticated", "Authentication required to search candidates");
    }

    // const userId = request.auth.uid;
    // const userEmail = request.auth.token.email;

    // Validate and sanitize input
    let validatedInput;
    try {
      validatedInput = JobSearchInputSchema.parse(request.data);
    } catch (error) {
      // await auditLogger.log(AuditAction.ERROR_OCCURRED, {
      //   userId,
      //   errorMessage: error instanceof z.ZodError ? error.errors[0].message : "Invalid request data",
      //   details: { function: "searchJobCandidates", validation_error: true },
      // });

      if (error instanceof z.ZodError) {
        throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
      }
      throw new HttpsError("invalid-argument", "Invalid request data");
    }

    const { job_description, limit, use_cache } = validatedInput;

    // Convert to JobDescription type
    const jobDesc: JobDescription = {
      title: job_description.title,
      description: job_description.description || "",
      required_skills: job_description.required_skills || [],
      preferred_skills: job_description.preferred_skills || [],
      years_experience: job_description.years_experience,
      education_level: job_description.education_level,
      company_type: job_description.company_type,
      team_size: job_description.team_size,
      location: job_description.location,
      salary_range: job_description.salary_range,
    };

    try {
      console.log(`Processing job search for: ${jobDesc.title}`);

      // Check cache if enabled
      if (use_cache) {
        const cachedResults = await jobSearchService.getCachedResults(jobDesc);
        if (cachedResults) {
          console.log("Returning cached search results");
          return {
            ...cachedResults,
            from_cache: true,
          };
        }
      }

      const started = Date.now();
      // Perform search
      const searchResults = await jobSearchService.searchCandidates(jobDesc, limit);

      // Cache results for future use
      if (use_cache) {
        await jobSearchService.cacheSearchResults(jobDesc, searchResults);
      }

      // const duration = Date.now() - startTime;

      // Log successful search
      // await auditLogger.logSearch(
      //   userId,
      //   "job_search",
      //   jobDesc,
      //   searchResults.matches.length,
      //   duration
      // );

      const out = {
        ...searchResults,
        from_cache: false,
      };
      await getAuditLogger().logSearch(request.auth.uid, "job_search", jobDesc, searchResults.matches.length, Date.now() - started);
      return out;
    } catch (error) {
      // const duration = Date.now() - startTime;

      // Log error
      await getAuditLogger().log(AuditAction.ERROR_OCCURRED, {
        userId: request.auth?.uid,
        resourceType: "job_search",
        errorMessage: (error as any)?.message,
        success: false,
      });

      // Handle error with error handler
      console.error("Error in job search:", error);
      throw new HttpsError("internal", "Failed to search for candidates");
    }
  }
);

/**
 * Quick match endpoint - simplified job search for quick results
 */
// Input validation schema for quick match
const QuickMatchInputSchema = z.object({
  job_title: z.string().min(1).max(200),
  skills: z.array(z.string().max(100)).max(10).optional(),
  experience_years: z.number().min(0).max(50).optional(),
  limit: z.number().min(1).max(50).optional().default(10),
});

export const quickMatch = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    // Check if user is authenticated
    if (!request.auth) {
      throw new HttpsError("unauthenticated", "Authentication required to use quick match");
    }

    // Validate and sanitize input
    let validatedInput;
    try {
      validatedInput = QuickMatchInputSchema.parse(request.data);
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
      }
      throw new HttpsError("invalid-argument", "Invalid request data");
    }

    const { job_title, skills, experience_years, limit } = validatedInput;

    try {
      // Create simplified job description
      const jobDesc: JobDescription = {
        title: job_title,
        description: `Looking for ${job_title} with ${experience_years || 3}+ years experience`,
        required_skills: skills || [],
        years_experience: experience_years || 3,
      };

      // Perform quick search
      const searchResults = await jobSearchService.searchCandidates(jobDesc, limit);

      // Return simplified results
      const simplifiedResults = {
        success: true,
        job_title: job_title,
        matches: searchResults.matches.map(match => ({
          candidate_id: match.candidate.candidate_id,
          name: match.candidate.name || 'N/A',
          score: Math.round(match.score),
          level: match.candidate.resume_analysis?.career_trajectory?.current_level || 'Unknown',
          experience: match.candidate.resume_analysis?.years_experience || 0,
          match_summary: match.rationale.overall_assessment,
          recommendation: match.score >= 80 ? 'Strong' : match.score >= 60 ? 'Moderate' : 'Weak',
        })),
        total_found: searchResults.matches.length,
        top_recommendation: searchResults.insights.recommendations[0] || 'No specific recommendations',
      };

      return simplifiedResults;
    } catch (error) {
      console.error("Error in quick match:", error);
      throw new HttpsError("internal", "Failed to perform quick match");
    }
  }
);

// Export upload functions
export { uploadCandidates, uploadCandidatesHttp } from './upload-candidates';

// Export embedding functions
export { generateAllEmbeddings, generateEmbeddingForCandidate } from './generate-embeddings';

// Export comprehensive CRUD functions
export {
  createCandidate,
  getCandidate,
  updateCandidate,
  deleteCandidate,
  searchCandidates,
  getCandidates,
  addCandidateNote,
  toggleCandidateBookmark,
  bulkCandidateOperations,
  getCandidateStats,
} from './candidates-crud';

export {
  createJob,
  getJob,
  updateJob,
  deleteJob,
  searchJobs,
  getJobs,
  duplicateJob,
  getJobStats,
} from './jobs-crud';

export {
  generateUploadUrl,
  confirmUpload,
  processUploadedFile,
  processFile,
  deleteFile,
  getUploadStats,
} from './file-upload-pipeline';

// Export user onboarding functions
export {
  handleNewUser,
  completeOnboarding,
  getOnboardingStatus,
} from './user-onboarding';

export {
  addAllowedUser,
  removeAllowedUser,
  listAllowedUsers,
  setAllowedUserRole,
} from './admin-users';

// Export skill-aware search functions
export {
  skillAwareSearch,
  getCandidateSkillAssessment,
} from './skill-aware-search';
export * from "./debug-search";

// Export REST API
export { api } from './rest-api';



// Export Organization Management
export {
  switchOrganization,
  createClientOrganization
} from './org-management';

// Export saved search functions
export {
  saveSearch,
  getSavedSearches,
  deleteSavedSearch,
} from './saved-searches';

// Export similar candidates function
export { findSimilarCandidates } from './similar-candidates';
export { analyzeSearchQuery } from './search-agent';
export { batchEnrichCandidates } from './batch-enrichment';
// Compliance and security reporting
export { getAuditReport, getSecuritySummary } from './compliance';

// Export LLM Reranking
export { rerankCandidates } from './rerank-candidates';

export { resetCandidate } from './reset-candidate';
export { verifyEnrichment } from './verify-enrichment';
export { getMainOrgId, addUserToOrg } from './user-helpers';
export { initAgencyModel } from './init-agency';
export { migrateCandidates } from './migrate-candidates';

// CSV Import for bulk candidate import
export { importCandidatesCSV, suggestColumnMapping } from './import-candidates-csv';
// Export debug CPO count
export { countCPO } from './count-cpo-function';

// Export Job Analysis (Strategy Phase)
export { analyzeJob } from './analyze-job';

// Export AI Engine Search (Modular Search Engines)
export { engineSearch, getAvailableEngines } from './engine-search';

// Export Backfill Classifications (one-time migration)
export { backfillClassifications, getClassificationStats } from './backfill-classifications';

// Export LLM-Based Multi-Function Classification Backfill
export { backfillLLMClassifications, getLLMClassificationStats } from './backfill-llm-classification';
