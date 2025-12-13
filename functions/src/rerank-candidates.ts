
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
        memory: "2GiB",
        timeoutSeconds: 300,
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

RECRUITER MENTALITY (Examples of Reasoning):

case "Senior Software Engineer" applying for "CTO":
- REASONING: "Candidate has strong technical skills (React, Node) but current scope is individual contribution. CTO requires organizational leadership, budget management, and boardroom presence. This is a severe scope mismatch."
- SCORE: Low (30-50).
- VERDICT: Individual Contributors generally lack the executive scope for C-Level roles, regardless of technical prowess.

case "VP of Engineering" applying for "CTO":
- REASONING: "Candidate manages managers, owns a budget, and drives strategy. The scope is aligned. Even if they don't know the exact stack (e.g. usage of Vue vs React), their leadership experience transfers."
- SCORE: High (85-95).
- VERDICT: Leadership Scope > Specific Stack Match for Executive roles.

case "Data Scientist" applying for "Principal Data Scientist":
- REASONING: "Candidate has the exact technical skills and seniority level. Perfect match."
- SCORE: Very High (90+).

GUIDING PRINCIPLE:
Evalute the **Scope of Responsibility** first. If the scope is mismatched (e.g. IC vs Executive), the score must be low, even if the keyword match is 100%. Don't get distracted by keyword density.

A senior recruiter understands that SKILLS IN CONTEXT matter:
- "Machine Learning" for a Data Scientist vs for a CTO means different things (hands-on vs strategic oversight)
- A candidate with the right title but wrong industry is often better than wrong title but right industry
- Years of experience in a DIFFERENT role don't transfer directly (15yr Data Scientist ≠ CTO candidate)

JOB DESCRIPTION:
${job_description}

CANDIDATES:
${candidates.map((c, i) => `
[Candidate ${i + 1}] ID: ${c.candidate_id}
Profile: ${JSON.stringify(c.profile).substring(0, 4000)}
`).join('\n')}

EVALUATION FRAMEWORK (Analyze Complexity & Scope):

1. SCOPE OF INFLUENCE (The "Executive" Test):
   - Assess the candidate's current management scope (Team size, Budget, Strategic influence).
   - Compare it to the Target Role.
   - Example: A "Director of Data Science" usually manages a specific vertical (Data). A "CTO" manages the entire horizontal engineering org. Is the candidate's scope broad enough?
   - Context Matters: A "VP" at a massive tech giant might be overqualified for a Seed startup CTO role, while a "Senior Engineer" might be underqualified. Use your judgment on Company Tier.

2. FUNCTIONAL BREADTH (Generalist vs Specialist):
   - Executive roles (CTO, VP Eng) require Generalist Engineering leadership (Infra, Product, People, Security).
   - Candidates stuck in a Niche (only Data Science, only QA, only DevOps) are often poor matches for broad C-Level roles, even if their title is high.
   - Look for evidence of cross-functional leadership.

3. CAREER TRAJECTORY (Logical Progression):
   - Is this role a logical next step?
   - Logical: VP -> CTO, Director -> VP.
   - Illogical/Risk: IC (Data Scientist) -> CTO.
   
SCORING PHILOSOPHY:
- Score based on *Probability of Success* in the target role.
- High Score (85+): Candidate has done this job before or is the perfect "Step Up" candidate with all necessary foundations.
- Mid Score (60-84): Candidate has the skills but the jump is large (e.g. pivoting domain or skipping a level). 
- Low Score (<60): Fundamental mismatch in scope or track (e.g. Specialist trying to be Generalist Executive).

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
