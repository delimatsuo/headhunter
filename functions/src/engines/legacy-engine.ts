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

        // ===== STEP 2: Multi-Pronged Retrieval =====
        if (options?.onProgress) {
            options.onProgress('Finding matching candidates...');
        }

        // Get level range for query
        const levelRange = this.getLevelRange(targetClassification.level);
        const targetCompanies = (options?.sourcingStrategy?.target_companies || [])
            .map((c: string) => c.toLowerCase());

        // Parallel retrieval from multiple sources
        const [functionPool, vectorPool] = await Promise.all([
            // Pool A: Function-based from Firestore
            this.searchByFunction(targetClassification.function, levelRange, 200),
            // Pool B: Vector similarity (existing results)
            Promise.resolve(vectorSearchResults || [])
        ]);

        console.log(`[LegacyEngine] Function pool: ${functionPool.length}, Vector pool: ${vectorPool.length}`);

        // ===== STEP 3: Merge & Score =====
        if (options?.onProgress) {
            options.onProgress('Ranking candidates...');
        }

        // Create maps for deduplication and scoring
        const candidateScores = new Map<string, {
            candidate: any;
            functionScore: number;
            vectorScore: number;
            companyScore: number;
            levelScore: number;
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
                sources: []
            };

            entry.functionScore = 60; // Strong boost for matching function
            entry.sources.push('function');
            entry.candidate = { ...entry.candidate, ...candidate }; // Merge data

            // Company pedigree
            entry.companyScore = this.calculateCompanyScore(candidate, targetCompanies);

            // Level match
            entry.levelScore = this.calculateLevelScore(
                candidate.searchable?.level || 'mid',
                targetClassification.level
            );

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
                sources: []
            };

            entry.vectorScore = 15; // Found in vector pool but not function pool
            entry.sources.push('vector');
            entry.candidate = { ...entry.candidate, ...candidate }; // Merge data

            // Also calculate company and level if not already done
            if (entry.companyScore === 0) {
                entry.companyScore = this.calculateCompanyScore(candidate, targetCompanies);
            }
            if (entry.levelScore === 0) {
                entry.levelScore = this.calculateLevelScore(
                    candidate.searchable?.level || candidate.profile?.current_level || 'mid',
                    targetClassification.level
                );
            }

            candidateScores.set(id, entry);
        }

        // Convert to array and calculate total scores
        let candidates = Array.from(candidateScores.values()).map(entry => ({
            ...entry.candidate,
            retrieval_score: entry.functionScore + entry.vectorScore + entry.companyScore + entry.levelScore,
            score_breakdown: {
                function: entry.functionScore,
                vector: entry.vectorScore,
                company: entry.companyScore,
                level: entry.levelScore
            },
            sources: entry.sources
        }));

        // Sort by retrieval score
        candidates.sort((a: any, b: any) => b.retrieval_score - a.retrieval_score);
        console.log(`[LegacyEngine] Merged ${candidates.length} unique candidates`);

        // ===== STEP 4: Cross-Encoder Reranking =====
        let searchStrategy = 'multi-signal retrieval';
        let useVertexRanking = false;

        try {
            if (options?.onProgress) {
                options.onProgress('AI reranking for precision...');
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
                    summary: profile.summary || ''
                };
            });

            const rankings = await this.rankingService.rerank(
                job.description || '',
                candidatesForRanking,
                { topN: 50 }
            );

            if (rankings && rankings.length > 0) {
                console.log(`[LegacyEngine] Vertex AI Ranking returned ${rankings.length} results`);
                const rankedMap = new Map(rankings.map(r => [r.candidate_id, r]));

                const rerankedTop = topCandidates.map((c: any) => {
                    const candidateId = c.candidate_id || c.id || '';
                    const ranking = rankedMap.get(candidateId);
                    const vertexScore = ranking ? ranking.rank_score * 100 : 0;
                    const retrievalScore = c.retrieval_score || 0;

                    // Combined: 40% Vertex + 60% Retrieval signals
                    const overallScore = (vertexScore * 0.4) + (retrievalScore * 0.6);

                    // Build rationale
                    const rationale: string[] = [];
                    if (c.sources?.includes('function')) {
                        rationale.push(`Matching ${targetClassification.function} function`);
                    }
                    if (c.score_breakdown?.company > 0) {
                        rationale.push('Top company experience');
                    }
                    if (ranking && ranking.rank_score >= 0.6) {
                        rationale.push('High AI relevance');
                    }
                    if (rationale.length === 0) {
                        rationale.push('Relevant background');
                    }

                    return {
                        ...c,
                        overall_score: overallScore,
                        vertex_score: vertexScore,
                        rationale
                    };
                }).sort((a: any, b: any) => b.overall_score - a.overall_score);

                const remainingCandidates = candidates.slice(50).map((c: any) => ({
                    ...c,
                    overall_score: c.retrieval_score || 0,
                    rationale: ['Additional match']
                }));

                candidates = [...rerankedTop, ...remainingCandidates];
                searchStrategy = 'multi-signal + vertex_ranking';
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
            // Query Firestore for candidates with matching function
            // Fetch more than needed since we'll score by level preference, not filter strictly
            const fetchLimit = Math.min(limit * 3, 500); // Fetch 3x to have variety

            let query = db.collection('candidates')
                .where('searchable.function', '==', targetFunction)
                .limit(fetchLimit);

            const snapshot = await query.get();

            // Don't filter by level - return all function matches
            // Let the scoring system handle level preference
            const candidates = snapshot.docs
                .map(doc => ({ id: doc.id, ...doc.data() }));

            console.log(`[LegacyEngine] Function query returned ${candidates.length} candidates for ${targetFunction}`);
            return candidates;
        } catch (error: any) {
            console.error('[LegacyEngine] Function search failed:', error.message);
            return [];
        }
    }

    private getLevelRange(targetLevel: string): string[] {
        // For executive roles, include all leadership levels
        // For a CPO search, we want: Director, VP, C-level, and even strong Managers/Seniors
        const levelOrder = ['intern', 'junior', 'mid', 'senior', 'manager', 'director', 'vp', 'c-level'];
        const targetIndex = levelOrder.indexOf(targetLevel);

        if (targetIndex === -1) return levelOrder;

        // For executive roles (director+), include from senior upward
        if (targetIndex >= 5) { // director, vp, c-level
            return ['senior', 'manager', 'director', 'vp', 'c-level'];
        }

        // For other roles, ±2 levels
        const minIndex = Math.max(0, targetIndex - 2);
        const maxIndex = Math.min(levelOrder.length - 1, targetIndex + 2);

        return levelOrder.slice(minIndex, maxIndex + 1);
    }

    private calculateCompanyScore(candidate: any, targetCompanies: string[]): number {
        const candidateCompanies = (candidate.searchable?.companies || [])
            .map((c: string) => c.toLowerCase());

        // Check target companies first
        if (targetCompanies.length > 0) {
            for (const tc of targetCompanies) {
                if (candidateCompanies.some((cc: string) => cc.includes(tc) || tc.includes(cc))) {
                    return 30; // High boost for target company
                }
            }
        }

        // Check top companies
        for (const topCompany of TOP_COMPANIES) {
            if (candidateCompanies.some((cc: string) => cc.includes(topCompany))) {
                return 15; // Medium boost for top company
            }
        }

        return 0;
    }

    private calculateLevelScore(candidateLevel: string, targetLevel: string): number {
        const levelOrder = ['intern', 'junior', 'mid', 'senior', 'manager', 'director', 'vp', 'c-level'];
        const candidateIndex = levelOrder.indexOf(candidateLevel.toLowerCase());
        const targetIndex = levelOrder.indexOf(targetLevel.toLowerCase());

        if (candidateIndex === -1 || targetIndex === -1) return 8; // Unknown level - neutral

        // For executive searches (c-level, vp, director)
        if (targetIndex >= 5) {
            // Directors, VPs, C-levels are all good for executive searches
            if (candidateIndex >= 5) return 25; // Director+ for Director+ search
            if (candidateIndex === 4) return 20; // Manager is good (step-up candidate)
            if (candidateIndex === 3) return 15; // Senior is acceptable
            return 5; // Mid and below - penalty
        }

        // For non-executive searches, use distance-based scoring
        const distance = Math.abs(candidateIndex - targetIndex);

        if (distance === 0) return 25; // Exact match
        if (distance === 1) return 20; // One level off
        if (distance === 2) return 12; // Two levels off
        return 5; // More than two levels off
    }
}
