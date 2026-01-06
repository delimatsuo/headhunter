/**
 * Legacy Engine (Fast Match) - v4.0 Multi-Signal Retrieval
 * 
 * Mimics senior recruiter search patterns:
 * 1. Function-based filtering (Product people for Product jobs)
 * 2. Title keyword matching
 * 3. Company pedigree boost
 * 4. Vector similarity for nuance
 * 5. Cross-encoder reranking
 * 
 * Target: 5-15 seconds. Best for most searches.
 */

import {
    IAIEngine,
    JobDescription,
    SearchOptions,
    SearchResult,
    CandidateMatch
} from './types';
import * as admin from 'firebase-admin';
import { getVertexRankingService } from '../vertex-ranking-service';
import { getGeminiRerankingService } from '../gemini-reranking-service';
import { getJobClassificationService, JobClassification } from '../job-classification-service';

const db = admin.firestore();

// Top companies for pedigree boost
const TOP_COMPANIES = [
    'google', 'meta', 'facebook', 'amazon', 'microsoft', 'apple', 'netflix',
    'nubank', 'ifood', 'mercado libre', 'mercadolibre', 'stone', 'quintoandar',
    'loft', 'creditas', 'pagseguro', 'inter', 'c6', 'btg',
    'stripe', 'airbnb', 'uber', 'lyft', 'doordash', 'instacart',
    'salesforce', 'oracle', 'sap', 'ibm', 'accenture', 'mckinsey', 'bain', 'bcg'
];

export class LegacyEngine implements IAIEngine {
    private rankingService = getVertexRankingService();
    private classificationService = getJobClassificationService();

    getName(): string {
        return 'legacy';
    }

    getLabel(): string {
        return '⚡ Fast Match';
    }

    getDescription(): string {
        return 'Senior recruiter-style search: function matching, company pedigree, and AI ranking.';
    }

    async search(
        job: JobDescription,
        options?: SearchOptions,
        vectorSearchResults?: any[]
    ): Promise<SearchResult> {
        const startTime = Date.now();
        const limit = options?.limit || 50;

        if (options?.onProgress) {
            options.onProgress('Analyzing job requirements...');
        }

        // ===== STEP 1: Classify Target Job =====
        let targetClassification: JobClassification;
        try {
            targetClassification = await this.classificationService.classifyJob(
                job.title || '',
                job.description
            );
            console.log('[LegacyEngine] Target classification:', targetClassification);
        } catch (error: any) {
            console.error('[LegacyEngine] Job classification failed:', error.message);
            targetClassification = {
                function: 'general',
                level: 'senior',
                domain: [],
                confidence: 0.5
            };
        }

        // ===== STEP 2: Determine Search Mode =====
        // Executive roles (C-level, VP, Director): Function + Level + Company tier
        // IC roles (Manager, Senior, Mid, Junior): Vector PRIMARY + Level
        const isExecutiveSearch = ['c-level', 'vp', 'director'].includes(targetClassification.level);
        const searchMode = isExecutiveSearch ? 'executive' : 'ic';

        console.log(`[LegacyEngine] Search mode: ${searchMode} (level: ${targetClassification.level})`);

        // ===== STEP 2.5: Detect Required Specialties =====
        const targetSpecialties = this.detectSpecialties(job.description, job.title || '');

        if (options?.onProgress) {
            options.onProgress(isExecutiveSearch
                ? 'Finding executive candidates...'
                : 'Finding matching candidates...');
        }

        // ===== STEP 3: Mode-Specific Retrieval =====
        const levelRange = this.getLevelRange(targetClassification.level);
        const targetCompanies = (options?.sourcingStrategy?.target_companies || [])
            .map((c: string) => c.toLowerCase());

        let functionPool: any[] = [];
        let vectorPool: any[] = vectorSearchResults || [];

        if (isExecutiveSearch) {
            // EXECUTIVE MODE: Function-based retrieval is PRIMARY
            // We want CTOs for CTO search, CPOs for CPO search - function matters
            functionPool = await this.searchByFunction(targetClassification.function, levelRange, 300);
            console.log(`[LegacyEngine] Executive mode - Function pool: ${functionPool.length}`);
        } else {
            // IC MODE: Vector similarity is PRIMARY
            // We want skill-matched candidates - vectors handle domain expertise
            functionPool = await this.searchByFunction(targetClassification.function, levelRange, 100);

            // CRITICAL: Filter vector pool by EFFECTIVE level (adjusted for company tier)
            // This allows startup CTOs to appear in VP searches at big companies
            // while still filtering out actual FAANG VPs stepping down
            const vectorPoolBeforeFilter = vectorPool.length;
            vectorPool = vectorPool.filter((c: any) => {
                const effectiveLevel = this.getEffectiveLevel(c);
                return levelRange.includes(effectiveLevel);
            });

            console.log(`[LegacyEngine] IC mode - Function pool: ${functionPool.length}, Vector pool: ${vectorPool.length} (filtered from ${vectorPoolBeforeFilter})`);
        }

        // ===== STEP 4: Mode-Specific Scoring =====
        if (options?.onProgress) {
            options.onProgress('Ranking candidates...');
        }

        // Scoring weights based on search mode
        // Added specialty weight to differentiate backend vs frontend for IC roles
        const weights = isExecutiveSearch
            ? { function: 50, vector: 15, company: 25, level: 35, specialty: 0 }  // Executive: function/company/level matter
            : { function: 25, vector: 25, company: 10, level: 15, specialty: 25 }; // IC: specialty matters for engineering subtypes

        const candidateScores = new Map<string, {
            candidate: any;
            functionScore: number;
            vectorScore: number;
            companyScore: number;
            levelScore: number;
            specialtyScore: number;
            sources: string[];
        }>();

        // Score function pool candidates
        for (const candidate of functionPool) {
            const id = candidate.id || candidate.candidate_id;
            const entry = candidateScores.get(id) || {
                candidate,
                functionScore: 0,
                vectorScore: 0,
                companyScore: 0,
                levelScore: 0,
                specialtyScore: 0,
                sources: []
            };

            // Use function confidence if available (from multi-function classification)
            // High confidence = full weight, low confidence = proportionally less
            const functionConfidence = candidate.function_confidence || 1.0;
            entry.functionScore = weights.function * functionConfidence;
            entry.sources.push('function');
            entry.candidate = { ...entry.candidate, ...candidate };

            // Company pedigree (weighted by mode)
            const rawCompanyScore = this.calculateCompanyScore(candidate, targetCompanies);
            entry.companyScore = (rawCompanyScore / 30) * weights.company;

            // Level match (with company tier boost)
            const rawLevelScore = this.calculateLevelScore(
                candidate.searchable?.level || 'mid',
                targetClassification.level,
                candidate
            );
            entry.levelScore = (rawLevelScore / 40) * weights.level;

            // Specialty match (backend vs frontend, etc.)
            const specialtyScore = this.calculateSpecialtyScore(candidate, targetSpecialties);
            entry.specialtyScore = specialtyScore * weights.specialty;

            candidateScores.set(id, entry);
        }

        // Score vector pool candidates
        for (const candidate of vectorPool) {
            const id = candidate.id || candidate.candidate_id;
            const entry = candidateScores.get(id) || {
                candidate,
                functionScore: 0,
                vectorScore: 0,
                companyScore: 0,
                levelScore: 0,
                specialtyScore: 0,
                sources: []
            };

            // Vector score - higher weight for IC mode
            entry.vectorScore = weights.vector;
            entry.sources.push('vector');
            entry.candidate = { ...entry.candidate, ...candidate };

            // Calculate company and level if not already done
            if (entry.companyScore === 0) {
                const rawCompanyScore = this.calculateCompanyScore(candidate, targetCompanies);
                entry.companyScore = (rawCompanyScore / 30) * weights.company;
            }
            if (entry.levelScore === 0) {
                const rawLevelScore = this.calculateLevelScore(
                    candidate.searchable?.level || candidate.profile?.current_level || 'mid',
                    targetClassification.level,
                    candidate
                );
                entry.levelScore = (rawLevelScore / 40) * weights.level;
            }

            // Specialty score for vector candidates too
            if (entry.specialtyScore === 0) {
                const specialtyScore = this.calculateSpecialtyScore(candidate, targetSpecialties);
                entry.specialtyScore = specialtyScore * weights.specialty;
            }

            candidateScores.set(id, entry);
        }

        // Convert to array and calculate total scores
        let candidates = Array.from(candidateScores.values()).map(entry => ({
            ...entry.candidate,
            retrieval_score: entry.functionScore + entry.vectorScore + entry.companyScore + entry.levelScore + entry.specialtyScore,
            score_breakdown: {
                function: entry.functionScore,
                vector: entry.vectorScore,
                company: entry.companyScore,
                level: entry.levelScore,
                specialty: entry.specialtyScore
            },
            sources: entry.sources,
            search_mode: searchMode
        }));

        // Sort by retrieval score
        candidates.sort((a: any, b: any) => b.retrieval_score - a.retrieval_score);
        console.log(`[LegacyEngine] ${searchMode.toUpperCase()} mode - Merged ${candidates.length} unique candidates`);

        // ===== STEP 4: Cross-Encoder Reranking =====
        let searchStrategy = 'multi-signal retrieval';
        let useVertexRanking = false;

        try {
            if (options?.onProgress) {
                options.onProgress('AI reasoning for best match...');
            }

            const topCandidates = candidates.slice(0, 50);
            const candidatesForRanking = topCandidates.map((c: any) => {
                const profile = c.profile || {};
                return {
                    candidate_id: c.candidate_id || c.id || '',
                    name: profile.name || c.name || 'Unknown',
                    current_role: profile.current_role || c.searchable?.title_keywords?.[0] || '',
                    years_experience: profile.years_experience || 0,
                    skills: profile.skills || profile.top_skills?.map((s: any) => s.skill || s) || [],
                    companies: c.searchable?.companies || profile.companies || [],
                };
            });

            // Use Gemini for instruction-following reranking
            const geminiService = getGeminiRerankingService();
            const jobContext = {
                function: targetClassification.function,
                level: targetClassification.level,
                title: job.title || `${targetClassification.level} ${targetClassification.function}`
            };

            console.log(`[LegacyEngine] Gemini reranking with context: ${JSON.stringify(jobContext)}`);

            const rankings = await geminiService.rerank(
                candidatesForRanking,
                jobContext,
                50
            );

            if (rankings && rankings.length > 0) {
                console.log(`[LegacyEngine] Gemini Reranking returned ${rankings.length} results`);

                // Debug: Log sample IDs to diagnose matching issues
                const sampleInputIds = candidatesForRanking.slice(0, 3).map(c => c.candidate_id);
                const sampleOutputIds = rankings.slice(0, 3).map(r => r.candidate_id);
                console.log(`[LegacyEngine] Sample input IDs: ${JSON.stringify(sampleInputIds)}`);
                console.log(`[LegacyEngine] Sample output IDs: ${JSON.stringify(sampleOutputIds)}`);

                const rankedMap = new Map(rankings.map(r => [r.candidate_id, r]));

                // Track match rate for debugging
                let matchCount = 0;
                const rerankedTop = topCandidates.map((c: any) => {
                    const candidateId = c.candidate_id || c.id || '';
                    const ranking = rankedMap.get(candidateId);
                    if (ranking) matchCount++;
                    const geminiScore = ranking ? ranking.score : 0;
                    const retrievalScore = c.retrieval_score || 0;

                    // Combined: 70% Gemini (follows hiring logic) + 30% Retrieval signals
                    const overallScore = (geminiScore * 0.7) + (retrievalScore * 0.3);

                    // Use Gemini's rationale if available
                    const rationale: string[] = [];
                    if (ranking?.rationale && ranking.rationale !== 'No explanation provided') {
                        rationale.push(ranking.rationale);
                    } else {
                        if (c.sources?.includes('function')) {
                            rationale.push(`Matching ${targetClassification.function} function`);
                        }
                        if (c.score_breakdown?.company > 0) {
                            rationale.push('Top company experience');
                        }
                    }
                    if (rationale.length === 0) {
                        rationale.push('Relevant background');
                    }

                    return {
                        ...c,
                        overall_score: overallScore,
                        gemini_score: geminiScore,
                        rationale
                    };
                }).sort((a: any, b: any) => b.overall_score - a.overall_score);

                const remainingCandidates = candidates.slice(50).map((c: any) => ({
                    ...c,
                    overall_score: c.retrieval_score || 0,
                    rationale: ['Additional match']
                }));

                candidates = [...rerankedTop, ...remainingCandidates];
                searchStrategy = 'multi-signal + gemini_rerank';
                useVertexRanking = true;
            }
        } catch (error: any) {
            console.error('[LegacyEngine] Vertex AI Ranking failed:', error.message);
            candidates = candidates.map((c: any) => ({
                ...c,
                overall_score: c.retrieval_score || 0,
                rationale: c.sources?.includes('function')
                    ? [`Matching ${targetClassification.function} function`]
                    : ['Relevant background']
            }));
        }

        // ===== STEP 5: Deduplicate =====
        const seenNames = new Set<string>();
        candidates = candidates.filter((c: any) => {
            const name = (c.profile?.name || c.name || '').toLowerCase().trim();
            if (!name || seenNames.has(name)) return false;
            seenNames.add(name);
            return true;
        });

        // ===== Convert to standard format =====
        const matches: CandidateMatch[] = candidates.slice(0, limit).map((c: any) => ({
            candidate_id: c.candidate_id || c.id || '',
            candidate: c,
            score: c.overall_score || 0,
            rationale: {
                overall_assessment: c.rationale?.join('. ') || 'Matched based on profile',
                strengths: c.rationale || [],
                gaps: [],
                risk_factors: []
            },
            match_metadata: {
                sources: c.sources,
                score_breakdown: c.score_breakdown,
                vertex_score: c.vertex_score,
                target_function: targetClassification.function,
                target_level: targetClassification.level,
                candidate_function: c.searchable?.function
            }
        }));

        const queryTime = Date.now() - startTime;
        console.log(`[LegacyEngine] Search completed in ${queryTime}ms, returned ${matches.length} matches`);

        return {
            matches,
            total_candidates: candidateScores.size,
            query_time_ms: queryTime,
            engine_used: this.getName(),
            engine_version: '4.0.0',
            metadata: {
                search_strategy: searchStrategy,
                used_vertex_ranking: useVertexRanking,
                target_classification: targetClassification
            }
        };
    }

    // ============================================================================
    // HELPER METHODS
    // ============================================================================

    private async searchByFunction(
        targetFunction: string,
        levelRange: string[],
        limit: number
    ): Promise<any[]> {
        try {
            const fetchLimit = Math.min(limit * 3, 500);

            // Query 1: Legacy single-function field (backward compatibility)
            const legacyQuery = db.collection('candidates')
                .where('searchable.function', '==', targetFunction)
                .limit(fetchLimit);

            const legacySnapshot = await legacyQuery.get();

            // Filter by EFFECTIVE level (adjusted for company tier)
            // This allows startup execs to appear in higher-tier role searches
            const candidates = legacySnapshot.docs
                .map(doc => ({ id: doc.id, ...doc.data() } as any))
                .filter((c: any) => {
                    const effectiveLevel = this.getEffectiveLevel(c);
                    return levelRange.includes(effectiveLevel);
                })
                .map((c: any) => {
                    // Calculate function confidence from multi-function array if available
                    let functionConfidence = 1.0; // Default for legacy single-function

                    if (c.searchable?.functions && Array.isArray(c.searchable.functions)) {
                        const matchingFunction = c.searchable.functions.find(
                            (f: any) => f.name === targetFunction
                        );
                        if (matchingFunction) {
                            functionConfidence = matchingFunction.confidence || 0.5;
                        }
                    }

                    return {
                        ...c,
                        function_confidence: functionConfidence
                    };
                });

            console.log(`[LegacyEngine] Function query: ${legacySnapshot.size} total, ${candidates.length} in level range [${levelRange.join(', ')}] for ${targetFunction}`);
            return candidates;
        } catch (error: any) {
            console.error('[LegacyEngine] Function search failed:', error.message);
            return [];
        }
    }

    private getLevelRange(targetLevel: string): string[] {
        // ===================================================================
        // RECRUITER MINDSET: Only show candidates who would be INTERESTED
        // - STEP UP: Junior → Mid, Manager → Director, etc. (INTERESTED)
        // - LATERAL: Same level at different company (INTERESTED)
        // - STEP DOWN: VP → Director, Senior → Mid (NOT INTERESTED)
        // ===================================================================

        if (targetLevel === 'c-level') {
            // For C-level (CEO, CTO, CPO): VPs and Directors stepping UP
            // Other C-levels might do lateral for right opportunity
            return ['vp', 'director', 'c-level'];
        }

        if (targetLevel === 'vp') {
            // For VP searches: Directors stepping UP, Senior (Staff/Principal from FAANG)
            // Other VPs might do lateral
            return ['director', 'senior', 'vp'];
        }

        if (targetLevel === 'director') {
            // For Director searches: Managers stepping UP
            // Other Directors might do lateral
            // C-level and VP won't step DOWN
            return ['manager', 'director'];
        }

        if (targetLevel === 'manager') {
            // For Manager searches: Seniors stepping into management
            // Other Managers might do lateral
            // Directors won't step DOWN
            return ['senior', 'manager'];
        }

        // For IC roles (senior, mid, junior)
        // KEY INSIGHT: Show candidates who would STEP UP into the role
        // Senior engineers won't take mid-level roles - they'd be stepping DOWN
        // But mid-level engineers would gladly take senior roles - stepping UP
        const levelOrder = ['intern', 'junior', 'mid', 'senior', 'manager'];
        const targetIndex = levelOrder.indexOf(targetLevel);

        if (targetIndex === -1) return levelOrder;

        // Show target level + one level BELOW (candidates stepping UP)
        // Don't show levels ABOVE - they won't be interested
        const minIndex = Math.max(0, targetIndex - 1);  // One level below can step up
        const maxIndex = targetIndex;  // Exact match, not above

        return levelOrder.slice(minIndex, maxIndex + 1);
    }

    // Company tiers for level adjustment (similar to levels.fyi)
    private static readonly COMPANY_TIERS: Record<string, number> = {
        // FAANG+ (Director here = VP elsewhere)
        'google': 2, 'meta': 2, 'facebook': 2, 'amazon': 2, 'apple': 2, 'microsoft': 2, 'netflix': 2,
        // Big Tech 
        'salesforce': 1, 'oracle': 1, 'adobe': 1, 'vmware': 1, 'cisco': 1, 'intel': 1, 'ibm': 1,
        // Top Unicorns
        'nubank': 1, 'stripe': 1, 'shopify': 1, 'uber': 1, 'lyft': 1, 'airbnb': 1, 'doordash': 1,
        // LatAm Tech Leaders
        'mercado libre': 1, 'mercadolibre': 1, 'ifood': 1, 'rappi': 1, 'stone': 1, 'pagseguro': 1,
        'quintoandar': 1, 'creditas': 1, 'loft': 1,
    };

    private getCompanyTier(candidate: any): number {
        const candidateCompanies = (candidate.searchable?.companies || [])
            .map((c: string) => c.toLowerCase());

        for (const company of candidateCompanies) {
            for (const [tierCompany, tier] of Object.entries(LegacyEngine.COMPANY_TIERS)) {
                if (company.includes(tierCompany)) {
                    return tier;
                }
            }
        }
        return 0; // Baseline (startup/unknown)
    }

    /**
     * Get effective level adjusted by company tier
     * 
     * LOGIC:
     * - FAANG Director (tier 2) = VP elsewhere → effective level stays 'director' for filtering
     *   but gets a boost in scoring
     * - Startup CTO (tier 0) = might be interested in VP at big company
     *   → effective level is 'director' (one step down)
     * 
     * For level filtering, we LOWER the effective level for low-tier companies
     * so that startup execs appear in searches for higher-tier roles
     */
    private getEffectiveLevel(candidate: any): string {
        const nominalLevel = (candidate.searchable?.level || 'mid').toLowerCase();
        const companyTier = this.getCompanyTier(candidate);

        // Level order for reference
        const levelOrder = ['intern', 'junior', 'mid', 'senior', 'manager', 'director', 'vp', 'c-level'];
        const currentIndex = levelOrder.indexOf(nominalLevel);

        if (currentIndex === -1) return nominalLevel;

        // If candidate is from FAANG (tier 2), their level is accurate
        // If candidate is from tier 0 (startup), their title may be inflated
        // We adjust DOWN by (2 - tier) levels for filtering purposes

        const adjustment = 2 - companyTier;  // tier 0 → -2, tier 1 → -1, tier 2 → 0
        const effectiveIndex = Math.max(0, currentIndex - adjustment);

        return levelOrder[effectiveIndex];
    }

    private calculateCompanyScore(candidate: any, targetCompanies: string[]): number {
        const candidateCompanies = (candidate.searchable?.companies || [])
            .map((c: string) => c.toLowerCase());

        // Check target companies first (highest priority)
        if (targetCompanies.length > 0) {
            for (const tc of targetCompanies) {
                if (candidateCompanies.some((cc: string) => cc.includes(tc) || tc.includes(cc))) {
                    return 30; // High boost for target company
                }
            }
        }

        // Company tier boost
        const tier = this.getCompanyTier(candidate);
        if (tier >= 2) return 20; // FAANG+
        if (tier >= 1) return 12; // Big Tech / Unicorn

        // Check other top companies not in tiers
        for (const topCompany of TOP_COMPANIES) {
            if (candidateCompanies.some((cc: string) => cc.includes(topCompany))) {
                return 8;
            }
        }

        return 0;
    }

    private calculateLevelScore(candidateLevel: string, targetLevel: string, candidate?: any): number {
        // Level order: intern(0) → junior(1) → mid(2) → senior(3) → manager(4) → director(5) → vp(6) → c-level(7)
        const levelOrder = ['intern', 'junior', 'mid', 'senior', 'manager', 'director', 'vp', 'c-level'];
        const candidateIndex = levelOrder.indexOf(candidateLevel.toLowerCase());
        const targetIndex = levelOrder.indexOf(targetLevel.toLowerCase());

        if (candidateIndex === -1 || targetIndex === -1) return 10; // Unknown level

        // Get company tier for level adjustment
        // A FAANG Director is like a VP elsewhere (tier +1 level effective)
        const companyTier = candidate ? this.getCompanyTier(candidate) : 0;
        const effectiveCandidateIndex = Math.min(candidateIndex + companyTier, levelOrder.length - 1);

        // EXECUTIVE SEARCHES (C-level, VP)
        if (targetIndex >= 6) { // c-level or vp
            // Score based on effective level proximity
            if (effectiveCandidateIndex >= 7) return 40; // Effective C-level
            if (effectiveCandidateIndex >= 6) return 35; // Effective VP
            if (effectiveCandidateIndex >= 5) return 25; // Effective Director
            if (effectiveCandidateIndex >= 3) return 15; // Senior (Staff/Principal from FAANG could work)
            return 0; // Too junior - shouldn't be in pool anyway
        }

        // DIRECTOR SEARCH
        if (targetIndex === 5) {
            if (effectiveCandidateIndex >= 6) return 35; // VP stepping down
            if (effectiveCandidateIndex >= 5) return 40; // Director exact
            if (effectiveCandidateIndex >= 4) return 25; // Manager stepping up
            return 10;
        }

        // MANAGER AND IC SEARCHES - use distance-based scoring
        const effectiveDistance = Math.abs(effectiveCandidateIndex - targetIndex);

        if (effectiveDistance === 0) return 40; // Exact match
        if (effectiveDistance === 1) return 30; // One level off
        if (effectiveDistance === 2) return 15; // Two levels off
        return 5; // More than two levels off
    }

    /**
     * Detect specialties needed from job description
     * Returns array of specialties like ['backend', 'microservices'] or ['frontend', 'react']
     */
    private detectSpecialties(jobDescription: string, jobTitle: string): string[] {
        const text = `${jobTitle} ${jobDescription}`.toLowerCase();
        const specialties: string[] = [];

        // Backend indicators
        const backendKeywords = ['backend', 'back-end', 'server-side', 'api', 'microservices',
            'ruby', 'python', 'java', 'golang', 'node.js', 'django', 'spring', 'rails',
            'database', 'sql', 'postgresql', 'mysql', 'mongodb', 'redis', 'kafka',
            'rest api', 'graphql', 'grpc', 'distributed systems', 'oop', 'object-oriented'];
        const backendMatches = backendKeywords.filter(kw => text.includes(kw)).length;
        if (backendMatches >= 2) specialties.push('backend');

        // Frontend indicators
        const frontendKeywords = ['frontend', 'front-end', 'front end', 'react', 'vue', 'angular',
            'javascript', 'typescript', 'css', 'html', 'ui developer', 'web developer',
            'responsive', 'spa', 'single page', 'browser', 'dom', 'webpack', 'next.js'];
        const frontendMatches = frontendKeywords.filter(kw => text.includes(kw)).length;
        if (frontendMatches >= 2) specialties.push('frontend');

        // Fullstack indicators
        if (text.includes('fullstack') || text.includes('full-stack') || text.includes('full stack')) {
            specialties.push('fullstack');
        }

        // Mobile indicators
        const mobileKeywords = ['mobile', 'ios', 'android', 'react native', 'flutter', 'swift', 'kotlin'];
        const mobileMatches = mobileKeywords.filter(kw => text.includes(kw)).length;
        if (mobileMatches >= 2) specialties.push('mobile');

        // DevOps/Infra indicators
        const devopsKeywords = ['devops', 'infrastructure', 'kubernetes', 'docker', 'terraform',
            'ci/cd', 'aws', 'gcp', 'azure', 'cloud', 'sre', 'platform engineer'];
        const devopsMatches = devopsKeywords.filter(kw => text.includes(kw)).length;
        if (devopsMatches >= 2) specialties.push('devops');

        // Data/ML indicators
        const dataKeywords = ['machine learning', 'ml engineer', 'data engineer', 'etl', 'spark',
            'airflow', 'data pipeline', 'tensorflow', 'pytorch', 'ai engineer'];
        const dataMatches = dataKeywords.filter(kw => text.includes(kw)).length;
        if (dataMatches >= 2) specialties.push('data');

        console.log(`[LegacyEngine] Detected specialties: ${specialties.join(', ') || 'none'}`);
        return specialties;
    }

    /**
     * Calculate specialty match score
     * Returns 0-1 based on how well candidate's specialties match job requirements
     */
    private calculateSpecialtyScore(candidate: any, targetSpecialties: string[]): number {
        if (!targetSpecialties.length) return 1.0; // No specific specialty needed

        const functions = candidate.searchable?.functions;
        if (!functions || !Array.isArray(functions)) return 0.5; // No specialty data

        let maxScore = 0;

        for (const func of functions) {
            const candidateSpecialties = func.specialties || [];
            const confidence = func.confidence || 0.5;

            for (const targetSpec of targetSpecialties) {
                // Direct match
                if (candidateSpecialties.includes(targetSpec)) {
                    maxScore = Math.max(maxScore, confidence);
                }
                // Fullstack matches both frontend and backend
                if (targetSpec === 'backend' && candidateSpecialties.includes('fullstack')) {
                    maxScore = Math.max(maxScore, confidence * 0.8);
                }
                if (targetSpec === 'frontend' && candidateSpecialties.includes('fullstack')) {
                    maxScore = Math.max(maxScore, confidence * 0.8);
                }
            }
        }

        return maxScore;
    }
}
