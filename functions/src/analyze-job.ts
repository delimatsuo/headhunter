import { onCall, HttpsError } from "firebase-functions/v2/https";
import { z } from "zod";
import { geminiModel } from "./gemini-client";

const AnalyzeJobSchema = z.object({
    job_description: z.string().min(10, "Job description is too short")
});

export const analyzeJob = onCall(
    {
        memory: "1GiB", // Lightweight task
        timeoutSeconds: 60,
        region: "us-central1"
    },
    async (request) => {
        try {
            // Validate Inputs
            const { job_description } = AnalyzeJobSchema.parse(request.data);

            const prompt = `
You are a Principal Technical Recruiter & Sourcing Strategist.
Analyze this Job Description to build a "Search Strategy".

JOB DESCRIPTION:
"""
${job_description}
"""

TASK:
1. **Target Company Identification**:
   - Infer the *type* of company (e.g. "Early-stage Fintech").
   - List 5-10 REAL companies that hire similar talent.
   - *Logic*: If JD says "Stripe-like API", target Adyen, Block, Checkout.com.

2. **Tech Stack Profiling**:
   - Identify the "Core" vs "Nice-to-have" tech.
   - Define "Anti-patterns" (e.g. if Modern Stack, penalize Legacy Enterprise Java).

3. **Title Expansion**:
   - List all valid titles. (e.g. for "Staff Engineer", include "Principal", "Tech Lead", "Architect").

4. **Experience Configuration**:
   - Determine the seniority level ("IC", "Manager", "Executive").

OUTPUT SCHEMA (JSON ONLY):
{
  "job_title": "Inferred or Explicit Title",
  "summary": "1-sentence summary of the role focus",
  "sourcing_strategy": {
    "target_companies": ["Stripe", "Adyen", ...],
    "target_industries": ["Fintech", "Payments", ...],
    "tech_stack": {
      "core": ["Go", ...],
      "avoid": ["Oracle", ...]
    },
    "title_variations": ["Staff Engineer", ...]
  },
  "required_skills": ["skill1", ...],
  "experience_level": "senior"
}
`;

            console.log("Analyzing job description with Gemini...");
            const result = await geminiModel.generateContent(prompt);
            const response = await result.response;
            const text = response.candidates?.[0]?.content?.parts?.[0]?.text || "";

            // Parse JSON - Robust extraction
            let jsonStr = text.replace(/```json/g, '').replace(/```/g, '').trim();
            const jsonMatch = jsonStr.match(/\{[\s\S]*\}/);
            if (jsonMatch) jsonStr = jsonMatch[0];
            jsonStr = jsonStr.replace(/,(\s*[\]}])/g, '$1');

            let analysis;
            try {
                analysis = JSON.parse(jsonStr);
            } catch (parseError) {
                console.error("JSON parse failed, attempting repair:", parseError);
                analysis = {
                    job_title: "Unknown Position",
                    summary: "Analysis failed - using raw search",
                    sourcing_strategy: {
                        target_companies: [],
                        target_industries: [],
                        tech_stack: { core: [], avoid: [] },
                        title_variations: []
                    },
                    required_skills: [],
                    experience_level: "senior"
                };
            }

            // Backwards compatibility layer (if frontend still expects old fields)
            analysis.neural_dimensions = {
                role_identity: analysis.job_title,
                domain_expertise: analysis.sourcing_strategy.target_industries[0] || "General",
                technical_env: "Inferred",
                leadership_scope: "Inferred"
            };
            analysis.synthetic_perfect_candidate_profile = analysis.summary;

            return {
                success: true,
                analysis: analysis
            };

        } catch (error) {
            console.error("Error in analyzeJob:", error);
            if (error instanceof z.ZodError) {
                throw new HttpsError("invalid-argument", `Invalid input: ${error.message}`);
            }
            throw new HttpsError("internal", "Failed to analyze job description");
        }
    }
);
