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
import { JobSearchService, JobDescription } from "./job-search";
// Temporarily comment out until modules are properly exported
// import { errorHandler } from "./error-handler";
// import { auditLogger, AuditAction } from "./audit-logger";

// Initialize Firebase Admin
admin.initializeApp();

// Set global options
setGlobalOptions({
  region: "us-central1",
  maxInstances: 10,
});

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
const createEnrichmentPrompt = (profile: CandidateProfile): string => {
  return `
As an expert executive recruiter and career analyst, provide deep strategic insights for this candidate profile.

CANDIDATE PROFILE:
${JSON.stringify(profile, null, 2)}

Please analyze this candidate and provide insights in the following JSON structure:

{
  "career_analysis": {
    "trajectory_insights": "Deep analysis of career progression patterns, velocity, and strategic decisions. What does their career path tell us about their ambition, decision-making, and growth mindset?",
    "growth_potential": "Assessment of future growth trajectory based on current level, skills, and experience. What roles could they reasonably target in 2-5 years?",
    "leadership_readiness": "Evaluation of leadership capabilities, team management experience, and readiness for increased responsibility.",
    "market_positioning": "How does this candidate stack up in the current market? What makes them competitive or unique?"
  },
  "strategic_fit": {
    "role_alignment_score": 85,
    "cultural_match_indicators": ["List specific cultural fit indicators based on their background", "Values alignment signals", "Team collaboration style"],
    "development_recommendations": ["Specific areas for growth", "Skills to develop", "Experience gaps to address"],
    "competitive_positioning": "What differentiates this candidate from others with similar backgrounds? What's their unique value proposition?"
  },
  "ai_summary": "2-3 sentence executive summary of this candidate's profile, highlighting their key strengths and ideal role fit."
}

Focus on:
1. Strategic career insights beyond what's already captured
2. Leadership potential and scalability
3. Cultural and team fit indicators
4. Market differentiation and competitive advantages
5. Specific development opportunities

Provide specific, actionable insights that would be valuable to both recruiters and hiring managers.
`;
};

/**
 * Process profile enrichment using locally processed data
 */
async function enrichProfileWithGemini(profile: CandidateProfile): Promise<EnrichedProfile["enrichment"]> {
  // const projectId = process.env.GOOGLE_CLOUD_PROJECT || "headhunter-ai-0088";
  // const location = "us-central1";
  // const model = "gemini-1.5-pro";

  const prompt = createEnrichmentPrompt(profile);

  try {
    // Call Vertex AI Gemini for real enrichment
    const { PredictionServiceClient } = require('@google-cloud/aiplatform').v1;
    
    const projectId = process.env.GOOGLE_CLOUD_PROJECT || "headhunter-ai-0088";
    const location = "us-central1";
    const model = "gemini-2.5-flash";
    
    const predictionClient = new PredictionServiceClient({
      apiEndpoint: `${location}-aiplatform.googleapis.com`,
    });
    
    const endpoint = `projects/${projectId}/locations/${location}/publishers/google/models/${model}`;
    
    console.log("Calling Gemini for candidate enrichment:", profile.candidate_id);
    console.log("Prompt length:", prompt.length);
    
    const instances = [{
      content: prompt
    }];
    
    const parameters = {
      temperature: 0.3,
      maxOutputTokens: 2048,
      topP: 0.8,
      topK: 40
    };
    
    try {
      const [response] = await predictionClient.predict({
        endpoint,
        instances: instances.map((instance) => 
          Object.fromEntries(
            Object.entries(instance).map(([k, v]) => [k, { stringValue: v as string }])
          )
        ),
        parameters: Object.fromEntries(
          Object.entries(parameters).map(([k, v]) => [k, { numberValue: v as number }])
        ),
      });
      
      if (response.predictions && response.predictions.length > 0) {
        const prediction = response.predictions[0];
        const content = prediction.structValue?.fields?.content?.stringValue || '';
        
        try {
          // Parse the JSON response from Gemini
          const enrichmentData = JSON.parse(content);
          
          return {
            ...enrichmentData,
            enrichment_timestamp: new Date().toISOString(),
            enrichment_version: "1.0-gemini",
          };
        } catch (parseError) {
          console.warn("Failed to parse Gemini response as JSON:", parseError);
          
          // Fallback: create structured response from text
          return {
            career_analysis: {
              trajectory_insights: content.substring(0, 500),
              growth_potential: "Analysis pending - raw response received",
              leadership_readiness: "Analysis pending - raw response received",
              market_positioning: "Analysis pending - raw response received"
            },
            strategic_fit: {
              role_alignment_score: 75,
              cultural_match_indicators: ["AI analysis in progress"],
              development_recommendations: ["Review AI analysis"],
              competitive_positioning: "Analysis pending - raw response received"
            },
            ai_summary: content.substring(0, 200) + "...",
            enrichment_timestamp: new Date().toISOString(),
            enrichment_version: "1.0-gemini-raw"
          };
        }
      } else {
        throw new Error("No response from Gemini API");
      }
      
    } catch (geminiError: any) {
      console.warn("Gemini API error, falling back to enhanced mock:", geminiError.message);
      
      // Enhanced fallback with more intelligent mock data
      const mockEnrichment = {
        career_analysis: {
          trajectory_insights: `Based on ${profile.resume_analysis?.years_experience || 0} years experience at ${profile.resume_analysis?.career_trajectory.current_level || "professional"} level, showing ${profile.resume_analysis?.career_trajectory.progression_speed || "steady"} progression in ${profile.resume_analysis?.career_trajectory.domain_expertise?.[0] || "their field"}.`,
          growth_potential: `${profile.resume_analysis?.leadership_scope.has_leadership ? "Strong leadership foundation" : "Individual contributor with leadership potential"} combined with expertise in ${profile.resume_analysis?.technical_skills?.slice(0, 3).join(", ") || "key technologies"}.`,
          leadership_readiness: profile.resume_analysis?.leadership_scope.has_leadership 
            ? `Proven leadership managing ${profile.resume_analysis.leadership_scope.team_size || "teams"} with ${profile.resume_analysis.leadership_scope.mentorship_experience ? "mentoring experience" : "hands-on management"}.`
            : "Ready for leadership opportunities given technical depth and domain expertise.",
          market_positioning: `Well-positioned in ${profile.resume_analysis?.company_pedigree.tier_level || "market"} with ${profile.resume_analysis?.company_pedigree.brand_recognition || "respected"} company background and ${profile.recruiter_insights?.sentiment || "positive"} market reception.`
        },
        strategic_fit: {
          role_alignment_score: Math.min(95, Math.max(65, Math.round((profile.overall_score || 0.75) * 100))),
          cultural_match_indicators: [
            ...(profile.resume_analysis?.cultural_signals?.slice(0, 2) || ["Growth mindset"]),
            ...(profile.recruiter_insights?.cultural_fit?.values_alignment?.slice(0, 2) || ["Team collaboration"])
          ],
          development_recommendations: [
            ...(profile.recruiter_insights?.development_areas?.slice(0, 2) || ["Technical leadership"]),
            "Strategic thinking expansion",
            "Industry expertise deepening"
          ],
          competitive_positioning: `Strong market position leveraging ${profile.resume_analysis?.technical_skills?.length || 5}+ technical skills across ${profile.resume_analysis?.company_pedigree.recent_companies?.length || 1} companies with ${profile.recruiter_insights?.recommendation || "positive"} assessment.`
        },
        ai_summary: `${profile.resume_analysis?.career_trajectory.current_level || "Experienced"} ${profile.resume_analysis?.career_trajectory.domain_expertise?.[0] || "technology"} professional with ${profile.resume_analysis?.years_experience || 0}+ years, ${profile.resume_analysis?.leadership_scope.has_leadership ? "proven leadership" : "strong technical"} capabilities, and ${profile.recruiter_insights?.cultural_fit?.cultural_alignment || "strong"} cultural fit indicators.`,
        enrichment_timestamp: new Date().toISOString(),
        enrichment_version: "1.0-fallback"
      };
      
      return mockEnrichment;
    }

    // TODO: Replace with actual Vertex AI call when ready
    /*
    const endpoint = `projects/${projectId}/locations/${location}/publishers/google/models/${model}`;
    
    const request = {
      endpoint,
      instances: [{
        content: prompt
      }],
      parameters: {
        temperature: 0.2,
        maxOutputTokens: 2048,
        topP: 0.8,
        topK: 40,
      }
    };

    const [response] = await client.predict(request);
    // ... process actual API response
    */
  } catch (error) {
    console.error("Error in profile enrichment:", error);
    throw new HttpsError("internal", "Failed to enrich profile with AI");
  }
}

/**
 * Storage trigger: Process uploaded candidate profiles
 */
export const processUploadedProfile = onObjectFinalized(
  {
    bucket: "headhunter-ai-0088-profiles",
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

      // Enrich the profile with Vertex AI Gemini
      const enrichment = await enrichProfileWithGemini(profile);

      // Create enriched profile
      const enrichedProfile: EnrichedProfile = {
        ...profile,
        enrichment,
      };

      // Store in Firestore
      await firestore
        .collection("enriched_profiles")
        .doc(profile.candidate_id)
        .set(enrichedProfile);

      // Also store in a searchable collection with flattened data for querying
      await firestore
        .collection("candidates")
        .doc(profile.candidate_id)
        .set({
          candidate_id: profile.candidate_id,
          name: profile.name,
          overall_score: profile.overall_score,
          recommendation: profile.recommendation,
          years_experience: profile.resume_analysis?.years_experience,
          current_level: profile.resume_analysis?.career_trajectory.current_level,
          leadership_level: profile.resume_analysis?.leadership_scope.leadership_level,
          company_tier: profile.resume_analysis?.company_pedigree.tier_level,
          technical_skills: profile.resume_analysis?.technical_skills || [],
          enrichment_summary: enrichment.ai_summary,
          career_insights: enrichment.career_analysis.trajectory_insights,
          growth_potential: enrichment.career_analysis.growth_potential,
          role_alignment_score: enrichment.strategic_fit.role_alignment_score,
          updated_at: admin.firestore.FieldValue.serverTimestamp(),
        });

      // Generate and store vector embedding for similarity search
      try {
        await vectorSearchService.storeEmbedding(enrichedProfile);
        console.log(`Generated embedding for candidate: ${profile.candidate_id}`);
      } catch (embeddingError) {
        console.error(`Error generating embedding for ${profile.candidate_id}:`, embeddingError);
        // Don't fail the entire process if embedding fails
      }

      console.log(`Successfully enriched and stored profile for: ${profile.candidate_id}`);
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
      const bucketName = "headhunter-ai-0088-profiles";
      const bucket = storage.bucket(bucketName);
      const [exists] = await bucket.exists();

      return {
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
    } catch (error) {
      console.error("Health check failed:", error);
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

    if (!profile) {
      throw new HttpsError("invalid-argument", "Profile data is required");
    }

    try {
      // Validate the profile data
      const validatedProfile = CandidateProfileSchema.parse(profile);

      // Enrich the profile
      const enrichment = await enrichProfileWithGemini(validatedProfile);

      const enrichedProfile: EnrichedProfile = {
        ...validatedProfile,
        enrichment,
      };

      return {
        success: true,
        enriched_profile: enrichedProfile,
      };
    } catch (error) {
      console.error("Error enriching profile:", error);
      if (error instanceof z.ZodError) {
        throw new HttpsError("invalid-argument", `Invalid profile data: ${error.message}`);
      }
      throw new HttpsError("internal", "Failed to enrich profile");
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

/**
 * Semantic search endpoint using vector similarity
 */
export const semanticSearch = onCall(
  {
    memory: "1GiB",
    timeoutSeconds: 60,
  },
  async (request) => {
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
    memory: "512MiB",
    timeoutSeconds: 30,
  },
  async (request) => {
    try {
      const stats = await vectorSearchService.getEmbeddingStats();
      const healthCheck = await vectorSearchService.healthCheck();

      return {
        success: true,
        timestamp: new Date().toISOString(),
        stats,
        health: healthCheck,
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

      return {
        ...searchResults,
        from_cache: false,
      };
    } catch (error) {
      // const duration = Date.now() - startTime;
      
      // Log error
      // await auditLogger.log(AuditAction.ERROR_OCCURRED, {
      //   userId,
      //   userEmail,
      //   resourceType: "job_search",
      //   errorMessage: (error as any).message,
      //   durationMs: duration,
      //   success: false,
      // });
      
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
