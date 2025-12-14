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
You are an expert Technical Recruiter and AI Hiring Manager.
Analyze the following Job Description to extract unstructured requirements into structured search parameters.

JOB DESCRIPTION:
"""
${job_description}
"""

TASK:
3. **COGNITIVE DECOMPOSITION (The "Neural Match" Brain)**:
   Break the job down into 4 distinct dimensions.
   - **Role Identity**: Who are they? (e.g., "Strategic Technical Executive", "Hands-on Architect").
   - **Domain Expertise**: What field? (e.g., "Fintech", "Healthtech").
     * CRITICAL: If the JD is generic (e.g., "Tech Company"), label as "Generalist Software Engineering". DO NOT hallucinate a specific niche like "Data Science" unless explicitly stated.
   - **Technical Environment**: Where do they thrive? (e.g., "High Scale", "Zero-to-One", "Cloud Native").
   - **Leadership Scope**: How do they lead? (e.g., "Manager of Managers", "Org Builder", "IC").

OUTPUT FORMAT (JSON ONLY):
{
  "job_title": "Inferred or Explicit Title",
  "summary": "Concise 1-sentence summary of the role focus",
  "required_skills": ["skill1", "skill2", ...],
  "preferred_skills": ["skill1", ...],
  "experience_level": "entry" | "mid" | "senior" | "executive",
  "key_responsibilities": ["string", "string", ...],
  "neural_dimensions": {
    "role_identity": "string",
    "domain_expertise": "string",
    "technical_env": "string",
    "leadership_scope": "string"
  }
}
`;

            console.log("Analyzing job description with Gemini...");
            const result = await geminiModel.generateContent(prompt);
            const response = await result.response;
            const text = response.candidates?.[0]?.content?.parts?.[0]?.text || "";

            // Parse JSON
            const jsonStr = text.replace(/```json/g, '').replace(/```/g, '').trim();
            const analysis = JSON.parse(jsonStr);

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
