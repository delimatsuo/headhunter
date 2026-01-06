/**
 * Gemini Reranking Service
 * 
 * Uses Gemini 2.5 Flash as an instruction-following LLM to rerank candidates
 * based on job-specific hiring logic, career trajectory, and fit.
 * 
 * Unlike Vertex AI's semantic ranker, Gemini can follow explicit ranking
 * criteria and reason about candidate suitability.
 */

import { GoogleGenerativeAI } from '@google/generative-ai';

// Types
interface CandidateForReranking {
    candidate_id: string;
    name: string;
    current_role: string;
    years_experience: number;
    skills: string[];
    companies: string[];
    career_trajectory?: string;
}

interface JobContext {
    function: string;      // product, engineering, data, sales, etc.
    level: string;         // c-level, vp, director, manager, senior, mid, junior
    title?: string;        // Full job title
    description?: string;  // Job description summary
}

interface RerankResult {
    candidate_id: string;
    score: number;         // 0-100
    rationale: string;     // Why this candidate ranks here
}

export class GeminiRerankingService {
    private genAI: GoogleGenerativeAI;
    private modelName: string = 'gemini-2.0-flash';

    constructor() {
        const apiKey = process.env.GOOGLE_API_KEY || '';
        this.genAI = new GoogleGenerativeAI(apiKey);
    }

    /**
     * Rerank candidates using Gemini's reasoning capabilities
     */
    async rerank(
        candidates: CandidateForReranking[],
        jobContext: JobContext,
        topN: number = 50
    ): Promise<RerankResult[]> {
        const startTime = Date.now();

        if (candidates.length === 0) {
            return [];
        }

        // Take top candidates for reranking (limit to control costs)
        const candidatesToRank = candidates.slice(0, Math.min(topN, 100));

        try {
            const model = this.genAI.getGenerativeModel({
                model: this.modelName,
                generationConfig: {
                    temperature: 0.1,  // Low temperature for consistent ranking
                    maxOutputTokens: 4096,
                }
            });

            const prompt = this.buildRerankingPrompt(candidatesToRank, jobContext);

            console.log(`[GeminiRerank] Sending ${candidatesToRank.length} candidates for reranking`);

            const result = await model.generateContent(prompt);
            const responseText = result.response.text();

            // Parse the ranked results
            const rankings = this.parseRankingResponse(responseText, candidatesToRank);

            const latency = Date.now() - startTime;
            console.log(`[GeminiRerank] Completed in ${latency}ms, returned ${rankings.length} results`);

            return rankings;

        } catch (error: any) {
            console.error('[GeminiRerank] Error:', error.message);
            // Fallback: return original order with default scores
            return candidatesToRank.map((c, idx) => ({
                candidate_id: c.candidate_id,
                score: 100 - idx,  // Decreasing scores
                rationale: 'Ranked by retrieval score (reranking unavailable)'
            }));
        }
    }

    /**
     * Build the reranking prompt based on job context
     */
    private buildRerankingPrompt(
        candidates: CandidateForReranking[],
        jobContext: JobContext
    ): string {
        const { function: func, level, title } = jobContext;
        const roleTitle = title || `${this.capitalizeLevel(level)} ${this.capitalizeFunction(func)}`;

        // Format candidates for the prompt
        const candidateList = candidates.map((c, idx) => {
            const skills = c.skills?.slice(0, 5).join(', ') || 'Not specified';
            const companies = c.companies?.slice(0, 3).join(', ') || 'Not specified';
            return `${idx + 1}. ID: ${c.candidate_id}
   Name: ${c.name}
   Current Role: ${c.current_role}
   Experience: ${c.years_experience} years
   Skills: ${skills}
   Companies: ${companies}`;
        }).join('\n\n');

        return `You are a senior executive recruiter evaluating candidates for a ${roleTitle} position.

## ROLE CONTEXT
- **Position**: ${roleTitle}
- **Function**: ${this.capitalizeFunction(func)}
- **Level**: ${this.capitalizeLevel(level)}

## YOUR TASK
Rank these ${candidates.length} candidates from BEST FIT to WORST FIT for this role.

## RANKING CRITERIA
${this.getGeneralizedHiringCriteria(func, level)}

## CANDIDATES
${candidateList}

## REQUIRED OUTPUT FORMAT
Return a JSON array with ALL candidates ranked from best to worst fit.
CRITICAL: The "id" field MUST be the EXACT candidate ID value shown after "ID:" for each candidate (e.g., if a candidate shows "ID: abc123xyz", use "abc123xyz" as the id).

\`\`\`json
[
  {"id": "<exact_candidate_id_from_above>", "score": 95, "reason": "One sentence explanation"},
  {"id": "<exact_candidate_id_from_above>", "score": 88, "reason": "One sentence explanation"},
  ...
]
\`\`\`

Score from 0-100 where:
- 90-100: Excellent fit - ready for this exact role
- 75-89: Strong fit - good match with minor gaps
- 60-74: Moderate fit - relevant experience but not ideal
- 40-59: Weak fit - significant gaps or wrong trajectory
- 0-39: Poor fit - wrong function, level, or experience

IMPORTANT: Include ALL candidates. Rank them by their suitability for ${roleTitle}, considering career trajectory, not just current title.`;
    }

    /**
     * Generate hiring criteria based on function and level
     * This is GENERAL - works for any role type
     */
    private getGeneralizedHiringCriteria(func: string, level: string): string {
        const funcName = this.capitalizeFunction(func);
        const levelName = this.capitalizeLevel(level);

        // Executive-level (C-level, VP)
        if (level === 'c-level' || level === 'vp') {
            return `For a ${levelName} in ${funcName}:

STRONGEST CANDIDATES:
- Current/former C-level or VPs in ${funcName}
- Founders or executives who built ${funcName} organizations
- Leaders with 15+ years and P&L or org-building experience

STRONG CANDIDATES:
- Directors in ${funcName} with 15+ years ready to step up
- Former executives now in advisory or consulting (still have skills)
- High performers from top companies on executive trajectory

CONSIDER (trajectory matters):
- Former VPs/Directors who took Principal/Staff roles (strategic move)
- Leaders at smaller companies with right experience
- Adjacent function leaders with transferable skills

WEAKER CANDIDATES:
- Managers without executive experience
- Individual contributors focused on execution, not strategy
- People whose experience is primarily in a different function`;
        }

        // Director-level
        if (level === 'director') {
            return `For a ${levelName} in ${funcName}:

STRONGEST CANDIDATES:
- Current Directors in ${funcName}
- VPs looking for specific Director-level opportunity
- Heads of departments at growing companies

STRONG CANDIDATES:
- Senior Managers with 10+ years ready for promotion
- Former Directors now in IC roles (may be strategic)
- Tech/Team Leads with significant org management

WEAKER CANDIDATES:
- Early-career managers (< 5 years management experience)
- ICs without demonstrated leadership
- Different function background entirely`;
        }

        // Manager-level
        if (level === 'manager') {
            return `For a ${levelName} in ${funcName}:

STRONGEST CANDIDATES:
- Current Managers in ${funcName}
- Team Leads transitioning to management
- Senior ICs with mentorship and leadership experience

STRONG CANDIDATES:
- Leads at top companies in ${funcName}
- People-focused contributors ready for management

WEAKER CANDIDATES:
- Junior candidates without team experience
- Very senior executives (overqualified, may not want the role)`;
        }

        // Senior IC level
        if (level === 'senior') {
            return `For a ${levelName} role in ${funcName}:

STRONGEST CANDIDATES:
- Current Senior ${funcName} professionals
- Staff/Principal level contributors
- Mid-level candidates with strong growth trajectory

STRONG CANDIDATES:
- Experienced ${funcName} professionals at good companies
- Adjacent function with transferable skills

WEAKER CANDIDATES:
- Junior candidates
- Managers who want to return to IC (verify intent)`;
        }

        // Mid-level and junior
        return `For this ${levelName} role in ${funcName}:

STRONGEST CANDIDATES:
- Candidates at similar level in ${funcName}
- Adjacent levels with right experience
- Strong educational background and relevant internships

WEAKER CANDIDATES:
- Overqualified executives (may not stay)
- Wrong function entirely`;
    }

    /**
     * Parse Gemini's ranking response
     */
    private parseRankingResponse(
        responseText: string,
        originalCandidates: CandidateForReranking[]
    ): RerankResult[] {
        try {
            // Extract JSON from response (handle markdown code blocks)
            let jsonStr = responseText;

            // Remove markdown code blocks if present
            const jsonMatch = responseText.match(/```(?:json)?\s*([\s\S]*?)```/);
            if (jsonMatch) {
                jsonStr = jsonMatch[1];
            }

            const parsed = JSON.parse(jsonStr.trim());

            if (!Array.isArray(parsed)) {
                throw new Error('Response is not an array');
            }

            // Build a map of original candidates for ID validation
            const originalIdMap = new Map(originalCandidates.map(c => [c.candidate_id, c]));
            const originalByIndex = new Map(originalCandidates.map((c, idx) => [String(idx + 1), c.candidate_id]));

            // Debug: Log first few returned IDs
            const sampleReturned = parsed.slice(0, 3).map((item: any) => item.id || item.candidate_id);
            console.log(`[GeminiRerank] Sample returned IDs: ${JSON.stringify(sampleReturned)}`);

            // Map to our format with ID recovery
            const results = parsed.map((item: any) => {
                let candidateId = item.id || item.candidate_id || '';

                // If the returned ID is a number (1, 2, 3...), map it back to actual candidate_id
                if (/^\d+$/.test(candidateId)) {
                    const actualId = originalByIndex.get(candidateId);
                    if (actualId) {
                        console.log(`[GeminiRerank] Recovered ID: ${candidateId} -> ${actualId}`);
                        candidateId = actualId;
                    }
                }

                return {
                    candidate_id: candidateId,
                    score: typeof item.score === 'number' ? item.score : 50,
                    rationale: item.reason || item.rationale || 'No explanation provided'
                };
            });

            // Track match rate
            const matchedCount = results.filter(r => originalIdMap.has(r.candidate_id)).length;
            console.log(`[GeminiRerank] ID match rate: ${matchedCount}/${results.length}`);

            return results;

        } catch (error) {
            console.error('[GeminiRerank] Failed to parse response:', error);
            console.error('[GeminiRerank] Raw response:', responseText.substring(0, 500));

            // Fallback: return original candidates with default scores
            return originalCandidates.map((c, idx) => ({
                candidate_id: c.candidate_id,
                score: 100 - idx,
                rationale: 'Fallback scoring (parse error)'
            }));
        }
    }

    /**
     * Helper to capitalize function names
     */
    private capitalizeFunction(func: string): string {
        const names: Record<string, string> = {
            'engineering': 'Engineering/Technology',
            'product': 'Product Management',
            'data': 'Data Science/Analytics',
            'design': 'Design/UX',
            'sales': 'Sales',
            'marketing': 'Marketing',
            'hr': 'Human Resources/People',
            'finance': 'Finance',
            'operations': 'Operations',
            'general': 'General Management'
        };
        return names[func] || func;
    }

    /**
     * Helper to capitalize level names
     */
    private capitalizeLevel(level: string): string {
        const names: Record<string, string> = {
            'c-level': 'C-Level Executive',
            'vp': 'VP/Senior Vice President',
            'director': 'Director',
            'manager': 'Manager',
            'senior': 'Senior',
            'mid': 'Mid-Level',
            'junior': 'Junior',
            'intern': 'Intern'
        };
        return names[level] || level;
    }
}

// Singleton instance
let geminiRerankingInstance: GeminiRerankingService | null = null;

export function getGeminiRerankingService(): GeminiRerankingService {
    if (!geminiRerankingInstance) {
        geminiRerankingInstance = new GeminiRerankingService();
    }
    return geminiRerankingInstance;
}
