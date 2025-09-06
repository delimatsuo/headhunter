/**
 * Cloud Functions for Headhunter AI
 * Data enrichment pipeline using Vertex AI Gemini
 */

import { onObjectFinalized } from "firebase-functions/v2/storage";
import { onCall, HttpsError } from "firebase-functions/v2/https";
import { setGlobalOptions } from "firebase-functions/v2";
import * as admin from "firebase-admin";
import { Storage } from "@google-cloud/storage";
import * as aiplatform from "@google-cloud/aiplatform";
import { z } from "zod";
import { VectorSearchService } from "./vector-search";

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

// Vertex AI client
const client = new aiplatform.v1.PredictionServiceClient({
  apiEndpoint: "us-central1-aiplatform.googleapis.com",
});

// Vector Search service
const vectorSearchService = new VectorSearchService();

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
 * Enhanced career analysis prompt for Vertex AI Gemini
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
 * Call Vertex AI Gemini for profile enrichment
 */
async function enrichProfileWithGemini(profile: CandidateProfile): Promise<EnrichedProfile["enrichment"]> {
  const projectId = process.env.GOOGLE_CLOUD_PROJECT || "headhunter-ai-0088";
  const location = "us-central1";
  const model = "gemini-1.5-pro";

  const prompt = createEnrichmentPrompt(profile);

  try {
    // For now, create a mock enrichment response
    // In production, this would call the actual Vertex AI API
    const mockEnrichment = {
      career_analysis: {
        trajectory_insights: `Based on the candidate's ${profile.resume_analysis?.years_experience || 0} years of experience and ${profile.resume_analysis?.career_trajectory.current_level || "unknown"} level, they show ${profile.resume_analysis?.career_trajectory.progression_speed || "moderate"} career progression with strong technical foundation.`,
        growth_potential: `High growth potential indicated by ${profile.resume_analysis?.leadership_scope.has_leadership ? "existing leadership experience" : "individual contributor track record"} and technical expertise in ${profile.resume_analysis?.technical_skills?.slice(0, 3).join(", ") || "multiple areas"}.`,
        leadership_readiness: profile.resume_analysis?.leadership_scope.has_leadership 
          ? `Demonstrated leadership with team of ${profile.resume_analysis.leadership_scope.team_size || "unknown size"} and ${profile.resume_analysis.leadership_scope.mentorship_experience ? "mentorship experience" : "management focus"}.`
          : "Ready for leadership transition based on technical expertise and domain knowledge.",
        market_positioning: `Competitive positioning in ${profile.resume_analysis?.company_pedigree.tier_level || "industry"} companies with ${profile.resume_analysis?.company_pedigree.brand_recognition || "solid"} brand recognition and ${profile.recruiter_insights?.sentiment || "positive"} recruiter feedback.`,
      },
      strategic_fit: {
        role_alignment_score: Math.min(95, Math.max(60, (profile.overall_score || 0.7) * 100)),
        cultural_match_indicators: [
          ...(profile.resume_analysis?.cultural_signals || ["Professional growth orientation"]),
          ...(profile.recruiter_insights?.cultural_fit?.values_alignment || ["Team collaboration"])
        ],
        development_recommendations: [
          ...(profile.recruiter_insights?.development_areas || ["Continue technical growth"]),
          "Expand strategic thinking",
          "Build industry network"
        ],
        competitive_positioning: `Strong competitive position with ${profile.resume_analysis?.technical_skills?.length || 0}+ technical skills, ${profile.resume_analysis?.company_pedigree.recent_companies?.join(" and ") || "solid company"} experience, and ${profile.recruiter_insights?.recommendation || "positive"} recommendation.`
      },
      ai_summary: `${profile.resume_analysis?.career_trajectory.current_level || "Experienced"} professional with ${profile.resume_analysis?.years_experience || 0} years in ${profile.resume_analysis?.career_trajectory.domain_expertise?.[0] || "technology"}, demonstrating ${profile.recruiter_insights?.recommendation === "strong_hire" ? "exceptional" : "strong"} capabilities and ${profile.recruiter_insights?.cultural_fit?.cultural_alignment || "good"} cultural alignment. ${profile.resume_analysis?.leadership_scope.has_leadership ? "Proven leadership experience" : "Ready for leadership opportunities"} with ${profile.recruiter_insights?.readiness_level || "immediate"} availability.`,
      enrichment_timestamp: new Date().toISOString(),
      enrichment_version: "1.0-mock",
    };

    // Log the prompt for debugging (in production, you'd call Vertex AI here)
    console.log("Enrichment prompt created for candidate:", profile.candidate_id);
    console.log("Prompt length:", prompt.length);

    return mockEnrichment;

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
    bucket: `${process.env.GOOGLE_CLOUD_PROJECT}-profiles`, // headhunter-ai-0088-profiles
    memory: "512MiB",
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
    memory: "256MiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    try {
      // Test Firestore connection
      await firestore.collection("health").doc("test").set({
        timestamp: admin.firestore.FieldValue.serverTimestamp(),
      });

      // Test Storage connection
      const bucketName = `${process.env.GOOGLE_CLOUD_PROJECT}-profiles`;
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
    memory: "512MiB",
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

/**
 * Search candidates endpoint (basic implementation)
 */
export const searchCandidates = onCall(
  {
    memory: "256MiB",
    timeoutSeconds: 30,
  },
  async (request) => {
    const { query, limit = 20 } = request.data;

    try {
      let candidatesQuery: admin.firestore.Query = firestore.collection("candidates");

      // Apply filters based on query parameters
      if (query?.min_years_experience) {
        candidatesQuery = candidatesQuery.where(
          "years_experience",
          ">=",
          query.min_years_experience
        );
      }

      if (query?.current_level) {
        candidatesQuery = candidatesQuery.where(
          "current_level",
          "==",
          query.current_level
        );
      }

      if (query?.company_tier) {
        candidatesQuery = candidatesQuery.where(
          "company_tier",
          "==",
          query.company_tier
        );
      }

      // Order by overall score and limit results
      const snapshot = await candidatesQuery
        .orderBy("overall_score", "desc")
        .limit(limit)
        .get();

      const candidates = snapshot.docs.map((doc) => ({
        id: doc.id,
        ...doc.data(),
      }));

      return {
        success: true,
        candidates,
        total: candidates.length,
      };
    } catch (error) {
      console.error("Error searching candidates:", error);
      throw new HttpsError("internal", "Failed to search candidates");
    }
  }
);

/**
 * Semantic search endpoint using vector similarity
 */
export const semanticSearch = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    const { query_text, filters, limit = 20 } = request.data;

    if (!query_text) {
      throw new HttpsError("invalid-argument", "Query text is required");
    }

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

/**
 * Generate embedding for a single profile (manual/testing)
 */
export const generateEmbedding = onCall(
  {
    memory: "256MiB",
    timeoutSeconds: 120,
  },
  async (request) => {
    const { candidate_id } = request.data;

    if (!candidate_id) {
      throw new HttpsError("invalid-argument", "Candidate ID is required");
    }

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
    memory: "256MiB",
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