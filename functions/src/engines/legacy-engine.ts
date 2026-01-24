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
import { Pool } from 'pg';
import { getVertexRankingService } from '../vertex-ranking-service';
import { getGeminiRerankingService } from '../gemini-reranking-service';
import { getJobClassificationService, JobClassification } from '../job-classification-service';

const db = admin.firestore();

// PostgreSQL connection for specialty lookups (sourcing schema)
let pgPool: Pool | null = null;

function getPgPool(): Pool {
    if (!pgPool) {
        const host = process.env.PGVECTOR_HOST || 'localhost';
        // Auto-detect SSL: default to true for non-localhost connections (Cloud SQL requires SSL)
        // Can be overridden by PGVECTOR_SSL_MODE=disable for local development
        const isLocalhost = host === 'localhost' || host === '127.0.0.1';
        const sslMode = process.env.PGVECTOR_SSL_MODE === 'disable' ? false : !isLocalhost;

        pgPool = new Pool({
            host,
            port: parseInt(process.env.PGVECTOR_PORT || '5432'),
            database: process.env.PGVECTOR_DATABASE || 'headhunter',
            user: process.env.PGVECTOR_USER || 'postgres',
            password: process.env.PGVECTOR_PASSWORD || '',
            ssl: sslMode,  // Cloud SQL requires SSL
            max: 5,  // Small pool for specialty lookups
            idleTimeoutMillis: 30000,
            connectionTimeoutMillis: 5000,
        });
        console.log(`[LegacyEngine] PostgreSQL pool created, host: ${host}, SSL: ${sslMode}`);
    }
    return pgPool;
}

// Cache for specialty data (TTL 5 minutes)
interface SpecialtyCache {
    data: Map<string, string[]>;
    lastUpdated: number;
}

let specialtyCache: SpecialtyCache = {
    data: new Map(),
    lastUpdated: 0
};

const SPECIALTY_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

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
        // FAIL FAST: If classification fails, we CANNOT deliver quality results
        // Returning bad results (general/mid) destroys user trust
        let targetClassification: JobClassification;
        try {
            targetClassification = await this.classificationService.classifyJob(
                job.title || '',
                job.description
            );
            console.log('[LegacyEngine] Target classification:', targetClassification);
        } catch (error: any) {
            console.error('[LegacyEngine] Job classification failed:', error.message);
            // FAIL FAST: Do NOT use fallback classification
            // Throwing error here returns a clear message to the user
            throw new Error('Search temporarily unavailable. Please try again in a moment.');
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
        let vectorPool: any[] = (vectorSearchResults || []).map((c: any) => ({
            ...c,
            _raw_vector_similarity: c.vector_similarity_score || c.similarity_score || 0
        }));

        if (isExecutiveSearch) {
            // EXECUTIVE MODE: Function-based retrieval is PRIMARY
            // We want CTOs for CTO search, CPOs for CPO search - function matters
            functionPool = await this.searchByFunction(targetClassification.function, levelRange, 300, []);
            console.log(`[LegacyEngine] Executive mode - Function pool: ${functionPool.length}`);
        } else {
            // IC MODE: Vector similarity is PRIMARY + Specialty filtering
            // We want backend engineers for backend roles, not all engineering
            functionPool = await this.searchByFunction(targetClassification.function, levelRange, 100, targetSpecialties);

            // PHASE 2 FIX: Convert level filter to scoring signal
            // Instead of excluding candidates, score them:
            // - In range: 1.0 (best)
            // - Unknown: 0.5 (neutral - let Gemini decide)
            // - Out of range: 0.3 (still included, lower priority)
            vectorPool = vectorPool.map((c: any) => {
                const effectiveLevel = this.getEffectiveLevel(c);
                let levelScore: number;

                if (effectiveLevel === 'unknown') {
                    levelScore = 0.5; // Neutral for unknown
                } else if (levelRange.includes(effectiveLevel)) {
                    levelScore = 1.0; // Full score for in-range
                } else {
                    levelScore = 0.3; // Low score but not excluded
                }

                return { ...c, _level_score: levelScore };
            });
            console.log(`[LegacyEngine] Level scoring applied to ${vectorPool.length} candidates (not filtered)`);

            // Specialty scoring for vector pool - Uses PostgreSQL specialties column
            // PHASE 2 FIX: Convert specialty filter to scoring
            // Instead of excluding, assign scores:
            // - Match: 1.0
            // - Fullstack for backend/frontend: 0.8
            // - No data: 0.5 (neutral)
            // - Clear mismatch: 0.2 (very low but Gemini can evaluate)
            if (targetSpecialties.length > 0 && targetClassification.function === 'engineering') {
                const vectorBeforeSpecialty = vectorPool.length;

                // Load PostgreSQL specialty data for scoring (uses LinkedIn URL matching)
                const pgSpecialties = await this.loadSpecialtiesFromPg(vectorPool);

                vectorPool = vectorPool.map((c: any) => {
                    const candidateId = c.candidate_id || c.id || '';
                    const candidateSpecialties = this.getCandidateSpecialty(c, pgSpecialties);

                    // No specialty data - neutral score
                    if (candidateSpecialties.length === 0) {
                        return { ...c, _specialty_score: 0.5 };
                    }

                    // Check for specialty match
                    for (const target of targetSpecialties) {
                        if (candidateSpecialties.includes(target)) {
                            return { ...c, _specialty_score: 1.0 }; // Direct match
                        }
                        // Fullstack matches both backend and frontend
                        if ((target === 'backend' || target === 'frontend') &&
                            (candidateSpecialties.includes('fullstack') ||
                             candidateSpecialties.includes('full-stack') ||
                             candidateSpecialties.includes('full stack'))) {
                            return { ...c, _specialty_score: 0.8 }; // Good match
                        }
                    }

                    // Mismatch detection (score low but don't exclude)
                    let mismatchScore = 0.4; // Default for unclear cases

                    if (targetSpecialties.includes('backend')) {
                        const isPureFrontend = candidateSpecialties.includes('frontend') &&
                            !candidateSpecialties.includes('backend') &&
                            !candidateSpecialties.includes('fullstack') &&
                            !candidateSpecialties.includes('full-stack');
                        if (isPureFrontend) mismatchScore = 0.2;

                        const wrongSpecialtiesForBackend = ['mobile', 'qa', 'data', 'devops', 'sre'];
                        const hasWrongSpecialty = wrongSpecialtiesForBackend.some(wrong =>
                            candidateSpecialties.includes(wrong) &&
                            !candidateSpecialties.includes('backend') &&
                            !candidateSpecialties.includes('fullstack') &&
                            !candidateSpecialties.includes('full-stack')
                        );
                        if (hasWrongSpecialty) mismatchScore = 0.2;
                    }

                    if (targetSpecialties.includes('frontend')) {
                        const isPureBackend = candidateSpecialties.includes('backend') &&
                            !candidateSpecialties.includes('frontend') &&
                            !candidateSpecialties.includes('fullstack') &&
                            !candidateSpecialties.includes('full-stack');
                        if (isPureBackend) mismatchScore = 0.2;

                        const wrongSpecialtiesForFrontend = ['mobile', 'qa', 'data', 'devops', 'sre'];
                        const hasWrongSpecialtyFE = wrongSpecialtiesForFrontend.some(wrong =>
                            candidateSpecialties.includes(wrong) &&
                            !candidateSpecialties.includes('frontend') &&
                            !candidateSpecialties.includes('fullstack') &&
                            !candidateSpecialties.includes('full-stack')
                        );
                        if (hasWrongSpecialtyFE) mismatchScore = 0.2;
                    }

                    return { ...c, _specialty_score: mismatchScore };
                });

                console.log(`[LegacyEngine] Specialty scoring applied to ${vectorPool.length} candidates (not filtered)`);
            }

            // ===== TECH STACK FILTER =====
            // Filter out candidates with wrong tech stack (e.g., Java developers for Node.js roles)
            // Only if the job specifies required skills
            const requiredSkills = job.required_skills || [];
            if (requiredSkills.length > 0 && targetClassification.function === 'engineering') {
                const beforeTechStack = vectorPool.length;

                // Load skills from PostgreSQL for tech stack filtering
                const pgSkills = await this.loadSkillsFromPg(vectorPool);

                // Define wrong stack indicators - these are backend languages that don't transfer well
                const wrongStackIndicators = ['java', 'c#', 'csharp', '.net', 'scala', 'kotlin', 'spring boot', 'spring framework'];
                // Node.js/TypeScript indicators - the right stack for this search
                const rightStackIndicators = ['node', 'nodejs', 'node.js', 'typescript', 'express', 'nestjs', 'fastify', 'javascript'];

                // Detect if this is a Node.js/TypeScript focused search
                const isNodeSearch = requiredSkills.some(skill =>
                    rightStackIndicators.some(ind => skill.toLowerCase().includes(ind))
                );

                if (isNodeSearch) {
                    vectorPool = vectorPool.filter((c: any) => {
                        const candidateId = c.candidate_id || c.id || '';
                        const candidateSkills = pgSkills.get(candidateId) || [];

                        // No skill data - let Gemini decide
                        if (candidateSkills.length === 0) return true;

                        const candidateSkillsLower = candidateSkills.map((s: string) => s.toLowerCase());

                        // Check if candidate has wrong stack (Java, C#, etc.)
                        const hasWrongStack = wrongStackIndicators.some(ws =>
                            candidateSkillsLower.some((cs: string) => cs.includes(ws))
                        );

                        // Check if candidate has right stack (Node.js, TypeScript, etc.)
                        const hasRightStack = rightStackIndicators.some(rs =>
                            candidateSkillsLower.some((cs: string) => cs.includes(rs))
                        );

                        // Exclude if has wrong stack AND doesn't have right stack
                        // This allows developers who know both Java AND Node.js to pass
                        return !(hasWrongStack && !hasRightStack);
                    });
                    console.log(`[LegacyEngine] Tech stack filter: ${beforeTechStack} → ${vectorPool.length} (required: ${requiredSkills.slice(0, 3).join(', ')})`);
                }
            }

            // ===== FUNCTION MISMATCH EXCLUSION =====
            // Filter out candidates whose current role clearly doesn't match engineering
            // PMs, QAs, Data Scientists should not appear in backend engineer searches
            if (targetClassification.function === 'engineering') {
                const beforeFunctionFilter = vectorPool.length;

                const excludedTitleKeywords = [
                    'product manager', 'product owner', 'pm ',
                    'qa engineer', 'quality assurance', 'test engineer', 'sdet',
                    'data scientist', 'data analyst', 'analytics engineer', 'bi analyst',
                    'ux designer', 'ui designer', 'product designer', 'graphic designer',
                    'project manager', 'delivery manager', 'scrum master', 'agile coach',
                    'technical writer', 'content strategist',
                    'recruiter', 'talent acquisition', 'hr '
                ];

                vectorPool = vectorPool.filter((c: any) => {
                    const title = (
                        c.profile?.current_role ||
                        c.searchable?.title_keywords?.[0] ||
                        c.current_role ||
                        ''
                    ).toLowerCase();

                    // If no title, let Gemini decide
                    if (!title) return true;

                    // Exclude if title contains any of the excluded keywords
                    return !excludedTitleKeywords.some(keyword => title.includes(keyword));
                });

                if (beforeFunctionFilter !== vectorPool.length) {
                    console.log(`[LegacyEngine] Function exclusion filter: ${beforeFunctionFilter} → ${vectorPool.length}`);
                }
            }

            console.log(`[LegacyEngine] IC mode - Function pool: ${functionPool.length}, Vector pool: ${vectorPool.length} (level scored, not filtered)`);
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

        // Load PostgreSQL specialty data for all candidates (for accurate scoring)
        // Uses LinkedIn URL matching since Firestore IDs don't match PostgreSQL IDs
        const allCandidates = [...functionPool, ...vectorPool];
        const allPgSpecialties = await this.loadSpecialtiesFromPg(allCandidates);

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

            // Level match - use pre-computed _level_score from Phase 2 fix if available
            const precomputedLevelScore = candidate._level_score;
            if (precomputedLevelScore !== undefined) {
                entry.levelScore = precomputedLevelScore * weights.level;
            } else {
                const rawLevelScore = this.calculateLevelScore(
                    candidate.searchable?.level || 'mid',
                    targetClassification.level,
                    candidate
                );
                entry.levelScore = (rawLevelScore / 40) * weights.level;
            }

            // Specialty match - use pre-computed _specialty_score from Phase 2 fix if available
            const precomputedSpecialtyScore = candidate._specialty_score;
            if (precomputedSpecialtyScore !== undefined) {
                entry.specialtyScore = precomputedSpecialtyScore * weights.specialty;
            } else {
                const specialtyScore = this.calculateSpecialtyScore(candidate, targetSpecialties, allPgSpecialties);
                entry.specialtyScore = specialtyScore * weights.specialty;
            }

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
                // Use pre-computed _level_score from Phase 2 fix if available
                const precomputedLevelScore = candidate._level_score;
                if (precomputedLevelScore !== undefined) {
                    entry.levelScore = precomputedLevelScore * weights.level;
                } else {
                    const rawLevelScore = this.calculateLevelScore(
                        candidate.searchable?.level || candidate.profile?.current_level || 'mid',
                        targetClassification.level,
                        candidate
                    );
                    entry.levelScore = (rawLevelScore / 40) * weights.level;
                }
            }

            // Specialty score for vector candidates too - use pre-computed _specialty_score if available
            if (entry.specialtyScore === 0) {
                const precomputedSpecialtyScore = candidate._specialty_score;
                if (precomputedSpecialtyScore !== undefined) {
                    entry.specialtyScore = precomputedSpecialtyScore * weights.specialty;
                } else {
                    const specialtyScore = this.calculateSpecialtyScore(candidate, targetSpecialties, allPgSpecialties);
                    entry.specialtyScore = specialtyScore * weights.specialty;
                }
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

        // ===== STEP 3.5: HARD Level Filter (Career Trajectory) =====
        // CRITICAL: Remove candidates who would be STEPPING DOWN to take this role
        // A Principal/Staff engineer will NOT accept a Senior role - that's a demotion
        // This filter uses NOMINAL level (not effective) because we're filtering by candidate interest
        //
        // IMPORTANT: Only apply to candidates with EXPLICIT level data
        // Candidates with unknown level pass through - Gemini will evaluate them
        if (!isExecutiveSearch) {
            const beforeLevelFilter = candidates.length;
            const levelsAboveTarget = this.getLevelsAbove(targetClassification.level);

            candidates = candidates.filter((c: any) => {
                // Try multiple sources for level data
                const nominalLevel = (
                    c.searchable?.level ||
                    c.profile?.current_level ||
                    c.metadata?.current_level ||
                    c.current_level ||
                    ''
                ).toLowerCase();

                // Unknown level passes - Gemini will evaluate them
                if (!nominalLevel || nominalLevel === 'unknown') return true;

                // Keep if candidate's level is NOT above target (they wouldn't be stepping down)
                return !levelsAboveTarget.includes(nominalLevel);
            });

            if (beforeLevelFilter !== candidates.length) {
                console.log(`[LegacyEngine] Hard level filter (career trajectory): ${beforeLevelFilter} → ${candidates.length} (removed ${levelsAboveTarget.join(', ')})`);
            }
        }

        // ===== STEP 4: Cross-Encoder Reranking =====
        let searchStrategy = 'multi-signal retrieval';
        let useVertexRanking = false;

        try {
            if (options?.onProgress) {
                options.onProgress('AI reasoning for best match...');
            }

            // Send more candidates to Gemini for nuanced evaluation
            // The limit here determines how many candidates Gemini can reason about
            const maxForReranking = Math.min(candidates.length, 100);
            const topCandidates = candidates.slice(0, maxForReranking);
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
                title: job.title || `${targetClassification.level} ${targetClassification.function}`,
                // NEW: Pass tech stack for intelligent matching
                requiredSkills: job.required_skills || [],
                avoidSkills: job.sourcing_strategy?.tech_stack?.avoid || [],
                companyContext: this.inferCompanyContext(job.description)
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
                        _raw_vector_similarity: c._raw_vector_similarity || 0,
                        rationale
                    };
                }).sort((a: any, b: any) => b.overall_score - a.overall_score);

                const remainingCandidates = candidates.slice(50).map((c: any) => ({
                    ...c,
                    overall_score: c.retrieval_score || 0,
                    _raw_vector_similarity: c._raw_vector_similarity || 0,
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
                _raw_vector_similarity: c._raw_vector_similarity || 0,
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

        // ===== STEP 6: Minimum Score Threshold =====
        // Lowered from 50 to 30 to let more candidates through to final ranking
        // This allows Gemini reranking to evaluate more candidates before cutting off
        const MIN_SCORE_THRESHOLD = 30;
        const beforeScoreFilter = candidates.length;
        candidates = candidates.filter((c: any) => {
            const score = c.overall_score || 0;
            return score >= MIN_SCORE_THRESHOLD;
        });
        if (beforeScoreFilter !== candidates.length) {
            console.log(`[LegacyEngine] Score threshold filter: ${beforeScoreFilter} → ${candidates.length} (min score: ${MIN_SCORE_THRESHOLD})`);
        }

        // ===== STEP 6.5: Sparse Results Fallback =====
        // If we have too few candidates after filtering, the search was too restrictive
        // Relax constraints and rely more on vector similarity
        const SPARSE_THRESHOLD = 20;
        if (candidates.length < SPARSE_THRESHOLD && vectorSearchResults && vectorSearchResults.length > candidates.length) {
            console.log(`[LegacyEngine] Sparse results detected (${candidates.length}/${SPARSE_THRESHOLD}), adding vector fallback candidates...`);

            // Get candidate IDs we already have
            const existingIds = new Set(candidates.map((c: any) => c.candidate_id || c.id || ''));

            // Add more candidates from vector search results that weren't included
            // These are sorted by vector similarity, so they're semantically relevant
            const fallbackCandidates = vectorSearchResults
                .filter((c: any) => {
                    const id = c.candidate_id || c.id || '';
                    return id && !existingIds.has(id);
                })
                .slice(0, SPARSE_THRESHOLD - candidates.length)
                .map((c: any) => ({
                    ...c,
                    overall_score: 25, // Below threshold but still included as fallback
                    _raw_vector_similarity: c._raw_vector_similarity || c.vector_similarity_score || 0,
                    rationale: ['Vector similarity match (fallback)'],
                    sources: ['vector_fallback'],
                    search_mode: searchMode
                }));

            candidates = [...candidates, ...fallbackCandidates];
            console.log(`[LegacyEngine] Added ${fallbackCandidates.length} fallback candidates, total now: ${candidates.length}`);
        }

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
                vector_score: c._raw_vector_similarity || 0,  // FIXED: Use preserved raw similarity
                raw_vector_similarity: c._raw_vector_similarity || 0,  // Explicit field for frontend
                gemini_score: c.gemini_score || 0,  // Include Gemini score for debugging
                target_function: targetClassification.function,
                target_level: targetClassification.level,
                candidate_function: c.searchable?.function
            }
        }));

        // Log score sample to verify scores differ
        if (matches.length > 0) {
            console.log(`[LegacyEngine] Score sample: overall=${matches[0]?.score || 0}, raw_vector=${matches[0]?.match_metadata?.raw_vector_similarity || 0}, gemini=${matches[0]?.match_metadata?.gemini_score || 0}`);
        }

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

    /**
     * Normalize LinkedIn URL to a comparable format (lowercase slug)
     */
    private normalizeLinkedInUrl(url: string | undefined): string {
        if (!url) return '';
        const lower = url.toLowerCase().trim();
        // Extract the /in/username part
        const match = lower.match(/linkedin\.com\/in\/([^/?#]+)/);
        return match ? match[1] : '';
    }

    /**
     * Load specialty data from PostgreSQL sourcing.candidates table
     * Uses LinkedIn URL matching since Firestore IDs don't match PostgreSQL IDs
     * Uses caching to avoid repeated queries
     */
    private async loadSpecialtiesFromPg(candidates: any[]): Promise<Map<string, string[]>> {
        if (candidates.length === 0) return new Map();

        // Check cache freshness
        const now = Date.now();
        if (now - specialtyCache.lastUpdated > SPECIALTY_CACHE_TTL) {
            // Cache expired, clear it
            specialtyCache.data.clear();
            specialtyCache.lastUpdated = now;
        }

        // Collect uncached candidate IDs
        // The candidate_id/id from vector search matches sourcing.candidates.id directly
        const uncachedIds: number[] = [];

        for (const c of candidates) {
            const candidateId = c.candidate_id || c.id || '';
            if (candidateId && !specialtyCache.data.has(candidateId)) {
                const numId = parseInt(candidateId, 10);
                if (!isNaN(numId)) {
                    uncachedIds.push(numId);
                }
            }
        }

        if (uncachedIds.length > 0) {
            try {
                const pool = getPgPool();
                const client = await pool.connect();

                try {
                    // Debug: Log sample IDs being queried
                    console.log(`[LegacyEngine] Querying specialties for ${uncachedIds.length} candidate IDs, sample: ${uncachedIds.slice(0, 5).join(', ')}`);

                    // Query by candidate ID directly (entity_id in embeddings = id in candidates)
                    const result = await client.query(`
                        SELECT
                            id,
                            COALESCE(specialties, '{}') as specialties
                        FROM sourcing.candidates
                        WHERE id = ANY($1)
                          AND deleted_at IS NULL
                    `, [uncachedIds]);

                    // Debug: Log what we got back
                    console.log(`[LegacyEngine] Found ${result.rows.length} specialty records from PostgreSQL`);
                    if (result.rows.length > 0) {
                        const sampleRow = result.rows[0];
                        console.log(`[LegacyEngine] Sample result: id=${sampleRow.id}, specialties=${JSON.stringify(sampleRow.specialties)}`);
                    }

                    // Update cache using candidate ID as key
                    for (const row of result.rows) {
                        specialtyCache.data.set(String(row.id), row.specialties || []);
                    }

                    // Mark missing entries as empty
                    for (const c of candidates) {
                        const candidateId = c.candidate_id || c.id || '';
                        if (candidateId && !specialtyCache.data.has(candidateId)) {
                            specialtyCache.data.set(candidateId, []);
                        }
                    }
                } finally {
                    client.release();
                }
            } catch (error: any) {
                console.error('[LegacyEngine] Failed to load specialties from PostgreSQL:', error.message);
                // On error, set empty arrays for uncached candidates
                for (const c of candidates) {
                    const candidateId = c.candidate_id || c.id || '';
                    if (candidateId && !specialtyCache.data.has(candidateId)) {
                        specialtyCache.data.set(candidateId, []);
                    }
                }
            }
        }

        // Return requested specialties from cache
        const result = new Map<string, string[]>();
        for (const c of candidates) {
            const candidateId = c.candidate_id || c.id || '';
            result.set(candidateId, specialtyCache.data.get(candidateId) || []);
        }
        return result;
    }

    /**
     * Load skills data from PostgreSQL sourcing.candidates table
     * Uses intelligent_analysis->'skill_assessment'->'technical_skills'->>'core_competencies'
     * Uses LinkedIn URL matching since Firestore IDs don't match PostgreSQL IDs
     */
    private async loadSkillsFromPg(candidates: any[]): Promise<Map<string, string[]>> {
        if (candidates.length === 0) return new Map();

        // Collect candidate IDs (entity_id from embeddings = id in candidates table)
        const candidateIds: number[] = [];

        for (const c of candidates) {
            const candidateId = c.candidate_id || c.id || '';
            if (candidateId) {
                const numId = parseInt(candidateId, 10);
                if (!isNaN(numId)) {
                    candidateIds.push(numId);
                }
            }
        }

        if (candidateIds.length === 0) return new Map();

        const result = new Map<string, string[]>();

        try {
            const pool = getPgPool();
            const client = await pool.connect();

            try {
                // Query skills from intelligent_analysis JSON field by candidate ID
                const queryResult = await client.query(`
                    SELECT
                        id,
                        COALESCE(
                            intelligent_analysis->'skill_assessment'->'technical_skills'->>'core_competencies',
                            '[]'
                        ) as skills_json
                    FROM sourcing.candidates
                    WHERE id = ANY($1)
                      AND deleted_at IS NULL
                      AND intelligent_analysis IS NOT NULL
                `, [candidateIds]);

                // Parse skills and map to candidate IDs
                for (const row of queryResult.rows) {
                    try {
                        // Parse the JSON array of skills
                        const skills = JSON.parse(row.skills_json || '[]');
                        result.set(String(row.id), Array.isArray(skills) ? skills : []);
                    } catch {
                        result.set(String(row.id), []);
                    }
                }

                // Mark candidates without skill data as empty
                for (const c of candidates) {
                    const candidateId = c.candidate_id || c.id || '';
                    if (candidateId && !result.has(candidateId)) {
                        result.set(candidateId, []);
                    }
                }

                console.log(`[LegacyEngine] Loaded skills for ${queryResult.rows.length}/${candidateIds.length} candidates from PostgreSQL`);
            } finally {
                client.release();
            }
        } catch (error: any) {
            console.error('[LegacyEngine] Failed to load skills from PostgreSQL:', error.message);
            // On error, return empty map
            for (const c of candidates) {
                const candidateId = c.candidate_id || c.id || '';
                if (candidateId && !result.has(candidateId)) {
                    result.set(candidateId, []);
                }
            }
        }

        return result;
    }

    /**
     * Get candidate specialty from PostgreSQL (with fallback to Firestore data)
     */
    private getCandidateSpecialty(candidate: any, pgSpecialties: Map<string, string[]>): string[] {
        const candidateId = candidate.candidate_id || candidate.id || '';

        // Priority 1: PostgreSQL specialties (most accurate, from backfill)
        const pgSpecs = pgSpecialties.get(candidateId);
        if (pgSpecs && pgSpecs.length > 0) {
            return pgSpecs;
        }

        // Priority 2: Firestore searchable.functions.engineering.specialties (legacy)
        const functions = candidate.searchable?.functions || [];
        const engFunction = functions.find((f: any) => f.name === 'engineering');
        if (engFunction?.specialties && engFunction.specialties.length > 0) {
            return engFunction.specialties;
        }

        // No specialty data available
        return [];
    }

    private async searchByFunction(
        targetFunction: string,
        levelRange: string[],
        limit: number,
        targetSpecialties: string[] = []
    ): Promise<any[]> {
        try {
            const fetchLimit = Math.min(limit * 3, 500);

            // Query 1: Legacy single-function field (backward compatibility)
            const legacyQuery = db.collection('candidates')
                .where('searchable.function', '==', targetFunction)
                .limit(fetchLimit);

            const legacySnapshot = await legacyQuery.get();

            // PHASE 2 FIX: Score by EFFECTIVE level instead of filtering
            // This allows startup execs to appear in higher-tier role searches
            // All candidates pass through with _level_score attached
            let candidates = legacySnapshot.docs
                .map(doc => ({ id: doc.id, ...doc.data() } as any))
                .map((c: any) => {
                    // PHASE 2 FIX: Score instead of filter
                    const effectiveLevel = this.getEffectiveLevel(c);
                    let levelScore: number;

                    if (effectiveLevel === 'unknown') {
                        levelScore = 0.5;
                    } else if (levelRange.includes(effectiveLevel)) {
                        levelScore = 1.0;
                    } else {
                        levelScore = 0.3;
                    }

                    return { ...c, _level_score: levelScore };
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

            // ===================================================================
            // SPECIALTY SCORING (for IC roles) - Uses PostgreSQL as primary source
            // PHASE 2 FIX: Score instead of filter (same logic as vector pool)
            // - Match: 1.0
            // - Fullstack for backend/frontend: 0.8
            // - No data: 0.5 (neutral)
            // - Clear mismatch: 0.2 (very low but Gemini can evaluate)
            // ===================================================================
            if (targetSpecialties.length > 0 && targetFunction === 'engineering') {
                const beforeFilter = candidates.length;

                // Load PostgreSQL specialty data for function pool candidates (uses LinkedIn URL matching)
                const pgSpecialties = await this.loadSpecialtiesFromPg(candidates);

                candidates = candidates.map((c: any) => {
                    const candidateId = c.id || '';
                    const candidateSpecialties = this.getCandidateSpecialty(c, pgSpecialties);

                    // No specialty data - neutral score
                    if (candidateSpecialties.length === 0) {
                        return { ...c, _specialty_score: 0.5 };
                    }

                    // Check for specialty match
                    for (const target of targetSpecialties) {
                        if (candidateSpecialties.includes(target)) {
                            return { ...c, _specialty_score: 1.0 };
                        }

                        // Fullstack matches both frontend and backend
                        if ((target === 'backend' || target === 'frontend') &&
                            (candidateSpecialties.includes('fullstack') ||
                             candidateSpecialties.includes('full-stack') ||
                             candidateSpecialties.includes('full stack'))) {
                            return { ...c, _specialty_score: 0.8 };
                        }
                    }

                    // Mismatch scoring
                    let mismatchScore = 0.4;
                    if (targetSpecialties.includes('backend')) {
                        const isPureFrontend = candidateSpecialties.includes('frontend') &&
                            !candidateSpecialties.includes('backend') &&
                            !candidateSpecialties.includes('fullstack') &&
                            !candidateSpecialties.includes('full-stack');
                        if (isPureFrontend) mismatchScore = 0.2;

                        const wrongForBackend = ['mobile', 'qa', 'data', 'devops', 'sre'];
                        if (wrongForBackend.some(w => candidateSpecialties.includes(w) &&
                            !candidateSpecialties.includes('backend') &&
                            !candidateSpecialties.includes('fullstack'))) {
                            mismatchScore = 0.2;
                        }
                    }
                    if (targetSpecialties.includes('frontend')) {
                        const isPureBackend = candidateSpecialties.includes('backend') &&
                            !candidateSpecialties.includes('frontend') &&
                            !candidateSpecialties.includes('fullstack') &&
                            !candidateSpecialties.includes('full-stack');
                        if (isPureBackend) mismatchScore = 0.2;

                        const wrongForFrontend = ['mobile', 'qa', 'data', 'devops', 'sre'];
                        if (wrongForFrontend.some(w => candidateSpecialties.includes(w) &&
                            !candidateSpecialties.includes('frontend') &&
                            !candidateSpecialties.includes('fullstack'))) {
                            mismatchScore = 0.2;
                        }
                    }

                    return { ...c, _specialty_score: mismatchScore };
                });

                console.log(`[LegacyEngine] Function pool specialty scoring: ${beforeFilter} candidates scored (specialties: ${targetSpecialties.join(', ')})`);
            }

            console.log(`[LegacyEngine] Function query: ${legacySnapshot.size} total, ${candidates.length} scored (level range: ${levelRange.join(', ')}) for ${targetFunction}`);
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

        // For IC roles (senior, mid, junior, staff, principal)
        // KEY INSIGHT: Show candidates who would STEP UP into the role
        // Senior engineers won't take mid-level roles - they'd be stepping DOWN
        // But mid-level engineers would gladly take senior roles - stepping UP
        //
        // IMPORTANT: IC track is SEPARATE from management track
        // Manager, Director, VP, C-level are NOT included in IC searches
        const icLevelOrder = ['intern', 'junior', 'mid', 'senior', 'staff', 'principal'];
        const targetIndex = icLevelOrder.indexOf(targetLevel);

        if (targetIndex === -1) return icLevelOrder;

        // Show target level + one level BELOW (candidates stepping UP)
        // Don't show levels ABOVE - they won't be interested
        const minIndex = Math.max(0, targetIndex - 1);  // One level below can step up
        const maxIndex = targetIndex;  // Exact match, not above

        return icLevelOrder.slice(minIndex, maxIndex + 1);
    }

    /**
     * Get levels ABOVE the target level (candidates who would be stepping DOWN)
     * Used for hard filtering to remove candidates who won't be interested
     *
     * Recruiter logic: A Principal engineer won't accept a Senior role - that's a demotion
     * Even if they're "technically qualified", they won't take it
     */
    private getLevelsAbove(targetLevel: string): string[] {
        // IC track: intern → junior → mid → senior → staff → principal
        // Management track: manager → director → vp → c-level
        // Cross-track: Management levels are always "above" IC levels for interest purposes

        const icLevelOrder = ['intern', 'junior', 'mid', 'senior', 'staff', 'principal'];
        const managementLevels = ['manager', 'director', 'vp', 'c-level'];

        const targetIndex = icLevelOrder.indexOf(targetLevel);

        if (targetIndex === -1) {
            // Target is on management track - return higher management levels
            const mgmtIndex = managementLevels.indexOf(targetLevel);
            if (mgmtIndex === -1) return [];
            return managementLevels.slice(mgmtIndex + 1);
        }

        // Target is on IC track
        // Levels above = higher IC levels + all management levels (manager won't take senior IC role)
        const higherIcLevels = icLevelOrder.slice(targetIndex + 1);
        return [...higherIcLevels, ...managementLevels];
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
     *
     * IMPORTANT: Management track (manager, director, vp, c-level) is SEPARATE from IC track.
     * We never adjust managers down to IC levels - they are different career paths.
     *
     * CRITICAL FIX: Only apply company tier adjustment when we have ACTUAL data.
     * Don't penalize candidates with missing metadata by demoting them to 'intern'.
     */
    private getEffectiveLevel(candidate: any): string {
        // Check multiple possible sources for level data
        const nominalLevel = (
            candidate.searchable?.level ||
            candidate.profile?.current_level ||
            candidate.metadata?.current_level ||
            candidate.current_level ||
            'unknown'
        ).toLowerCase();

        // If we don't know the level, return it as-is (will be filtered leniently)
        // This prevents demoting unknown candidates to 'intern'
        if (nominalLevel === 'unknown') {
            return 'unknown';
        }

        // IC levels vs Management levels - these are DIFFERENT TRACKS
        const icLevels = ['intern', 'junior', 'mid', 'senior', 'staff', 'principal'];
        const managementLevels = ['manager', 'director', 'vp', 'c-level'];

        // If candidate is on management track, their level is fixed - no adjustment
        // A Manager is always a Manager, regardless of company tier
        // This prevents managers from appearing in IC (senior engineer) searches
        if (managementLevels.includes(nominalLevel)) {
            return nominalLevel;
        }

        // For IC levels, only apply company tier adjustment if we have BOTH:
        // 1. Explicit level data (not defaulted)
        // 2. Company data to determine tier
        const hasExplicitLevel = Boolean(
            candidate.searchable?.level ||
            candidate.profile?.current_level ||
            candidate.metadata?.current_level
        );
        const hasCompanyData = Boolean(
            (candidate.searchable?.companies && candidate.searchable.companies.length > 0) ||
            (candidate.profile?.companies && candidate.profile.companies.length > 0)
        );

        // If we don't have reliable data, return the nominal level without adjustment
        if (!hasExplicitLevel || !hasCompanyData) {
            return nominalLevel;
        }

        const companyTier = this.getCompanyTier(candidate);
        const levelOrder = ['intern', 'junior', 'mid', 'senior', 'staff', 'principal'];
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
     *
     * Detection strategy:
     * 1. EXPLICIT title detection - if specialty is in job title, that's a clear signal
     *    (e.g., "Senior Backend Engineer" → backend)
     * 2. If no explicit title match, fall back to description keyword analysis (2+ threshold)
     */
    private detectSpecialties(jobDescription: string, jobTitle: string): string[] {
        const text = `${jobTitle} ${jobDescription}`.toLowerCase();
        const titleLower = jobTitle.toLowerCase();
        const specialties: string[] = [];

        // PHASE 1: Explicit title detection (recruiter standard: job title = job family)
        // "Senior Backend Engineer" → backend
        // "Frontend Developer" → frontend
        if (titleLower.includes('backend') || titleLower.includes('back-end')) {
            specialties.push('backend');
        }
        if (titleLower.includes('frontend') || titleLower.includes('front-end') || titleLower.includes('front end')) {
            specialties.push('frontend');
        }
        if (titleLower.includes('fullstack') || titleLower.includes('full-stack') || titleLower.includes('full stack')) {
            specialties.push('fullstack');
        }
        if (titleLower.includes('mobile') || titleLower.includes('ios developer') || titleLower.includes('android developer')) {
            specialties.push('mobile');
        }
        if (titleLower.includes('devops') || titleLower.includes('sre') || titleLower.includes('platform engineer')) {
            specialties.push('devops');
        }
        if (titleLower.includes('data engineer') || titleLower.includes('ml engineer') || titleLower.includes('machine learning')) {
            specialties.push('data');
        }

        // PHASE 2: If no explicit title match, fall back to description keyword analysis (2+ threshold)
        if (specialties.length === 0) {
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
        }

        console.log(`[LegacyEngine] Detected specialties: ${specialties.join(', ') || 'none'}`);
        return specialties;
    }

    /**
     * Calculate specialty match score
     * Returns 0-1 based on how well candidate's specialties match job requirements
     * Now uses PostgreSQL specialties as primary source (more accurate from backfill)
     */
    private calculateSpecialtyScore(
        candidate: any,
        targetSpecialties: string[],
        pgSpecialties?: Map<string, string[]>
    ): number {
        if (!targetSpecialties.length) return 1.0; // No specific specialty needed

        // Get candidate specialties (PostgreSQL first, then Firestore fallback)
        const candidateId = candidate.id || candidate.candidate_id || '';
        const candidateSpecialties = pgSpecialties
            ? this.getCandidateSpecialty(candidate, pgSpecialties)
            : this.getCandidateSpecialtyFromFirestore(candidate);

        // No specialty data - neutral score
        if (candidateSpecialties.length === 0) return 0.5;

        let maxScore = 0;

        for (const targetSpec of targetSpecialties) {
            // Direct match - full score
            if (candidateSpecialties.includes(targetSpec)) {
                maxScore = Math.max(maxScore, 1.0);
            }

            // Fullstack matches both frontend and backend (slightly lower score)
            if ((targetSpec === 'backend' || targetSpec === 'frontend') &&
                (candidateSpecialties.includes('fullstack') ||
                 candidateSpecialties.includes('full-stack') ||
                 candidateSpecialties.includes('full stack'))) {
                maxScore = Math.max(maxScore, 0.8);
            }

            // Related specialties (e.g., devops is somewhat related to backend)
            if (targetSpec === 'backend' && candidateSpecialties.includes('devops')) {
                maxScore = Math.max(maxScore, 0.4);
            }
        }

        return maxScore;
    }

    /**
     * Get specialty from Firestore data (legacy fallback)
     */
    private getCandidateSpecialtyFromFirestore(candidate: any): string[] {
        const functions = candidate.searchable?.functions || [];
        const engFunction = functions.find((f: any) => f.name === 'engineering');
        if (engFunction?.specialties && engFunction.specialties.length > 0) {
            return engFunction.specialties;
        }
        return [];
    }

    /**
     * Infer company context from job description
     * Helps Gemini understand what type of company this is (startup, enterprise, etc.)
     */
    private inferCompanyContext(description: string): string {
        const text = description.toLowerCase();
        const contexts: string[] = [];

        // Company stage indicators
        if (text.includes('early-stage') || text.includes('early stage') || text.includes('seed') ||
            text.includes('series a') || text.includes('series b')) {
            contexts.push('early-stage startup');
        } else if (text.includes('growth stage') || text.includes('series c') || text.includes('series d') ||
                   text.includes('scale') || text.includes('hypergrowth')) {
            contexts.push('growth-stage company');
        } else if (text.includes('enterprise') || text.includes('fortune 500') || text.includes('global')) {
            contexts.push('enterprise company');
        }

        // Industry context
        if (text.includes('fintech') || text.includes('financial') || text.includes('banking') ||
            text.includes('payments') || text.includes('crypto')) {
            contexts.push('fintech');
        }
        if (text.includes('healthtech') || text.includes('healthcare') || text.includes('medical')) {
            contexts.push('healthtech');
        }
        if (text.includes('saas') || text.includes('b2b')) {
            contexts.push('B2B SaaS');
        }
        if (text.includes('ecommerce') || text.includes('e-commerce') || text.includes('marketplace')) {
            contexts.push('e-commerce');
        }

        // Team size context
        if (text.includes('small team') || text.includes('founding') || text.includes('first hire')) {
            contexts.push('small team');
        }

        return contexts.length > 0 ? contexts.join(', ') : '';
    }
}
