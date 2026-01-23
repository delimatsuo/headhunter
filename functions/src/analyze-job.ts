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
1. **Tech Stack Extraction** (CRITICAL - DO THIS FIRST):
   - Extract ALL specific technologies, frameworks, tools, cloud services, and platforms mentioned in the job description.
   - Be LITERAL - extract exact names as written (e.g., "NestJS" not "Node.js frameworks").
   - Include: programming languages, frameworks, libraries, databases, cloud services (AWS, GCP, Azure), specific services (Lambda, Fargate, S3), tools, platforms.
   - Examples of what to extract: "AWS", "Lambda", "Fargate", "NestJS", "PostgreSQL", "Docker", "Kubernetes", "React", "TypeScript", "Node.js", "Redis", "MongoDB", "GraphQL", "REST", "CI/CD", "Terraform".
   - Do NOT use generic phrases like "Proficiency in..." - just the technology name.

2. **Target Company Identification**:
   - Infer the *type* of company (e.g. "Early-stage Fintech").
   - List 5-10 REAL companies that hire similar talent.
   - *Logic*: If JD says "Stripe-like API", target Adyen, Block, Checkout.com.

3. **Tech Stack Profiling**:
   - From the extracted technologies, identify "Core" (must-have) vs "Nice-to-have".
   - Define "Anti-patterns" (e.g. if Modern Stack, penalize Legacy Enterprise Java).

4. **Title Expansion**:
   - List all valid titles. (e.g. for "Staff Engineer", include "Principal", "Tech Lead", "Architect").

5. **Experience Configuration**:
   - Determine the seniority level ("IC", "Manager", "Executive").

OUTPUT SCHEMA (JSON ONLY):
{
  "job_title": "Inferred or Explicit Title",
  "summary": "1-sentence summary of the role focus",
  "sourcing_strategy": {
    "target_companies": ["Stripe", "Adyen", ...],
    "target_industries": ["Fintech", "Payments", ...],
    "tech_stack": {
      "core": ["Go", "Kubernetes", ...],
      "avoid": ["Oracle", ...]
    },
    "title_variations": ["Staff Engineer", ...]
  },
  "required_skills": ["Node.js", "TypeScript", "NestJS", "AWS", "Lambda", "Fargate"],
  "experience_level": "senior"
}

IMPORTANT RULES FOR required_skills:
Include TWO categories of skills:

A) EXPLICIT TECHNOLOGIES (from the job description):
   - Extract ONLY technologies explicitly mentioned in the text
   - Use exact names: "NestJS", "Lambda", "Fargate", "AWS", "Node.js", "TypeScript"
   - Do NOT add alternative languages (e.g., don't add Java/Python/C# if JD says Node.js)
   - Do NOT add "JavaScript" unless explicitly mentioned (TypeScript implies it)
   - Include cloud services as separate items: "AWS", "Lambda", "Fargate", "S3"

B) INFERRED COMPETENCIES (based on role/seniority/context):
   - A recruiter would infer these based on the role type and seniority
   - Examples: "API Design", "Database Design", "System Design", "Testing", "CI/CD"
   - These should be architectural/domain skills, NOT alternative technologies
   - For a "Senior Backend Engineer" → infer "API Design", "Database Design", "Microservices"
   - For a "Fintech" role → infer "Financial Systems", "Payment Processing"

CRITICAL - NEVER include technologies that could substitute the mentioned stack:
- If JD says "Node.js, TypeScript" → do NOT add "Java", "Python", "C#", "Go", "Ruby"
- If JD says "AWS" → do NOT add "GCP", "Azure" unless explicitly mentioned
- If JD says "PostgreSQL" → do NOT add "MySQL", "Oracle", "SQL Server" unless mentioned
- Do NOT include soft skills here (put those in summary if relevant).
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
