
import { onCall, HttpsError } from "firebase-functions/v2/https";
import { z } from "zod";
import { geminiReasoningModel } from "./gemini-client";

const RerankInputSchema = z.object({
    job_description: z.string(),
    candidates: z.array(z.object({
        candidate_id: z.string(),
        profile: z.any(), // Flexible profile structure
        initial_score: z.number().optional()
    })),
    limit: z.number().min(1).max(50).default(20) // Increased for recruiter workflows
});

export const rerankCandidates = onCall(
    {
        memory: "2GiB",
        timeoutSeconds: 300,
    },
    async (request) => {
        try {
            const { job_description, candidates, limit } = RerankInputSchema.parse(request.data);

            if (candidates.length === 0) {
                console.log("No candidates to rerank.");
                return { success: true, results: [] };
            }
            console.log(`[Reranker] Received ${candidates.length} candidates. Requesting Top ${limit}.`);

            // Construct prompt for LISTWISE Reranking
            const prompt = `
You are a Senior Executive Recruiter acting as a "Calibration Expert".
Your task is to RE-ORDER the following list of candidates for the role: **${(job_description.match(/Role: (.*?)\n/)?.[1] || job_description).substring(0, 200)}**

**THE PROBLEM:**
The current search results are "noisy". We have legitimate "Chief Product Officers" mixed with "Senior Product Managers".
We need strictly hierarchical ordering.

**YOUR RANKING RULES (The "Hierarchy of Value"):**

1.  **TIER 1 (The "Perfect Match"):**
    *   **Exact Title Match**: Must hold the *target title* NOW (e.g. "CPO" for a CPO role).
    *   **Domain Fit**: Experience in the exact target industry (e.g. Fintech).
    *   **Scale Fit**: Experience at similar company size.

2.  **TIER 2 (The "Step Up" / "Stretch"):
    *   One level below (e.g. "VP of Product" for a CPO role).
    *   MUST be from a *better* or *larger* company to justify the step up.

3.  **TIER 3 (The "Fallbacks"):**
    *   Incorrect title (e.g. "Senior PM" for CPO role - usually too junior).
    *   Irrelevant domain.

**INSTRUCTIONS:**
1.  **Compare** the candidates against each other.
2.  **Sort** them from Best Fit (#1) to Worst Fit.
3.  **Disqualify** clearly unqualified candidates (e.g. a "Customer Support" agent for a "CTO" role) by putting them at the bottom.

**JOB DESCRIPTION:**
${job_description}

**CANDIDATES TO RANK:**
${candidates.map((c, i) => `
---
ID: ${c.candidate_id}
Profile Summary:
${JSON.stringify(c.profile).substring(0, 3000)}
---
`).join('\n')}

**OUTPUT FORMAT:**
Return a valid JSON object containing a SINGLE list called "ranked_ids".
The list must contain the \`candidate_id\` strings in your proposed order (Best to Worst).
Include a brief \`rationale\` for the top 3 choices.

Example:
{
  "ranked_ids": ["id_123", "id_456", "id_789"],
  "top_3_rationale": [
    "Candidate id_123 is a current CPO at a Fintech unicorn (Perfect Match).",
    "Candidate id_456 is a VP Product at a major bank (Strong Step-up).",
    "Candidate id_789 is a Head of Product but lacks scale."
  ]
}
`;

            // Call Gemini Pro (Reasoning Model)
            console.log("Calling Gemini Pro for Listwise Reranking...");
            const result = await geminiReasoningModel.generateContent(prompt);
            console.log("Gemini response received.");
            const response = await result.response;
            const text = response.candidates?.[0]?.content?.parts?.[0]?.text || "";

            // Clean and parse JSON
            let jsonStr = text.replace(/```json/g, '').replace(/```/g, '').trim();
            const jsonMatch = jsonStr.match(/\{[\s\S]*\}/);
            if (jsonMatch) jsonStr = jsonMatch[0];
            jsonStr = jsonStr.replace(/,(\s*[\]}])/g, '$1');

            let parsed;
            try {
                parsed = JSON.parse(jsonStr);
                if (!parsed.ranked_ids || !Array.isArray(parsed.ranked_ids)) {
                    throw new Error("Invalid response format: missing ranked_ids array");
                }
            } catch (parseError) {
                console.error("JSON parse failed or invalid format:", parseError);
                console.log("Raw Text:", text);
                return { success: true, results: [] }; // Fallback
            }

            const rankedIds = parsed.ranked_ids;
            console.log(`LLM returned ${rankedIds.length} ranked items.`);

            // Reconstruct the list in the new order and assign artificial scores
            // Score = 95 - (index * 1). So #1=95, #2=94, #3=93...#45=50
            // This ensures they appear sorted in the UI which uses 'score'
            // Gentler decay allows more candidates to pass the 50 threshold
            const rankedResults = rankedIds.map((id: string, index: number) => {
                const original = candidates.find(c => c.candidate_id === id);
                if (!original) return null;

                // Artificial score decay to enforce order in frontend (1 point per rank)
                const newScore = Math.max(50, 95 - index);

                // Get rationale if available for top 3, otherwise generic
                let rationaleText = "AI Reranked based on comparative fit.";
                if (index < 3 && parsed.top_3_rationale && parsed.top_3_rationale[index]) {
                    rationaleText = parsed.top_3_rationale[index];
                }

                return {
                    ...original,
                    overall_score: newScore,
                    rationale: [rationaleText]
                };
            }).filter(Boolean);

            // Append any candidates that were missed by the LLM (safety net)
            const missedCandidates = candidates.filter(c => !rankedIds.includes(c.candidate_id));
            missedCandidates.forEach((c, i) => {
                rankedResults.push({
                    ...c,
                    overall_score: 49 - i, // Bottom of the pile
                    rationale: ["Ranked lower by AI comparison."]
                });
            });

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
