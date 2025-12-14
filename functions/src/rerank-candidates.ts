
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

CRITICAL PRINCIPLE - THE "NEURAL MATCH" FRAMEWORK:
Evaluate the candidate against the 4 Cognitive Dimensions of the job:

1. ROLE IDENTITY Match (Weight: 40%):
   - Does he/she identify as the person we need? (e.g. "Strategic Executive" vs "Hands-on Builder").
   - Mismatch here is fatal for Senior roles.

2. DOMAIN EXPERTISE Match (Weight: 30%):
   - Is their domain relevant? (e.g. Fintech knowledge for a Fintech role).
   - "Generalist" is OK if the JD is generic. but "Specialist" (e.g. Data Science) for a Generalist Role is a MISMATCH.

3. LEADERSHIP SCOPE Match (Weight: 20%):
   - Do they manage the right blast radius? (Team size, P&L, Strategy).
   - Avoid "Title Inflation" - look at actual responsibilities.

4. TECHNICAL ENVIRONMENT Match (Weight: 10%):
   - Have they worked in a similar stage/scale? (e.g. Startup vs Big Tech).

REASONING EXAMPLES:

case "VP of Data" applying for "Generalist CTO":
- ROLE: Mismatch. They are a functional leader, not a generalist tech executive.
- DOMAIN: Mismatch. Too niche (Data) vs Broad (Engineering/Product).
- SCORE: Low (45).
- REASONING: "Candidate is a high-level executive (VP), BUT their domain is too narrow (Data Science). We need a Generalist CTO who can manage Web/Mobile/DevOps, not just AI."

case "Principal Engineer" applying for "CTO":
- ROLE: Partial Match. Technical depth is there, but Identity is "IC".
- SCOPE: Mismatch. Lacks organizational leadership experience.
- SCORE: Medium-Low (55).
- REASONING: "Strong technical builder, but lacks the strategic/political scope required for a C-Level role."

case "Director of Engineering" applying for "VP of Engineering":
- ROLE: Match.
- SCOPE: Match (Stepping up).
- SCORE: High (90).

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

4. HIERARCHY & LEVEL PROGRESSION (The "Ladder"):
   - Standard path: IC -> Manager -> Director -> VP -> C-Level.
   - VALID JUMP (+1 Step): Director -> VP, or VP -> C-Level.
   - RISKY JUMP (+2 Steps): Manager -> VP. (Score limit: 70).
   - INVALID JUMP (+3 Steps): Manager -> C-Level (e.g. Eng Manager -> CTO).
     - REASONING: "Candidate is currently a Manager. jumping to CTO skips Director and VP levels. Taking a Manager to generic C-Level is extremely rare and risky."
     - SCORE: Must be < 60.
     - EXCEPTION: If they held the title "CTO" or "VP" in the PAST (check history), then they are qualified.
   
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

            // Call Gemini Pro (Reasoning Model)
            console.log("Calling Gemini Pro for reranking...");
            const result = await geminiReasoningModel.generateContent(prompt);
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
