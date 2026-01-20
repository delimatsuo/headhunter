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
}

interface RerankResult {
    candidate_id: string;
    score: number;         // 0-100
    rationale: string;     // Why this candidate ranks here
}

// Internal types for two-pass architecture
interface FilterResult {
    keep: string[];      // Candidate IDs to keep
    remove: string[];    // Candidate IDs to remove
}

export class GeminiRerankingService {
    private genAI: GoogleGenerativeAI;
    private modelName: string = 'gemini-2.0-flash';

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
     * Pass 1: Quick filter with tiny prompt (~200 tokens)
     * Pass 2: Deep rank on filtered candidates (~500 tokens)
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

        // Limit total candidates to process
        const candidatesToProcess = candidates.slice(0, Math.min(topN * 2, 100));

        try {
            const model = this.genAI.getGenerativeModel({
                model: this.modelName,
                generationConfig: {
                    temperature: 0.1,  // Low temperature for consistent results
                    maxOutputTokens: 2048,
                }
            });

            // ===== PASS 1: Quick Filter =====
            console.log(`[GeminiRerank] Pass 1: Filtering ${candidatesToProcess.length} candidates`);
            const filteredIds = await this.quickFilter(model, candidatesToProcess, jobContext);

            // Get filtered candidates (keep order)
            const filteredCandidates = candidatesToProcess.filter(c =>
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

            // ===== PASS 2: Deep Rank =====
            // Only rank top candidates to keep prompt small
            const toRank = filteredCandidates.slice(0, Math.min(30, topN));
            console.log(`[GeminiRerank] Pass 2: Deep ranking ${toRank.length} candidates`);

            const rankings = await this.deepRank(model, toRank, jobContext);

            const latency = Date.now() - startTime;
            console.log(`[GeminiRerank] Completed in ${latency}ms, returned ${rankings.length} results`);

            // Track ID match rate
            const originalIdSet = new Set(candidatesToProcess.map(c => c.candidate_id));
            const matchedCount = rankings.filter(r => originalIdSet.has(r.candidate_id)).length;
            console.log(`[GeminiRerank] ID match rate: ${matchedCount}/${rankings.length}`);

            return rankings;

        } catch (error: any) {
            console.error('[GeminiRerank] Error:', error.message);
            // Fallback: return original order with default scores
            return candidatesToProcess.slice(0, topN).map((c, idx) => ({
                candidate_id: c.candidate_id,
                score: 100 - idx,
                rationale: 'Ranked by retrieval score (reranking unavailable)'
            }));
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

        const prompt = `You are ranking candidates for: ${roleTitle}

${rubric}

KEY PRINCIPLE: The best candidate is EXCITED about this opportunity.
- Mid→Senior = step UP (motivated)
- Principal/Staff→Senior = step DOWN (unlikely to accept)

Candidates:
${candidateList}

Return a JSON array ranked best to worst:
\`\`\`json
[{"id": "actual_id_here", "score": 88, "reason": "Senior Backend, 8yrs Python/AWS"},
 {"id": "actual_id_here", "score": 72, "reason": "Fullstack but strong backend"}]
\`\`\`

CRITICAL: Use the EXACT ID from "ID: xxx" field. Include ALL candidates. Score 0-100.`;

        try {
            const result = await model.generateContent(prompt);
            const responseText = result.response.text();

            // Parse ranking response with multiple strategies
            const rankings = this.parseRankingResponseRobust(responseText, candidates);
            return rankings;

        } catch (error: any) {
            console.error('[GeminiRerank] Rank pass failed:', error.message);
            // On failure, return default scores
            return candidates.map((c, idx) => ({
                candidate_id: c.candidate_id,
                score: 100 - (idx * 2),
                rationale: 'Fallback scoring (rank pass failed)'
            }));
        }
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
        candidates: CandidateForReranking[]
    ): RerankResult[] {
        const candidateIdSet = new Set(candidates.map(c => c.candidate_id));
        const candidateByIndex = new Map(candidates.map((c, idx) => [String(idx + 1), c.candidate_id]));

        try {
            // Extract JSON using multiple strategies
            const jsonStr = this.extractJson(responseText);
            if (!jsonStr) {
                console.error('[GeminiRerank] No JSON found in rank response');
                console.error('[GeminiRerank] Full response:', responseText);
                return this.fallbackRanking(candidates);
            }

            const parsed = JSON.parse(jsonStr);

            if (!Array.isArray(parsed)) {
                console.error('[GeminiRerank] Response is not an array');
                return this.fallbackRanking(candidates);
            }

            // Map results with ID recovery
            const results: RerankResult[] = [];
            let recoveredCount = 0;

            for (const item of parsed) {
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
                }
            }

            if (recoveredCount > 0) {
                console.log(`[GeminiRerank] Recovered ${recoveredCount} IDs via fallback strategies`);
            }

            // If we got some results, return them
            if (results.length > 0) {
                console.log(`[GeminiRerank] Parsed ${results.length}/${parsed.length} rankings successfully`);
                return results;
            }

            console.error('[GeminiRerank] No valid IDs matched');
            return this.fallbackRanking(candidates);

        } catch (error: any) {
            console.error('[GeminiRerank] Rank parse failed:', error.message);
            console.error('[GeminiRerank] Full response:', responseText);
            return this.fallbackRanking(candidates);
        }
    }

    /**
     * Extract JSON from response using multiple strategies
     */
    private extractJson(text: string): string | null {
        // Strategy 1: Code block with json marker
        const codeBlockMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
        if (codeBlockMatch) {
            return codeBlockMatch[1].trim();
        }

        // Strategy 2: Find array starting with [
        const arrayMatch = text.match(/\[\s*\{[\s\S]*\}\s*\]/);
        if (arrayMatch) {
            return arrayMatch[0];
        }

        // Strategy 3: Find object starting with {
        const objectMatch = text.match(/\{\s*"[\s\S]*\}/);
        if (objectMatch) {
            return objectMatch[0];
        }

        return null;
    }

    /**
     * Fallback ranking when parsing fails
     */
    private fallbackRanking(candidates: CandidateForReranking[]): RerankResult[] {
        return candidates.map((c, idx) => ({
            candidate_id: c.candidate_id,
            score: 100 - (idx * 2),
            rationale: 'Fallback scoring (parse error)'
        }));
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
