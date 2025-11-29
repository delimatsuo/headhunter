
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
You are a Senior Executive Recruiter. Your task is to rank the following candidates for a specific job description.

JOB DESCRIPTION:
${job_description}

CANDIDATES:
${candidates.map((c, i) => `
[Candidate ${i + 1}] ID: ${c.candidate_id}
Profile: ${JSON.stringify(c.profile).substring(0, 1000)}... (truncated)
`).join('\n')}

INSTRUCTIONS:
1. Evaluate each candidate's fit for the role based on skills, experience, and trajectory.
2. Assign a score from 0-100.
3. Provide a concise, 1-sentence "Senior Recruiter Rationale" for your score.
4. Return the top ${limit} candidates in JSON format.

OUTPUT FORMAT (JSON ONLY):
{
  "ranked_candidates": [
    {
      "candidate_id": "string",
      "score": number,
      "rationale": "string"
    }
  ]
}
`;

            // Call Gemini
            const result = await geminiModel.generateContent(prompt);
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
            throw new HttpsError("internal", "Failed to rerank candidates");
        }
    }
);
