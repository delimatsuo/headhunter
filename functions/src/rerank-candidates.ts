
import { onCall, HttpsError } from "firebase-functions/v2/https";
import { z } from "zod";
import { geminiModel } from "./gemini-client";

const RerankInputSchema = z.object({
    job_description: z.string(),
    candidates: z.array(z.object({
        candidate_id: z.string(),
        profile: z.any(), // Flexible profile structure
        initial_score: z.number().optional()
    })),
    limit: z.number().min(1).max(20).default(10)
});

export const rerankCandidates = onCall(
    {
        memory: "1GiB",
        timeoutSeconds: 60,
    },
    async (request) => {
        try {
            const { job_description, candidates, limit } = RerankInputSchema.parse(request.data);

            if (candidates.length === 0) {
                return { success: true, results: [] };
            }

            // Construct prompt
            const prompt = `
You are a Senior Executive Recruiter with 20+ years of experience. Your task is to rank candidates for the job description below.

CRITICAL PRINCIPLE - ROLE-LEVEL MATCHING:
The most important factor is whether a candidate's CURRENT ROLE AND LEVEL matches what the job requires. This applies to ALL positions:

- For executive roles (CTO, VP, Director): Look for candidates currently in executive/leadership positions. Individual contributors (engineers, analysts, scientists) are NOT good matches even with relevant skills.
- For senior individual contributors (Staff Engineer, Principal Architect): Look for senior IC experience. Junior developers are poor matches; executives might be overqualified.
- For mid-level roles (Software Engineer, Data Analyst): Look for 3-7 years experience in similar roles. Interns are too junior; Directors are overqualified.
- For junior/entry roles: Look for early-career candidates or new graduates. Senior professionals are overqualified.

A senior recruiter understands that SKILLS IN CONTEXT matter:
- "Machine Learning" for a Data Scientist vs for a CTO means different things (hands-on vs strategic oversight)
- A candidate with the right title but wrong industry is often better than wrong title but right industry
- Years of experience in a DIFFERENT role don't transfer directly (15yr Data Scientist ≠ CTO candidate)

JOB DESCRIPTION:
${job_description}

CANDIDATES:
${candidates.map((c, i) => `
[Candidate ${i + 1}] ID: ${c.candidate_id}
Profile: ${JSON.stringify(c.profile).substring(0, 1500)}
`).join('\n')}

EVALUATION CRITERIA (apply these to ANY role):
1. Role/Title Alignment (60%): Is the candidate's current role at the same level as the job? 
2. Responsibility Match (25%): Does their scope of work (team size, decision authority, domain) match?
3. Skill Relevance (15%): Do they have the required skills for THIS role level?

SCORING GUIDE:
- 90-100: Perfect role match (same title/level, relevant experience)
- 70-89: Adjacent role (one level away, strong transferable experience) 
- 50-69: Significant mismatch (different level but some relevant skills)
- <50: Wrong candidate type (fundamentally different career track)

OUTPUT FORMAT (JSON ONLY, no markdown):
{
  "ranked_candidates": [
    {
      "candidate_id": "string",
      "score": number,
      "rationale": "1 sentence explaining role fit, e.g. 'Current VP of Engineering aligns perfectly with CTO role' or 'Senior Data Scientist lacks executive experience for this CTO position'"
    }
  ]
}
`;

            // Call Gemini
            console.log("Calling Gemini for reranking...");
            const result = await geminiModel.generateContent(prompt);
            console.log("Gemini response received.");
            const response = await result.response;
            const text = response.candidates?.[0]?.content?.parts?.[0]?.text || "";

            // Clean and parse JSON
            const jsonStr = text.replace(/```json/g, '').replace(/```/g, '').trim();
            const parsed = JSON.parse(jsonStr);

            // Merge with original candidate data
            const rankedResults = parsed.ranked_candidates.map((r: any) => {
                const original = candidates.find(c => c.candidate_id === r.candidate_id);
                if (!original) return null;
                return {
                    ...original,
                    overall_score: r.score,
                    rationale: [r.rationale] // Override rationale
                };
            }).filter(Boolean);

            return {
                success: true,
                results: rankedResults
            };

        } catch (error) {
            console.error("Error in rerankCandidates:", error);
            if (error instanceof Error) {
                console.error("Error message:", error.message);
                console.error("Error stack:", error.stack);
            }
            throw new HttpsError("internal", "Failed to rerank candidates");
        }
    }
);
