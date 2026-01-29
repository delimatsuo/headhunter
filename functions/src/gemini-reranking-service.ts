/**
 * Gemini Reranking Service - Two-Pass Architecture
 *
 * Uses Gemini 2.0 Flash with a two-pass approach to avoid token overflow:
 *
 * Pass 1 (Quick Filter): Lightweight prompt (~200 tokens) to filter obvious mismatches
 *   - Removes wrong specialties (frontend for backend role)
 *   - Removes wrong levels (Principal for Senior role)
 *
 * Pass 2 (Deep Rank): Focused prompt (~500 tokens) for quality scoring
 *   - Career trajectory reasoning
 *   - Nuanced specialty matching
 *   - Meaningful rationale generation
 *
 * This avoids the token overflow that caused 100% parse failures with single-pass.
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
    // Tech stack context for intelligent matching
    requiredSkills?: string[];      // Core tech from JD: ["Node.js", "TypeScript", "NestJS"]
    avoidSkills?: string[];         // Anti-patterns: ["Oracle", "legacy"]
    companyContext?: string;        // "early-stage fintech startup"
}

interface RerankResult {
    candidate_id: string;
    score: number;         // 0-100
    rationale: string;     // Why this candidate ranks here
}

interface RerankOptions {
    skipFilter?: boolean;  // Skip Pass 1 filter (default: auto-detect based on function)
}

// Internal types for two-pass architecture
interface FilterResult {
    keep: string[];      // Candidate IDs to keep
    remove: string[];    // Candidate IDs to remove
}

export class GeminiRerankingService {
    private genAI: GoogleGenerativeAI;
    private modelName: string = 'gemini-2.0-flash';  // Non-thinking model (deprecated March 2026 - migrate to gemini-2.5-flash-lite)

    constructor() {
        const apiKey = process.env.GOOGLE_API_KEY || '';
        this.genAI = new GoogleGenerativeAI(apiKey);
    }

    /**
     * Sanitize candidate data to prevent JSON parsing issues
     * Escapes quotes, removes newlines, handles special chars
     */
    private sanitizeText(text: string | undefined): string {
        if (!text) return '';
        return text
            .replace(/[\n\r\t]/g, ' ')      // Remove newlines/tabs
            .replace(/"/g, "'")              // Replace double quotes with single
            .replace(/\\/g, '')              // Remove backslashes
            .replace(/[\x00-\x1F]/g, '')     // Remove control characters
            .trim()
            .substring(0, 100);              // Limit length
    }

    /**
     * Sanitize skills array - limit count and clean each skill
     */
    private sanitizeSkills(skills: string[] | undefined): string {
        if (!skills || !Array.isArray(skills)) return 'Not specified';
        return skills
            .slice(0, 5)
            .map(s => this.sanitizeText(s))
            .filter(s => s.length > 0)
            .join(', ') || 'Not specified';
    }

    /**
     * Two-Pass Reranking: Filter → Rank
     *
     * Pass 1: Quick filter with tiny prompt (~200 tokens) - SKIPPED for engineering searches
     * Pass 2: Deep rank on filtered candidates (~500 tokens) - now batched for reliability
     *
     * Key insight: For common searches (e.g., "Senior Backend Engineer") where 60%+ of
     * candidates match, filtering is counterproductive. We skip Pass 1 and send all
     * candidates directly to Pass 2 for proper ranking.
     */
    async rerank(
        candidates: CandidateForReranking[],
        jobContext: JobContext,
        topN: number = 50,
        options: RerankOptions = {}
    ): Promise<RerankResult[]> {
        const startTime = Date.now();

        if (candidates.length === 0) {
            return [];
        }

        // Limit total candidates to process
        const candidatesToProcess = candidates.slice(0, Math.min(topN * 2, 100));

        // Determine if we should skip Pass 1 filter
        // Default: skip for engineering searches (majority of candidates likely match)
        const skipFilter = options.skipFilter ??
            (jobContext.function === 'engineering');

        try {
            const model = this.genAI.getGenerativeModel({
                model: this.modelName,
                generationConfig: {
                    temperature: 0.1,  // Low temperature for consistent results
                    maxOutputTokens: 8192,  // Increased to handle full batch responses
                },
                // Disable thinking for gemini-2.5-flash to prevent token budget exhaustion
                // Thinking tokens were consuming ~3500 of 4096 tokens, leaving only ~500 for output
            } as any);

            // Note: thinkingConfig may need to be passed via generateContent() call
            // if the SDK doesn't support it in getGenerativeModel()

            let filteredCandidates: CandidateForReranking[];

            if (skipFilter) {
                // ===== SKIP PASS 1: Direct to ranking =====
                console.log(`[GeminiRerank] Skipping Pass 1 filter for ${jobContext.function} (${candidatesToProcess.length} candidates)`);
                filteredCandidates = candidatesToProcess.slice(0, Math.min(50, topN));
            } else {
                // ===== PASS 1: Quick Filter =====
                console.log(`[GeminiRerank] Pass 1: Filtering ${candidatesToProcess.length} candidates`);
                const filteredIds = await this.quickFilter(model, candidatesToProcess, jobContext);

                // Get filtered candidates (keep order)
                filteredCandidates = candidatesToProcess.filter(c =>
                    filteredIds.includes(c.candidate_id)
                );

                console.log(`[GeminiRerank] Pass 1 complete: ${filteredCandidates.length}/${candidatesToProcess.length} candidates kept`);

                // If too few candidates passed filter, add some back
                if (filteredCandidates.length < 10 && candidatesToProcess.length > 10) {
                    const additionalCandidates = candidatesToProcess
                        .filter(c => !filteredIds.includes(c.candidate_id))
                        .slice(0, 10 - filteredCandidates.length);
                    filteredCandidates.push(...additionalCandidates);
                    console.log(`[GeminiRerank] Added ${additionalCandidates.length} fallback candidates`);
                }
            }

            // ===== PASS 2: Deep Rank (Batched) =====
            const toRank = filteredCandidates.slice(0, Math.min(50, topN));
            console.log(`[GeminiRerank] Pass 2: Deep ranking ${toRank.length} candidates (batched)`);

            const rankings = await this.deepRankBatched(model, toRank, jobContext);

            const latency = Date.now() - startTime;
            console.log(`[GeminiRerank] Completed in ${latency}ms, returned ${rankings.length} results`);

            // Track ID match rate
            const originalIdSet = new Set(candidatesToProcess.map(c => c.candidate_id));
            const matchedCount = rankings.filter(r => originalIdSet.has(r.candidate_id)).length;
            console.log(`[GeminiRerank] ID match rate: ${matchedCount}/${rankings.length}`);

            return rankings;

        } catch (error: any) {
            console.error('[GeminiRerank] Error:', error.message);
            // Fallback: use improved scoring based on candidate metadata
            return this.fallbackRanking(candidatesToProcess.slice(0, topN), jobContext);
        }
    }

    /**
     * PASS 1: Quick Filter
     * Tiny prompt (~200 tokens) to identify obvious mismatches
     */
    private async quickFilter(
        model: any,
        candidates: CandidateForReranking[],
        jobContext: JobContext
    ): Promise<string[]> {
        const { function: func, level, title } = jobContext;
        const roleTitle = title || `${this.capitalizeLevel(level)} ${this.capitalizeFunction(func)}`;
        const specialty = this.extractSpecialtyFromTitle(roleTitle);

        // Build compact candidate list (minimal info for filtering)
        const candidateList = candidates.map((c, idx) => {
            const name = this.sanitizeText(c.name) || 'Unknown';
            const role = this.sanitizeText(c.current_role) || 'Unknown';
            return `${idx + 1}. ${name} | ${role} | ${c.years_experience || 0}y`;
        }).join('\n');

        // Determine filter criteria based on job
        let keepCriteria = '';
        let removeCriteria = '';

        if (func === 'engineering' && specialty) {
            keepCriteria = `KEEP: ${specialty}, Fullstack, Software Engineer at Mid/Senior level`;
            removeCriteria = `REMOVE: Wrong specialty (${this.getOppositeSpecialty(specialty)}), Principal/Staff/Director+, PM/QA`;
        } else {
            keepCriteria = `KEEP: ${this.capitalizeFunction(func)} professionals at ${level} or one level below`;
            removeCriteria = `REMOVE: Wrong function, significantly overqualified (2+ levels above)`;
        }

        const prompt = `Job: ${roleTitle}

For each candidate, answer: KEEP or REMOVE?
- ${keepCriteria}
- ${removeCriteria}

Candidates:
${candidateList}

Return JSON: {"keep": [1, 2, 5, ...], "remove": [3, 4, 6, ...]}
Use candidate NUMBERS (1, 2, 3...), not names or IDs.`;

        try {
            const result = await model.generateContent(prompt);
            const responseText = result.response.text();

            // Parse filter response
            const filterResult = this.parseFilterResponse(responseText, candidates);
            return filterResult;

        } catch (error: any) {
            console.error('[GeminiRerank] Filter pass failed:', error.message);
            // On failure, keep all candidates
            return candidates.map(c => c.candidate_id);
        }
    }

    /**
     * PASS 2: Deep Rank
     * Focused prompt (~500 tokens) for quality scoring
     */
    private async deepRank(
        model: any,
        candidates: CandidateForReranking[],
        jobContext: JobContext
    ): Promise<RerankResult[]> {
        const { function: func, level, title } = jobContext;
        const roleTitle = title || `${this.capitalizeLevel(level)} ${this.capitalizeFunction(func)}`;
        const specialty = this.extractSpecialtyFromTitle(roleTitle);

        // Build candidate list with more detail (but still compact)
        const candidateList = candidates.map((c, idx) => {
            const name = this.sanitizeText(c.name) || 'Unknown';
            const role = this.sanitizeText(c.current_role) || 'Unknown';
            const skills = this.sanitizeSkills(c.skills);
            return `${idx + 1}. ID: ${c.candidate_id} | ${name} | ${role} | ${c.years_experience || 0}y | Skills: ${skills}`;
        }).join('\n');

        // Build scoring rubric based on job
        const rubric = this.buildScoringRubric(func, level, specialty);

        // Build tech stack and seniority guidance
        const techStackGuidance = this.buildTechStackGuidance(jobContext);
        const seniorityGuidance = this.buildSeniorityGuidance(jobContext);

        const prompt = `You are a Principal Technical Recruiter ranking candidates for: ${roleTitle}

${rubric}
${techStackGuidance}
${seniorityGuidance}

KEY RECRUITER PRINCIPLES:
1. **Tech Stack Fit**: ${jobContext.requiredSkills?.length ? `This ${jobContext.requiredSkills.slice(0, 3).join('/')} role needs candidates with THAT stack, not alternatives` : 'Match technical skills to job requirements'}
   - Java/C# developers are NOT good fits for Node.js/TypeScript roles (different ecosystems)
   - "Backend" is not enough - the PRIMARY LANGUAGE matters

2. **Career Excitement**: The best candidate is EXCITED about this opportunity
   - Mid→Senior = step UP (motivated, will accept)
   - Staff/Principal→Senior = step DOWN (unlikely to accept, will be bored)
   - Manager→Senior IC = career pivot (very unlikely unless explicitly seeking)

3. **Seniority Reality Check**: For a ${this.capitalizeLevel(jobContext.level)} role:
   - Engineering Managers won't leave management for IC work
   - Staff/Principal engineers expect Staff+ roles, not Senior
   - Tech Leads might accept if role has growth path

Candidates:
${candidateList}

Return a JSON array ranked best to worst:
\`\`\`json
[{"id": "actual_id_here", "score": 88, "reason": "8yr Node.js/TypeScript at Stripe, AWS certified, exact stack match"},
 {"id": "actual_id_here", "score": 45, "reason": "Strong Java/Spring background but no Node.js experience"},
 {"id": "actual_id_here", "score": 25, "reason": "Currently Engineering Manager at Meta, unlikely to return to IC"}]
\`\`\`

CRITICAL RULES:
- Use the EXACT ID from "ID: xxx" field
- Include ALL candidates
- Score 0-100 based on BOTH tech fit AND career fit

REASON FORMAT (BE SPECIFIC, NOT GENERIC):
- GOOD: "12yr CTO at fintech startup, scaled team 10→200, board experience"
- GOOD: "Senior Backend at Google, Python/Go/K8s, 6 years"
- BAD: "Title match is good" (too generic)
- BAD: "Exact title match is KING" (DO NOT repeat scoring rules)
- BAD: "Company scale is reasonable" (say WHICH company and WHY)

Each reason MUST mention: candidate's actual company OR specific skills OR years of experience.
Never repeat phrases from the scoring rubric in the reason.`;

        try {
            const result = await model.generateContent(prompt);
            const response = result.response;
            const responseText = response.text();

            // Log finish reason and token usage for debugging
            const candidate = response.candidates?.[0];
            const finishReason = candidate?.finishReason || 'unknown';
            const tokenCount = response.usageMetadata?.candidatesTokenCount || 'unknown';
            console.log(`[GeminiRerank] Response: ${responseText.length} chars, finishReason: ${finishReason}, tokens: ${tokenCount}`);

            // Parse ranking response with multiple strategies
            const rankings = this.parseRankingResponseRobust(responseText, candidates, jobContext);
            return rankings;

        } catch (error: any) {
            console.error('[GeminiRerank] Rank pass failed:', error.message);
            // On failure, return default scores using improved fallback
            return this.fallbackRanking(candidates, jobContext);
        }
    }

    /**
     * PASS 2 (Batched): Process candidates in batches to avoid token overflow
     * and improve parse reliability
     */
    private async deepRankBatched(
        model: any,
        candidates: CandidateForReranking[],
        jobContext: JobContext
    ): Promise<RerankResult[]> {
        const BATCH_SIZE = 10;  // Process 10 candidates at a time to avoid response truncation
        const allResults: RerankResult[] = [];
        const processedIds = new Set<string>();

        // Split candidates into batches
        const batches = this.chunkArray(candidates, BATCH_SIZE);
        console.log(`[GeminiRerank] Processing ${batches.length} batches of up to ${BATCH_SIZE} candidates each`);

        for (let i = 0; i < batches.length; i++) {
            const batch = batches[i];
            console.log(`[GeminiRerank] Processing batch ${i + 1}/${batches.length} (${batch.length} candidates)`);

            try {
                const batchResults = await this.deepRank(model, batch, jobContext);

                // Add results, avoiding duplicates
                for (const result of batchResults) {
                    if (!processedIds.has(result.candidate_id)) {
                        // Normalize score to 0-100 range
                        allResults.push({
                            ...result,
                            score: this.normalizeScore(result.score)
                        });
                        processedIds.add(result.candidate_id);
                    }
                }

                console.log(`[GeminiRerank] Batch ${i + 1} returned ${batchResults.length} results`);

            } catch (error: any) {
                console.error(`[GeminiRerank] Batch ${i + 1} failed:`, error.message);
                // Add fallback scores for failed batch
                for (const candidate of batch) {
                    if (!processedIds.has(candidate.candidate_id)) {
                        const fallbackResults = this.fallbackRanking([candidate], jobContext);
                        allResults.push(...fallbackResults);
                        processedIds.add(candidate.candidate_id);
                    }
                }
            }
        }

        // Sort all results by score descending
        allResults.sort((a, b) => b.score - a.score);

        // Ensure we have results for all candidates (fill gaps with fallback)
        const resultIds = new Set(allResults.map(r => r.candidate_id));
        for (const candidate of candidates) {
            if (!resultIds.has(candidate.candidate_id)) {
                const fallbackResults = this.fallbackRanking([candidate], jobContext);
                allResults.push(...fallbackResults);
            }
        }

        return allResults;
    }

    /**
     * Helper to split array into chunks
     */
    private chunkArray<T>(array: T[], size: number): T[][] {
        const chunks: T[][] = [];
        for (let i = 0; i < array.length; i += size) {
            chunks.push(array.slice(i, i + size));
        }
        return chunks;
    }

    /**
     * Normalize score to 0-100 range
     * Handles cases where LLM returns 0-1 scale or out-of-range values
     */
    private normalizeScore(score: number): number {
        // If score looks like 0-1 scale, convert to 0-100
        if (score <= 1 && score >= 0) {
            return Math.round(score * 100);
        }
        // Clamp to valid range
        return Math.max(0, Math.min(100, Math.round(score)));
    }

    /**
     * Build a concise scoring rubric for the deep rank pass
     */
    private buildScoringRubric(func: string, level: string, specialty: string | null): string {
        if (func === 'engineering' && specialty) {
            return `SCORING RUBRIC:
- 85-100: ${this.capitalizeLevel(level)} ${specialty}/Software Engineer with exact match
- 75-84: Fullstack or ${specialty} at adjacent level (stepping UP is good)
- 55-74: SRE/Platform/DevOps (infrastructure overlap)
- 35-54: Wrong specialty (${this.getOppositeSpecialty(specialty)})
- 15-34: Leadership stepping DOWN (Tech Lead, Manager) - unlikely to accept
- 0-15: Principal/Staff/Director+ or wrong function`;
        }

        return `SCORING RUBRIC:
- 85-100: Exact ${level} level in ${func}, ready for role
- 70-84: One level below stepping UP (motivated)
- 50-69: Adjacent function with transferable skills
- 25-49: Overqualified (stepping DOWN)
- 0-24: Wrong function or significantly mismatched`;
    }

    /**
     * Build tech stack guidance for the prompt
     * Helps Gemini understand that Node.js roles need Node.js developers, not Java developers
     */
    private buildTechStackGuidance(jobContext: JobContext): string {
        if (!jobContext.requiredSkills?.length) return '';

        const primarySkills = jobContext.requiredSkills.slice(0, 5);
        const avoidSkills = jobContext.avoidSkills || [];

        return `
REQUIRED TECH STACK: ${primarySkills.join(', ')}
- Candidates with 3+ required skills: Excellent tech fit (+20 to score)
- Candidates with 1-2 required skills: Partial fit (no penalty)
- Candidates with 0 required skills but related stack: Poor fit (-15)
- Candidates with ALTERNATIVE stacks (e.g., Java when Node.js needed): Wrong fit (-25)

${avoidSkills.length ? `AVOID: ${avoidSkills.join(', ')} - legacy or mismatched tech` : ''}

IMPORTANT: "Backend" alone is insufficient. A Java Spring developer is NOT a good fit for a Node.js/NestJS role - different ecosystems, different patterns.`;
    }

    /**
     * Build seniority guidance for the prompt
     * Helps Gemini understand that managers won't step down to IC roles
     */
    private buildSeniorityGuidance(jobContext: JobContext): string {
        const level = jobContext.level?.toLowerCase() || 'senior';

        // Define who would realistically take this role
        const guidance: Record<string, string> = {
            'senior': `
SENIORITY CONSTRAINTS FOR SENIOR IC ROLE:
- IDEAL: Senior Engineers, Senior Developers (exact match)
- GOOD: Mid-level engineers stepping UP (motivated, will grow)
- MARGINAL: Leads if seeking IC focus (rare but possible)
- POOR: Staff/Principal Engineers (overqualified, will be bored)
- UNLIKELY: Engineering Managers (won't leave management track)
- EXCLUDE: Directors, VPs, Heads of (completely wrong level)`,

            'mid': `
SENIORITY CONSTRAINTS FOR MID-LEVEL ROLE:
- IDEAL: Mid-level Engineers (exact match)
- GOOD: Junior engineers stepping UP (eager to grow)
- POOR: Senior engineers (why step down?)
- UNLIKELY: Any management or staff+ level`,

            'staff': `
SENIORITY CONSTRAINTS FOR STAFF ROLE:
- IDEAL: Staff Engineers, Senior Engineers ready to step up
- GOOD: Tech Leads seeking IC track
- MARGINAL: Principal if role has scope
- UNLIKELY: Managers (different track)`,

            'principal': `
SENIORITY CONSTRAINTS FOR PRINCIPAL ROLE:
- IDEAL: Principal Engineers, Staff Engineers stepping up
- GOOD: Distinguished Engineers at smaller companies
- MARGINAL: Directors seeking IC track
- UNLIKELY: VPs (different track)`,

            'manager': `
SENIORITY CONSTRAINTS FOR MANAGER ROLE:
- IDEAL: Engineering Managers (exact match)
- GOOD: Tech Leads stepping into management
- GOOD: Senior engineers seeking management
- UNLIKELY: Directors (stepping down)`,

            'director': `
SENIORITY CONSTRAINTS FOR DIRECTOR ROLE:
- IDEAL: Directors (exact match)
- GOOD: Senior Managers stepping up
- GOOD: VPs at smaller companies
- UNLIKELY: C-level (stepping down)`,

            'c-level': `
SENIORITY CONSTRAINTS FOR C-LEVEL ROLE (CTO, CPO, CEO, Chief):
- IDEAL: Current C-level executives - CTOs, CPOs, CEOs (90-100 score)
- GOOD: VPs/SVPs stepping up, especially with board exposure (75-89 score)
- GOOD: Directors from FAANG/large enterprises with broad scope (70-84 score)
- MARGINAL: Senior/Staff engineers with founder experience (50-69 score)
- UNLIKELY: Managers, Senior Engineers without leadership scope (30-49 score)

FOR CTO/CPO/CEO SEARCHES:
- Current executives with same title score highest
- Company scale matters: CTO at 500+ person company > CTO at 10-person startup
- Look for: board exposure, investor relations, team scaling experience
- Don't penalize sparse profiles - executives often have brief LinkedIn summaries`,

            'vp': `
SENIORITY CONSTRAINTS FOR VP ROLE:
- IDEAL: VPs, SVPs (exact match) - 85-100 score
- GOOD: Directors stepping up with strong track record - 70-84 score
- GOOD: C-level at smaller companies seeking larger scope - 70-84 score
- MARGINAL: Senior Managers with executive potential - 55-69 score
- UNLIKELY: ICs without management experience`,
        };

        return guidance[level] || guidance['senior'];
    }

    /**
     * Get opposite specialty for filtering
     */
    private getOppositeSpecialty(specialty: string): string {
        const opposites: Record<string, string> = {
            'backend': 'Frontend, Mobile, QA',
            'frontend': 'Backend, DevOps, Data',
            'mobile': 'Backend, DevOps, Data',
            'data': 'Frontend, Mobile',
            'platform': 'Frontend, Mobile',
            'devops': 'Frontend, Mobile'
        };
        return opposites[specialty] || 'other specialties';
    }

    /**
     * Parse filter response (Pass 1)
     * Returns list of candidate IDs to keep
     */
    private parseFilterResponse(responseText: string, candidates: CandidateForReranking[]): string[] {
        try {
            // Extract JSON using multiple strategies
            const jsonStr = this.extractJson(responseText);
            if (!jsonStr) {
                console.warn('[GeminiRerank] No JSON found in filter response');
                return candidates.map(c => c.candidate_id);
            }

            const parsed = JSON.parse(jsonStr);

            // Get the "keep" array of indices
            const keepIndices: number[] = parsed.keep || [];

            // Convert indices to candidate IDs
            const keepIds = keepIndices
                .filter(idx => idx >= 1 && idx <= candidates.length)
                .map(idx => candidates[idx - 1].candidate_id);

            return keepIds.length > 0 ? keepIds : candidates.map(c => c.candidate_id);

        } catch (error: any) {
            console.error('[GeminiRerank] Filter parse failed:', error.message);
            console.error('[GeminiRerank] Filter response:', responseText.substring(0, 300));
            // On parse failure, keep all candidates
            return candidates.map(c => c.candidate_id);
        }
    }

    /**
     * Parse ranking response with multiple extraction strategies (Pass 2)
     */
    private parseRankingResponseRobust(
        responseText: string,
        candidates: CandidateForReranking[],
        jobContext?: JobContext
    ): RerankResult[] {
        const candidateIdSet = new Set(candidates.map(c => c.candidate_id));
        const candidateByIndex = new Map(candidates.map((c, idx) => [String(idx + 1), c.candidate_id]));
        // Build name-to-ID map for name-based recovery
        const candidateByName = new Map(candidates.map(c => [
            (c.name || '').toLowerCase().trim(),
            c.candidate_id
        ]));

        try {
            // Extract JSON using multiple strategies
            const jsonStr = this.extractJson(responseText);
            if (!jsonStr) {
                console.error('[GeminiRerank] No JSON found in rank response');
                console.error('[GeminiRerank] Full response:', responseText);
                return this.fallbackRanking(candidates, jobContext);
            }

            const parsed = JSON.parse(jsonStr);

            // Handle both array and object-with-array responses
            let rankings: any[];
            if (Array.isArray(parsed)) {
                rankings = parsed;
            } else if (parsed && typeof parsed === 'object') {
                // Gemini sometimes wraps in object: {"rankings": [...]} or {"candidates": [...]}
                rankings = parsed.rankings || parsed.candidates || parsed.results ||
                           parsed.data || Object.values(parsed).find(v => Array.isArray(v)) as any[];
                if (!rankings) {
                    console.error('[GeminiRerank] Object response has no array property:', Object.keys(parsed));
                    return this.fallbackRanking(candidates, jobContext);
                }
                console.log(`[GeminiRerank] Unwrapped array from object wrapper`);
            } else {
                console.error('[GeminiRerank] Response is neither array nor object');
                return this.fallbackRanking(candidates, jobContext);
            }

            // Log sample of what Gemini returned for debugging
            if (rankings.length > 0) {
                const sample = rankings[0];
                console.log(`[GeminiRerank] Sample item keys: ${Object.keys(sample).join(', ')}`);
                console.log(`[GeminiRerank] Sample item: id=${sample.id}, candidate_id=${sample.candidate_id}, name=${sample.name}`);
            }

            // Map results with ID recovery
            const results: RerankResult[] = [];
            let recoveredCount = 0;

            for (const item of rankings) {
                let candidateId = item.id || item.candidate_id || '';

                // Strategy 1: Direct ID match
                if (candidateIdSet.has(candidateId)) {
                    results.push({
                        candidate_id: candidateId,
                        score: typeof item.score === 'number' ? item.score : 50,
                        rationale: item.reason || item.rationale || 'Matched candidate'
                    });
                    continue;
                }

                // Strategy 2: Index recovery (if Gemini returned 1, 2, 3...)
                if (/^\d+$/.test(candidateId)) {
                    const actualId = candidateByIndex.get(candidateId);
                    if (actualId) {
                        recoveredCount++;
                        results.push({
                            candidate_id: actualId,
                            score: typeof item.score === 'number' ? item.score : 50,
                            rationale: item.reason || item.rationale || 'Matched candidate'
                        });
                        continue;
                    }
                }

                // Strategy 3: Partial ID match (first 8 chars)
                const partialMatch = Array.from(candidateIdSet).find(
                    id => id.startsWith(candidateId) || candidateId.startsWith(id.substring(0, 8))
                );
                if (partialMatch) {
                    recoveredCount++;
                    results.push({
                        candidate_id: partialMatch,
                        score: typeof item.score === 'number' ? item.score : 50,
                        rationale: item.reason || item.rationale || 'Matched candidate'
                    });
                    continue;
                }

                // Strategy 4: Name-based recovery (if Gemini returned name instead of ID)
                const itemName = (item.name || item.candidate_name || '').toLowerCase().trim();
                if (itemName && candidateByName.has(itemName)) {
                    const actualId = candidateByName.get(itemName)!;
                    recoveredCount++;
                    results.push({
                        candidate_id: actualId,
                        score: typeof item.score === 'number' ? item.score : 50,
                        rationale: item.reason || item.rationale || 'Matched candidate'
                    });
                    continue;
                }

                // Strategy 5: Fuzzy name match (partial name in response)
                if (itemName) {
                    const fuzzyMatch = Array.from(candidateByName.entries()).find(([name]) =>
                        name.includes(itemName) || itemName.includes(name)
                    );
                    if (fuzzyMatch) {
                        recoveredCount++;
                        results.push({
                            candidate_id: fuzzyMatch[1],
                            score: typeof item.score === 'number' ? item.score : 50,
                            rationale: item.reason || item.rationale || 'Matched candidate'
                        });
                    }
                }
            }

            if (recoveredCount > 0) {
                console.log(`[GeminiRerank] Recovered ${recoveredCount} IDs via fallback strategies`);
            }

            // If we got some results, return them
            if (results.length > 0) {
                console.log(`[GeminiRerank] Parsed ${results.length}/${rankings.length} rankings successfully`);
                return results;
            }

            console.error('[GeminiRerank] No valid IDs matched');
            return this.fallbackRanking(candidates, jobContext);

        } catch (error: any) {
            console.error('[GeminiRerank] Rank parse failed:', error.message);
            console.error('[GeminiRerank] Full response:', responseText);
            return this.fallbackRanking(candidates, jobContext);
        }
    }

    /**
     * Extract JSON from response using multiple strategies
     * Handles: code blocks, trailing text, object wrappers, markdown artifacts, truncated responses
     */
    private extractJson(text: string): string | null {
        let json: string | null = null;

        // Strategy 1: Code block with json marker
        const codeBlockMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
        if (codeBlockMatch) {
            json = codeBlockMatch[1].trim();
        } else {
            // Strategy 2: Find array starting with [ and ending with ]
            const arrayStart = text.indexOf('[');
            const arrayEnd = text.lastIndexOf(']');
            if (arrayStart !== -1 && arrayEnd > arrayStart) {
                json = text.substring(arrayStart, arrayEnd + 1);
            } else if (arrayStart !== -1) {
                // Array started but no closing bracket - truncated response
                json = text.substring(arrayStart);
            }
        }

        if (!json) {
            // Strategy 3: Find object starting with { and ending with }
            const objectStart = text.indexOf('{');
            const objectEnd = text.lastIndexOf('}');
            if (objectStart !== -1 && objectEnd > objectStart) {
                json = text.substring(objectStart, objectEnd + 1);
            }
        }

        if (!json) return null;

        // Try to repair truncated JSON
        json = this.repairTruncatedJson(json);

        return json;
    }

    /**
     * Attempt to repair truncated JSON arrays
     * Handles cases where Gemini response was cut off mid-array
     */
    private repairTruncatedJson(json: string): string {
        // First, try parsing as-is
        try {
            JSON.parse(json);
            return json; // Valid JSON, return as-is
        } catch (e) {
            // JSON is malformed, try to repair
        }

        // Count open/close brackets to detect truncation
        let openBrackets = 0;
        let openBraces = 0;
        let inString = false;
        let escapeNext = false;

        for (const char of json) {
            if (escapeNext) {
                escapeNext = false;
                continue;
            }
            if (char === '\\') {
                escapeNext = true;
                continue;
            }
            if (char === '"') {
                inString = !inString;
                continue;
            }
            if (inString) continue;

            if (char === '[') openBrackets++;
            if (char === ']') openBrackets--;
            if (char === '{') openBraces++;
            if (char === '}') openBraces--;
        }

        // If we have unclosed structures, try to close them
        if (openBrackets > 0 || openBraces > 0) {
            console.log(`[GeminiRerank] Attempting to repair truncated JSON (${openBrackets} unclosed brackets, ${openBraces} unclosed braces)`);

            // Find the last complete object in the array
            // Look for the last "}," or "}" that's properly balanced
            let repairedJson = json.trim();

            // Remove trailing incomplete content after last complete object
            // Find last complete object by looking for pattern: }"reason": "..."}
            const lastCompleteObjectMatch = repairedJson.match(/^([\s\S]*\})\s*,?\s*\{[^}]*$/);
            if (lastCompleteObjectMatch) {
                repairedJson = lastCompleteObjectMatch[1];
            }

            // Close any open braces
            for (let i = 0; i < openBraces; i++) {
                repairedJson += '}';
            }

            // Close any open brackets
            for (let i = 0; i < openBrackets; i++) {
                repairedJson += ']';
            }

            // Verify the repaired JSON is valid
            try {
                JSON.parse(repairedJson);
                console.log(`[GeminiRerank] JSON repair successful`);
                return repairedJson;
            } catch (e) {
                // Repair failed, try more aggressive approach
                // Find all complete objects and rebuild array

                // Strategy 1: Match objects with complete reason strings
                let objectMatches = json.matchAll(/\{\s*"id"\s*:\s*"[^"]+"\s*,\s*"score"\s*:\s*\d+\s*,\s*"reason"\s*:\s*"[^"]*"\s*\}/g);
                let objects = Array.from(objectMatches).map(m => m[0]);

                // Strategy 2: If that fails, try matching objects that end with } even if reason is cut off
                if (objects.length === 0) {
                    // Match any object with id and score, reason can be partial
                    objectMatches = json.matchAll(/\{\s*"id"\s*:\s*"([^"]+)"\s*,\s*"score"\s*:\s*(\d+)\s*,\s*"reason"\s*:\s*"([^}]*)"\s*\}/g);
                    objects = Array.from(objectMatches).map(m => m[0]);
                }

                // Strategy 3: Extract id/score pairs and create minimal objects
                if (objects.length === 0) {
                    const idScoreMatches = json.matchAll(/"id"\s*:\s*"([^"]+)"\s*,\s*"score"\s*:\s*(\d+)/g);
                    objects = Array.from(idScoreMatches).map(m =>
                        `{"id":"${m[1]}","score":${m[2]},"reason":"Parsed from truncated response"}`
                    );
                }

                if (objects.length > 0) {
                    const rebuiltJson = '[' + objects.join(',') + ']';
                    try {
                        JSON.parse(rebuiltJson);
                        console.log(`[GeminiRerank] JSON rebuilt from ${objects.length} complete objects`);
                        return rebuiltJson;
                    } catch (e2) {
                        // Even rebuilt JSON failed, try one more approach
                        console.error(`[GeminiRerank] Rebuilt JSON still invalid, trying minimal extraction`);
                    }
                }

                // Strategy 4: Ultimate fallback - extract any id/score pairs
                const minimalMatches = json.matchAll(/"id"\s*:\s*"([^"]+)"[^}]*"score"\s*:\s*(\d+)/g);
                const minimalObjects = Array.from(minimalMatches).map(m =>
                    `{"id":"${m[1]}","score":${m[2]},"reason":"Extracted from malformed response"}`
                );
                if (minimalObjects.length > 0) {
                    const minimalJson = '[' + minimalObjects.join(',') + ']';
                    try {
                        JSON.parse(minimalJson);
                        console.log(`[GeminiRerank] JSON minimally rebuilt from ${minimalObjects.length} id/score pairs`);
                        return minimalJson;
                    } catch (e3) {
                        // Complete failure
                    }
                }
            }
        }

        return json; // Return original if repair failed
    }

    /**
     * Improved fallback ranking when LLM fails
     * Uses candidate metadata to compute meaningful scores instead of just position
     */
    private fallbackRanking(candidates: CandidateForReranking[], jobContext?: JobContext): RerankResult[] {
        // Define skill sets for matching
        const backendSkills = ['python', 'java', 'go', 'golang', 'node', 'nodejs', 'sql', 'postgresql', 'mysql', 'mongodb', 'aws', 'docker', 'kubernetes', 'redis', 'kafka', 'spring', 'django', 'fastapi', 'graphql', 'rest', 'api', 'microservices'];
        const frontendSkills = ['react', 'vue', 'angular', 'javascript', 'typescript', 'css', 'html', 'webpack', 'nextjs', 'gatsby', 'redux', 'tailwind'];
        const dataSkills = ['python', 'sql', 'spark', 'hadoop', 'tensorflow', 'pytorch', 'pandas', 'numpy', 'ml', 'machine learning', 'data pipeline', 'airflow', 'dbt'];
        const platformSkills = ['kubernetes', 'docker', 'terraform', 'aws', 'gcp', 'azure', 'ci/cd', 'jenkins', 'github actions', 'ansible', 'helm', 'prometheus', 'grafana'];

        // Choose skill set based on job context
        let relevantSkills = backendSkills;  // Default to backend
        const specialty = jobContext?.title ? this.extractSpecialtyFromTitle(jobContext.title) : null;

        if (specialty === 'frontend') {
            relevantSkills = frontendSkills;
        } else if (specialty === 'data') {
            relevantSkills = dataSkills;
        } else if (specialty === 'platform' || specialty === 'devops') {
            relevantSkills = platformSkills;
        }

        return candidates.map((c, idx) => {
            // Base score decreases with position (retrieval order matters)
            let score = 70 - (idx * 1.2);

            // Bonus for matching skills
            const candidateSkills = (c.skills || []).map(s => s.toLowerCase());
            const matchedSkills = relevantSkills.filter(skill =>
                candidateSkills.some(cs => cs.includes(skill))
            );
            score += matchedSkills.length * 2.5;

            // Bonus for seniority match in title
            const roleLevel = this.extractLevelFromRole(c.current_role);
            const targetLevel = jobContext?.level || 'senior';
            if (roleLevel === targetLevel) {
                score += 5;
            } else if (this.isOneStepUp(roleLevel, targetLevel)) {
                // Stepping up is good (motivated candidate)
                score += 3;
            }

            // Bonus for relevant experience years
            const yearsExp = c.years_experience || 0;
            if (targetLevel === 'senior' && yearsExp >= 5 && yearsExp <= 12) {
                score += 3;
            } else if (targetLevel === 'mid' && yearsExp >= 2 && yearsExp <= 6) {
                score += 3;
            }

            // Clamp to reasonable range (not too high, not too low)
            score = Math.max(20, Math.min(85, Math.round(score)));

            // Build rationale
            const rationaleItems: string[] = [];
            if (matchedSkills.length > 0) {
                rationaleItems.push(`${matchedSkills.length} relevant skills`);
            }
            if (roleLevel) {
                rationaleItems.push(`${roleLevel} level`);
            }
            if (yearsExp > 0) {
                rationaleItems.push(`${yearsExp} years exp`);
            }

            const rationale = rationaleItems.length > 0
                ? `Fallback scoring: ${rationaleItems.join(', ')}`
                : 'Fallback scoring based on retrieval position';

            return {
                candidate_id: c.candidate_id,
                score,
                rationale
            };
        }).sort((a, b) => b.score - a.score);  // Sort by score
    }

    /**
     * Extract level from role title
     */
    private extractLevelFromRole(role: string | undefined): string | null {
        if (!role) return null;
        const roleLower = role.toLowerCase();

        if (roleLower.includes('junior') || roleLower.includes('associate')) return 'junior';
        if (roleLower.includes('senior') || roleLower.includes('sr.') || roleLower.includes('sr ')) return 'senior';
        if (roleLower.includes('staff')) return 'staff';
        if (roleLower.includes('principal')) return 'principal';
        if (roleLower.includes('lead') || roleLower.includes('manager')) return 'manager';
        if (roleLower.includes('director')) return 'director';
        if (roleLower.includes('vp') || roleLower.includes('vice president')) return 'vp';
        if (roleLower.includes('cto') || roleLower.includes('ceo') || roleLower.includes('chief')) return 'c-level';

        // Default to mid if no clear indicator
        return 'mid';
    }

    /**
     * Check if candidate is one step up (stepping up to role - motivated)
     */
    private isOneStepUp(candidateLevel: string | null, targetLevel: string): boolean {
        if (!candidateLevel) return false;
        const progression = ['junior', 'mid', 'senior', 'staff', 'principal', 'manager', 'director', 'vp', 'c-level'];
        const candidateIdx = progression.indexOf(candidateLevel);
        const targetIdx = progression.indexOf(targetLevel);
        return candidateIdx >= 0 && targetIdx >= 0 && targetIdx - candidateIdx === 1;
    }

    // ============================================================================
    // HELPER METHODS (kept lean for two-pass architecture)
    // ============================================================================

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
     * Extract engineering specialty from job title
     */
    private extractSpecialtyFromTitle(title: string): string | null {
        const titleLower = title.toLowerCase();

        // Backend indicators
        if (titleLower.includes('backend') || titleLower.includes('back-end') || titleLower.includes('back end')) {
            return 'backend';
        }

        // Frontend indicators
        if (titleLower.includes('frontend') || titleLower.includes('front-end') || titleLower.includes('front end')) {
            return 'frontend';
        }

        // Fullstack indicators
        if (titleLower.includes('fullstack') || titleLower.includes('full-stack') || titleLower.includes('full stack')) {
            return 'fullstack';
        }

        // Mobile indicators
        if (titleLower.includes('mobile') || titleLower.includes('ios') || titleLower.includes('android')) {
            return 'mobile';
        }

        // Data/ML indicators
        if (titleLower.includes('data engineer') || titleLower.includes('ml engineer') || titleLower.includes('machine learning')) {
            return 'data';
        }

        // DevOps/Platform/SRE indicators
        if (titleLower.includes('devops') || titleLower.includes('platform') || titleLower.includes('sre') || titleLower.includes('infrastructure')) {
            return 'platform';
        }

        return null;
    }

    /**
     * Get specialty-specific guidance for Gemini
     */
    private getSpecialtyGuidance(specialty: string): string {
        const specialtyGuides: Record<string, string> = {
            'backend': `For a BACKEND engineering role:

**HOW TO DETERMINE SPECIALTY - USE JOB TITLE FIRST:**
Judge specialty by the candidate's CURRENT JOB TITLE, not their skills list.
- "Backend Engineer", "Server Engineer", "API Engineer" → BACKEND
- "Software Engineer" with Java/Python/Go → likely BACKEND
- "Frontend Engineer", "UI Engineer" → FRONTEND (wrong specialty)
- "Fullstack Engineer" → FULLSTACK (good, has backend)
- "Software Developer" → look at primary skills

**IMPORTANT**: Many engineers have mixed skills. A Backend engineer might know React.
Don't penalize someone for having frontend skills IF their title is backend/software engineer.

**PRIORITY ORDER (score accordingly):**
1. BACKEND/SOFTWARE ENGINEERS with Java/Python/Go/Node.js (score 85-100)
2. FULLSTACK ENGINEERS (score 75-88): Have backend skills, great candidates
3. "Software Engineer/Developer" with backend-heavy skills (score 75-90)
4. SRE/PLATFORM/DEVOPS (score 55-70): Infrastructure focus, some backend overlap

**SCORE LOW (35-50) - TITLE SAYS FRONTEND:**
- Job title explicitly says "Frontend Engineer" or "UI Engineer"
- Job title says "Mobile Engineer" (iOS/Android)

**SCORE VERY LOW (20-35) - WRONG FUNCTION:**
- Product Managers, QA Engineers, Data Analysts - different function

**DO NOT penalize engineers who have some frontend skills but work as Software Engineers.**
A "Senior Software Engineer" with Java AND React is still a good backend candidate.`,

            'frontend': `For a FRONTEND engineering role:

**WHAT FRONTEND ENGINEERS DO:**
- Build user interfaces, client-side applications
- Work with HTML, CSS, JavaScript frameworks
- Handle UX, accessibility, browser compatibility
- Tech stack: React, Vue, Angular, TypeScript, CSS, etc.

**PRIORITY ORDER (score accordingly):**
1. FRONTEND ENGINEERS (score 85-100): Actual frontend/UI experience
2. FULLSTACK ENGINEERS (score 70-84): Have frontend skills but split focus
3. MOBILE ENGINEERS (score 60-70): Client-side UI experience

**SCORE LOW (30-45) - WRONG SPECIALTY:**
- BACKEND engineers - server-side focus, different skills
- DATA engineers - different function entirely
- PLATFORM/DEVOPS - infrastructure focus

**"Transferable skills" is NOT a good reason to score high.**
A Backend engineer is NOT a good frontend candidate regardless of seniority.`,

            'fullstack': `For a FULLSTACK engineering role:

**PRIORITY ORDER:**
1. FULLSTACK ENGINEERS (score 85-100): Proven full-stack experience
2. BACKEND + FRONTEND experience (score 80-90): Has done both
3. Strong BACKEND or FRONTEND ready to expand (score 65-75)

Fullstack roles need demonstrated experience across the stack.`,

            'platform': `For a PLATFORM/DEVOPS/SRE role:

**PRIORITY ORDER:**
1. PLATFORM/DEVOPS/SRE engineers (score 85-100): Direct experience
2. BACKEND engineers with infra experience (score 70-80)
3. System administrators stepping up (score 60-70)

**SCORE LOW:**
- FRONTEND engineers (different focus entirely)
- MOBILE engineers (different domain)`,

            'mobile': `For a MOBILE engineering role:

**PRIORITY ORDER:**
1. MOBILE engineers - iOS/Android (score 85-100)
2. FRONTEND engineers with mobile interest (score 60-70)

**SCORE LOW:**
- BACKEND engineers (server-side, not mobile)
- DATA engineers (different function)`,

            'data': `For a DATA/ML engineering role:

**PRIORITY ORDER:**
1. DATA/ML engineers (score 85-100)
2. BACKEND engineers with data pipeline experience (score 65-75)
3. Data scientists wanting to engineer (score 60-70)

**SCORE LOW:**
- FRONTEND engineers (different function)
- MOBILE engineers (different domain)`
        };

        return specialtyGuides[specialty] || '';
    }

    /**
     * Get level exclusions for career trajectory filtering
     */
    private getLevelExclusions(level: string): string {
        const exclusions: Record<string, string> = {
            'junior': 'Mid, Senior, Staff, Principal, Manager+ are overqualified',
            'mid': 'Senior, Staff, Principal, Manager+ are overqualified',
            'senior': 'Staff, Principal, Manager, Director, VP, C-level won\'t step down',
            'staff': 'Principal, Director, VP, C-level won\'t step down',
            'principal': 'Director, VP, C-level won\'t step down',
            'manager': 'Director, VP, C-level won\'t step down',
            'director': 'VP, C-level typically won\'t step down',
            'vp': 'C-level typically won\'t step down',
            'c-level': 'No exclusions - top of hierarchy'
        };
        return exclusions[level] || 'Consider career trajectory carefully';
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
