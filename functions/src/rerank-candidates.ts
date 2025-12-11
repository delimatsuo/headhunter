
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
You are a Senior Executive Recruiter with 20+ years of experience. Your task is to rank the following candidates for a specific job description.

CRITICAL INSTRUCTIONS - READ CAREFULLY:
1. **ROLE-LEVEL MATCHING IS THE #1 PRIORITY**. If the job is for a CTO, prioritize candidates with executive titles (CTO, VP of Engineering, Chief Architect, Head of Technology, etc.). Do NOT rank individual contributors (Data Scientists, Software Engineers, Analysts) highly just because they share technical skills.
2. A senior recruiter understands that "cloud computing" in a CTO job description means strategic oversight, not hands-on coding. Match candidates by ROLE and RESPONSIBILITY LEVEL, not just keywords.
3. For executive roles: Look for leadership scope (team size, P&L ownership, board exposure), strategic decision-making, and executive presence.
4. A Data Scientist with 15 years experience is NOT a good match for a CTO role unless they have transitioned into executive leadership.

JOB DESCRIPTION:
${job_description}

CANDIDATES:
${candidates.map((c, i) => `
[Candidate ${i + 1}] ID: ${c.candidate_id}
Profile: ${JSON.stringify(c.profile).substring(0, 1500)}
`).join('\n')}

EVALUATION CRITERIA (in priority order):
1. Role/Title Match: Does the candidate's current role align with the job level? (70% weight)
2. Leadership Scope: For executive roles, do they have executive-level responsibilities? (20% weight)
3. Skill Overlap: Technical skills are secondary to role fit. (10% weight)

OUTPUT FORMAT (JSON ONLY, no markdown):
{
  "ranked_candidates": [
    {
      "candidate_id": "string",
      "score": number (0-100, where 90+ = perfect role match, 70-89 = adjacent role, <70 = wrong level),
      "rationale": "1 sentence explaining role fit, not just skills"
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
