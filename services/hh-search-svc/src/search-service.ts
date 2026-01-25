import { badRequestError, getFirestore, getLogger } from '@hh/common';
import type { Firestore } from '@google-cloud/firestore';
import { createHash } from 'crypto';
import type { Logger } from 'pino';

import type { SearchServiceConfig } from './config';
import type { EmbedClient } from './embed-client';
import type {
  FirestoreCandidateRecord,
  HybridSearchRequest,
  HybridSearchResponse,
  HybridSearchResultItem,
  PgHybridSearchRow,
  SearchContext,
  SignalScores
} from './types';
import type { PgVectorClient } from './pgvector-client';
import type { SearchRedisClient } from './redis-client';
import type { RerankClient, RerankCandidate, RerankRequest, RerankResponse, MatchRationale } from './rerank-client';
import type { PerformanceTracker } from './performance-tracker';
import { resolveWeights, type SignalWeightConfig, type RoleType } from './signal-weights';
import { computeWeightedScore, extractSignalScores, normalizeVectorScore, completeSignalScores, type SignalComputationContext } from './scoring';

interface HybridSearchDependencies {
  config: SearchServiceConfig;
  pgClient: PgVectorClient;
  embedClient: EmbedClient;
  redisClient?: SearchRedisClient;
  rerankClient?: RerankClient;
  performanceTracker: PerformanceTracker;
  logger?: Logger;
}

function computeSkillMatches(
  candidateSkills: string[] | undefined | null,
  requested: string[] | undefined
): {
  matches: string[];
  normalizedMatches: Set<string>;
  coverage: number;
} {
  if (!candidateSkills || candidateSkills.length === 0 || !requested || requested.length === 0) {
    return { matches: [], normalizedMatches: new Set<string>(), coverage: 0 };
  }

  const candidateSet = new Set(candidateSkills.map((skill) => skill.trim().toLowerCase()).filter(Boolean));
  const requestedSet = requested.map((skill) => skill.trim().toLowerCase()).filter(Boolean);

  const matches = requestedSet.filter((skill) => candidateSet.has(skill));
  const coverage = matches.length === 0 ? 0 : matches.length / requestedSet.length;

  return {
    matches: matches.map((skill) => skill.replace(/\b\w/g, (s) => s.toUpperCase())),
    normalizedMatches: new Set(matches),
    coverage
  };
}

// Country indicators for auto-extraction from job descriptions
const BRAZIL_INDICATORS = [
  'são paulo', 'sao paulo', 'rio de janeiro', 'brasil', 'brazil',
  'belo horizonte', 'curitiba', 'porto alegre', 'brasília', 'brasilia',
  'recife', 'salvador', 'fortaleza', 'campinas', 'manaus'
];

const US_INDICATORS = [
  'united states', 'usa', 'u.s.', 'us only', 'new york', 'san francisco',
  'los angeles', 'seattle', 'boston', 'chicago', 'austin', 'remote us'
];

function extractCountryFromJobDescription(jobDescription: string | undefined): string | null {
  if (!jobDescription) return null;

  const text = jobDescription.toLowerCase();

  // Check for explicit location requirements
  const locationPatterns = [
    /based in\s+([^,.\n]+)/i,
    /located in\s+([^,.\n]+)/i,
    /position in\s+([^,.\n]+)/i,
    /role in\s+([^,.\n]+)/i,
    /office in\s+([^,.\n]+)/i,
    /location:\s*([^,.\n]+)/i
  ];

  for (const pattern of locationPatterns) {
    const match = text.match(pattern);
    if (match) {
      const location = match[1].toLowerCase().trim();
      // Check if extracted location is a Brazil indicator
      for (const indicator of BRAZIL_INDICATORS) {
        if (location.includes(indicator)) {
          return 'Brazil';
        }
      }
      // Check if extracted location is a US indicator
      for (const indicator of US_INDICATORS) {
        if (location.includes(indicator)) {
          return 'United States';
        }
      }
    }
  }

  // Check for Brazil indicators anywhere in text
  for (const indicator of BRAZIL_INDICATORS) {
    if (text.includes(indicator)) {
      return 'Brazil';
    }
  }

  // Check for US indicators anywhere in text
  for (const indicator of US_INDICATORS) {
    if (text.includes(indicator)) {
      return 'United States';
    }
  }

  return null;
}

export class SearchService {
  private readonly config: SearchServiceConfig;
  private readonly pgClient: PgVectorClient;
  private readonly embedClient: EmbedClient;
  private readonly redisClient: SearchRedisClient | null;
  private readonly rerankClient: RerankClient | null;
  private readonly performanceTracker: PerformanceTracker;
  private readonly logger: Logger;
  private firestore: Firestore | null = null;

  constructor(deps: HybridSearchDependencies) {
    this.config = deps.config;
    this.pgClient = deps.pgClient;
    this.embedClient = deps.embedClient;
    this.redisClient = deps.redisClient ?? null;
    this.rerankClient = deps.rerankClient ?? null;
    this.performanceTracker = deps.performanceTracker;
    this.logger = (deps.logger ?? getLogger({ module: 'search-service' })).child({ module: 'search-service' });
  }

  setFirestore(client: Firestore): void {
    this.firestore = client;
  }

  computeCacheToken(request: HybridSearchRequest): string {
    if (request.jdHash && request.jdHash.trim().length > 0) {
      return request.jdHash.trim();
    }

    const hash = createHash('sha1');
    hash.update(request.query ?? '');
    hash.update(JSON.stringify(request.filters ?? {}));
    hash.update(String(request.limit ?? ''));
    hash.update(request.jobDescription ?? '');
    return hash.digest('hex');
  }

  private computeEmbeddingCacheToken(request: HybridSearchRequest): string | null {
    if (request.jdHash && request.jdHash.trim().length > 0) {
      return request.jdHash.trim();
    }

    const baseText = (request.jobDescription ?? request.query ?? '').trim();
    if (baseText.length === 0) {
      return null;
    }

    const hash = createHash('sha1');
    hash.update(baseText);
    return hash.digest('hex');
  }

  async hybridSearch(context: SearchContext, request: HybridSearchRequest): Promise<HybridSearchResponse> {
    const totalStart = Date.now();
    this.logger.info({ requestId: context.requestId, tenantId: context.tenant.id }, 'Hybrid search received request.');

    if (
      !request.query &&
      !request.jobDescription &&
      (!request.embedding || request.embedding.length === 0)
    ) {
      throw badRequestError('Either query text, job description, or pre-computed embedding is required.');
    }

    const limit = Math.min(Math.max(1, request.limit ?? 20), this.config.search.maxResults);
    const offset = Math.max(0, request.offset ?? 0);
    const sanitizedQuery = (request.query ?? '').trim();
    const timings: HybridSearchResponse['timings'] = {
      totalMs: 0
    };

    // Pipeline metrics tracking (PIPE-01)
    const pipelineMetrics = {
      retrievalCount: 0,
      retrievalMs: 0,
      scoringCount: 0,
      scoringMs: 0,
      rerankCount: 0,
      rerankMs: 0,
      rerankApplied: false,
      totalMs: 0
    };

    // Resolve signal weights from request or role-type defaults
    const roleType: RoleType = request.roleType ?? 'default';
    const resolvedWeights = resolveWeights(request.signalWeights, roleType);

    this.logger.info(
      { requestId: context.requestId, roleType, weightsApplied: resolvedWeights },
      'Signal weights resolved for search.'
    );

    // Auto-extract country from job description if not explicitly provided
    const detectedCountry = extractCountryFromJobDescription(request.jobDescription);
    if (detectedCountry && (!request.filters?.countries || request.filters.countries.length === 0)) {
      request = {
        ...request,
        filters: {
          ...request.filters,
          countries: [detectedCountry]
        }
      };
      this.logger.info({ requestId: context.requestId, detectedCountry }, 'Auto-detected country from job description.');
    }

    let embedding = request.embedding;
    let embeddingCacheKey: string | null = null;
    const embeddingCacheToken = this.computeEmbeddingCacheToken(request);

    if ((!embedding || embedding.length === 0) && this.redisClient && !this.redisClient.isDisabled() && embeddingCacheToken) {
      embeddingCacheKey = this.redisClient.buildEmbeddingKey(context.tenant.id, embeddingCacheToken);
      const cachedEmbedding = await this.redisClient.get<number[]>(embeddingCacheKey);
      if (Array.isArray(cachedEmbedding) && cachedEmbedding.length > 0) {
        embedding = cachedEmbedding;
      }
    }

    if (!embedding || embedding.length === 0) {
      const embeddingStart = Date.now();
      const embeddingText = sanitizedQuery || request.jobDescription || request.query || ' ';
      const result = await this.embedClient.generateEmbedding({
        tenantId: context.tenant.id,
        requestId: context.requestId,
        query: embeddingText,
        metadata: {
          source: 'hh-search-svc',
          requestId: context.requestId
        }
      });
      timings.embeddingMs = Date.now() - embeddingStart;
      embedding = result.embedding;

      if (embeddingCacheKey && this.redisClient && !this.redisClient.isDisabled() && Array.isArray(embedding) && embedding.length > 0) {
        await this.redisClient.set(embeddingCacheKey, embedding);
      }
    }

    // === STAGE 1: RETRIEVAL (recall-focused) ===
    const retrievalStart = Date.now();
    const rows = await this.pgClient.hybridSearch({
      tenantId: context.tenant.id,
      embedding,
      textQuery: sanitizedQuery,
      limit,
      offset,
      minSimilarity: this.config.search.minSimilarity,
      vectorWeight: this.config.search.vectorWeight,
      textWeight: this.config.search.textWeight,
      filters: request.filters,
      warmupMultiplier: this.config.search.warmupMultiplier,
      // RRF configuration
      rrfK: this.config.search.rrfK,
      perMethodLimit: this.config.search.perMethodLimit,
      enableRrf: this.config.search.enableRrf
    });
    const retrievalMs = Date.now() - retrievalStart;
    timings.retrievalMs = retrievalMs;

    // Update pipeline metrics for Stage 1
    pipelineMetrics.retrievalCount = rows.length;
    pipelineMetrics.retrievalMs = retrievalMs;

    // Stage 1 logging
    if (this.config.search.pipelineLogStages) {
      this.logger.info({
        stage: 'STAGE 1: RETRIEVAL',
        requestId: context.requestId,
        count: rows.length,
        target: this.config.search.pipelineRetrievalLimit,
        latencyMs: retrievalMs
      }, 'Pipeline Stage 1 complete - retrieval focused on recall');
    }

    let candidates = rows.map((row) => this.hydrateResult(row, request, resolvedWeights, roleType));

    if (candidates.length === 0 && this.config.firestoreFallback.enabled) {
      const fallbackStart = Date.now();
      const fallback = await this.fetchFromFirestore(context.tenant.id, limit);
      timings.retrievalMs = (timings.retrievalMs ?? 0) + (Date.now() - fallbackStart);
      candidates = fallback.map((record) => ({
        candidateId: record.candidate_id,
        score: 0.2,
        vectorScore: 0,
        textScore: 0,
        confidence: record.analysis_confidence ?? 0,
        fullName: record.full_name,
        title: record.current_title,
        headline: record.headline,
        location: record.location,
        industries: record.industries,
        yearsExperience: record.years_experience,
        skills:
          record.skills?.map((skill) => ({
            name: skill,
            weight: 0.1
          })) ?? [],
        matchReasons: ['Fetched via Firestore fallback'],
        metadata: record.metadata,
        // Signal scoring fields with neutral defaults (0.5) for fallback
        signalScores: completeSignalScores({}, 0.5),
        weightsApplied: resolvedWeights,
        roleTypeUsed: roleType
      } satisfies HybridSearchResultItem));
    }

    // === STAGE 2: SCORING (precision-focused) ===
    const scoringStart = Date.now();
    const rankingStart = Date.now();
    let ranked = this.rankCandidates(candidates, request);
    const rankingMs = Date.now() - rankingStart;
    timings.rankingMs = rankingMs;

    // Apply scoring stage cutoff - keep only top N for reranking
    const preScoringCount = ranked.length;
    const scoringLimit = this.config.search.pipelineScoringLimit;
    ranked = ranked.slice(0, scoringLimit);
    const scoringMs = Date.now() - scoringStart;

    // Update pipeline metrics for Stage 2
    pipelineMetrics.scoringCount = ranked.length;
    pipelineMetrics.scoringMs = scoringMs;

    // Stage 2 logging
    if (this.config.search.pipelineLogStages) {
      this.logger.info({
        stage: 'STAGE 2: SCORING',
        requestId: context.requestId,
        inputCount: preScoringCount,
        outputCount: ranked.length,
        cutoff: scoringLimit,
        latencyMs: scoringMs
      }, 'Pipeline Stage 2 complete - scoring focused on precision');
    }

    // Log Phase 7 signal statistics for debugging
    if (ranked.length > 0) {
      const phase7Stats = {
        avgSkillsExact: 0,
        avgSkillsInferred: 0,
        avgSeniority: 0,
        avgRecency: 0,
        avgCompanyRelevance: 0,
        candidatesWithPhase7: 0
      };

      for (const r of ranked.slice(0, 20)) { // Sample top 20
        if (r.signalScores?.skillsExactMatch !== undefined) {
          phase7Stats.avgSkillsExact += r.signalScores.skillsExactMatch;
          phase7Stats.avgSkillsInferred += r.signalScores.skillsInferred ?? 0;
          phase7Stats.avgSeniority += r.signalScores.seniorityAlignment ?? 0;
          phase7Stats.avgRecency += r.signalScores.recencyBoost ?? 0;
          phase7Stats.avgCompanyRelevance += r.signalScores.companyRelevance ?? 0;
          phase7Stats.candidatesWithPhase7++;
        }
      }

      if (phase7Stats.candidatesWithPhase7 > 0) {
        const n = phase7Stats.candidatesWithPhase7;
        this.logger.info(
          {
            requestId: context.requestId,
            phase7Signals: {
              sampleSize: n,
              avgSkillsExact: (phase7Stats.avgSkillsExact / n).toFixed(3),
              avgSkillsInferred: (phase7Stats.avgSkillsInferred / n).toFixed(3),
              avgSeniority: (phase7Stats.avgSeniority / n).toFixed(3),
              avgRecency: (phase7Stats.avgRecency / n).toFixed(3),
              avgCompanyRelevance: (phase7Stats.avgCompanyRelevance / n).toFixed(3)
            }
          },
          'Phase 7 signal statistics computed.'
        );
      }
    }

    // === STAGE 3: RERANKING (nuance via LLM) ===
    const rerankStart = Date.now();
    const rerankOutcome = await this.applyRerankIfEnabled(context, request, ranked, scoringLimit);

    if (rerankOutcome) {
      ranked = rerankOutcome.results;
      if (rerankOutcome.timingsMs !== undefined) {
        timings.rerankMs = rerankOutcome.timingsMs;
      }
    }

    // Apply final rerank cutoff
    const preRerankCount = ranked.length;
    const rerankLimit = this.config.search.pipelineRerankLimit;
    ranked = ranked.slice(0, rerankLimit);
    const rerankMs = Date.now() - rerankStart;

    // Update pipeline metrics for Stage 3
    pipelineMetrics.rerankCount = ranked.length;
    pipelineMetrics.rerankMs = rerankMs;
    pipelineMetrics.rerankApplied = Boolean(rerankOutcome && !rerankOutcome.metadata?.usedFallback);

    // Stage 3 logging
    if (this.config.search.pipelineLogStages) {
      this.logger.info({
        stage: 'STAGE 3: RERANKING',
        requestId: context.requestId,
        inputCount: preRerankCount,
        outputCount: ranked.length,
        cutoff: rerankLimit,
        rerankApplied: Boolean(rerankOutcome && !rerankOutcome.metadata?.usedFallback),
        llmProvider: rerankOutcome?.metadata?.llmProvider ?? 'none',
        latencyMs: rerankMs
      }, 'Pipeline Stage 3 complete - LLM reranking for nuance');
    }

    // Generate match rationales for top candidates if requested (TRNS-03)
    if (request.includeMatchRationale && ranked.length > 0) {
      ranked = await this.addMatchRationales(
        context,
        request,
        ranked
      );
    }

    // Update total pipeline time
    pipelineMetrics.totalMs = Date.now() - totalStart;

    const response: HybridSearchResponse = {
      results: ranked.slice(0, limit),
      total: ranked.length,
      cacheHit: false,
      requestId: context.requestId,
      timings,
      metadata: {
        vectorWeight: this.config.search.vectorWeight,
        textWeight: this.config.search.textWeight,
        minSimilarity: this.config.search.minSimilarity,
        // Signal scoring configuration
        signalWeights: {
          roleType,
          weightsApplied: resolvedWeights
        }
      },
      // Pipeline stage metrics (PIPE-01)
      pipelineMetrics: {
        retrievalCount: pipelineMetrics.retrievalCount,
        retrievalMs: pipelineMetrics.retrievalMs,
        scoringCount: pipelineMetrics.scoringCount,
        scoringMs: pipelineMetrics.scoringMs,
        rerankCount: pipelineMetrics.rerankCount,
        rerankMs: pipelineMetrics.rerankMs,
        rerankApplied: pipelineMetrics.rerankApplied,
        totalMs: pipelineMetrics.totalMs
      }
    };

    if (rerankOutcome?.metadata) {
      response.metadata = {
        ...response.metadata,
        rerank: rerankOutcome.metadata
      } satisfies Record<string, unknown>;
    }

    if (request.includeDebug) {
      response.debug = {
        candidateCount: ranked.length,
        filtersApplied: request.filters ?? {},
        minSimilarity: this.config.search.minSimilarity,
        // RRF configuration
        rrfConfig: {
          enabled: this.config.search.enableRrf,
          k: this.config.search.rrfK,
          perMethodLimit: this.config.search.perMethodLimit
        },
        // Signal scoring configuration
        signalScoringConfig: {
          roleType,
          weightsApplied: resolvedWeights,
          requestOverrides: request.signalWeights ?? null
        },
        // Enhanced score breakdown with signal scores
        scoreBreakdown: ranked.slice(0, 5).map(r => ({
          candidateId: r.candidateId,
          score: r.score,
          vectorScore: r.vectorScore,
          textScore: r.textScore,
          rrfScore: r.rrfScore,
          vectorRank: r.vectorRank,
          textRank: r.textRank,
          // Individual signal scores
          signalScores: r.signalScores
        })),
        // Phase 7 signal breakdown
        phase7Breakdown: ranked.slice(0, 5).map(r => ({
          candidateId: r.candidateId,
          skillsExactMatch: r.signalScores?.skillsExactMatch,
          skillsInferred: r.signalScores?.skillsInferred,
          seniorityAlignment: r.signalScores?.seniorityAlignment,
          recencyBoost: r.signalScores?.recencyBoost,
          companyRelevance: r.signalScores?.companyRelevance
        })),
        // Pipeline stage breakdown
        pipelineBreakdown: {
          stage1_retrieval: {
            count: pipelineMetrics.retrievalCount,
            target: this.config.search.pipelineRetrievalLimit,
            latencyMs: pipelineMetrics.retrievalMs
          },
          stage2_scoring: {
            inputCount: pipelineMetrics.retrievalCount,
            outputCount: pipelineMetrics.scoringCount,
            cutoff: this.config.search.pipelineScoringLimit,
            latencyMs: pipelineMetrics.scoringMs
          },
          stage3_rerank: {
            inputCount: pipelineMetrics.scoringCount,
            outputCount: pipelineMetrics.rerankCount,
            cutoff: this.config.search.pipelineRerankLimit,
            rerankApplied: pipelineMetrics.rerankApplied,
            latencyMs: pipelineMetrics.rerankMs
          }
        }
      };
    }

    timings.totalMs = Date.now() - totalStart;

    // Pipeline summary log (PIPE-01)
    this.logger.info(
      {
        requestId: context.requestId,
        tenantId: context.tenant.id,
        pipeline: {
          retrieval: pipelineMetrics.retrievalCount,
          afterScoring: pipelineMetrics.scoringCount,
          final: pipelineMetrics.rerankCount,
          rerankApplied: pipelineMetrics.rerankApplied
        },
        latency: {
          retrievalMs: pipelineMetrics.retrievalMs,
          scoringMs: pipelineMetrics.scoringMs,
          rerankMs: pipelineMetrics.rerankMs,
          totalMs: pipelineMetrics.totalMs
        },
        targets: {
          retrieval: this.config.search.pipelineRetrievalLimit,
          scoring: this.config.search.pipelineScoringLimit,
          rerank: this.config.search.pipelineRerankLimit
        }
      },
      'Pipeline complete: retrieval(%d) -> scoring(%d) -> rerank(%d)',
      pipelineMetrics.retrievalCount,
      pipelineMetrics.scoringCount,
      pipelineMetrics.rerankCount
    );

    this.logger.info(
      {
        requestId: context.requestId,
        tenantId: context.tenant.id,
        timings,
        resultCount: response.results.length,
        roleType,
        avgWeightedScore: response.results.length > 0
          ? (response.results.reduce((sum, r) => sum + r.score, 0) / response.results.length).toFixed(3)
          : 0
      },
      'Hybrid search with signal scoring completed.'
    );

    this.performanceTracker.record({
      totalMs: timings.totalMs,
      embeddingMs: timings.embeddingMs,
      retrievalMs: timings.retrievalMs,
      rerankMs: timings.rerankMs,
      rerankApplied: Boolean(rerankOutcome),
      cacheHit: false
    });

    return response;
  }

  private hydrateResult(
    row: PgHybridSearchRow,
    request: HybridSearchRequest,
    resolvedWeights: SignalWeightConfig,
    roleType: RoleType
  ): HybridSearchResultItem {
    const requestedSkills = request.filters?.skills ?? [];
    const { matches, normalizedMatches, coverage } = computeSkillMatches(row.skills ?? undefined, requestedSkills);

    const matchReasons: string[] = [];
    if (matches.length > 0) {
      matchReasons.push(`Matches required skills: ${matches.join(', ')}`);
    }

    if (request.filters?.locations && row.location) {
      const requestedLocations = request.filters.locations.map((loc) => loc.toLowerCase());
      if (requestedLocations.includes(row.location.toLowerCase())) {
        matchReasons.push(`Located in preferred market (${row.location})`);
      }
    }

    if (request.filters?.countries && row.country) {
      if (request.filters.countries.includes(row.country)) {
        matchReasons.push(`Located in ${row.country}`);
      }
    }

    if (typeof request.filters?.minExperienceYears === 'number' && row.years_experience) {
      if (row.years_experience >= request.filters.minExperienceYears) {
        matchReasons.push('Meets minimum experience threshold');
      }
    }

    if (typeof request.filters?.maxExperienceYears === 'number' && row.years_experience) {
      if (row.years_experience <= request.filters.maxExperienceYears) {
        matchReasons.push('Within desired experience range');
      }
    }

    const baseVector = Number(row.vector_score ?? 0);
    const baseText = Number(row.text_score ?? 0);

    // Build search context for Phase 7 signals
    const signalContext: SignalComputationContext = {
      requiredSkills: request.filters?.skills,
      preferredSkills: [], // Could be extended in future
      targetLevel: this.detectTargetLevel(request),
      targetCompanies: this.extractTargetCompanies(request),
      targetIndustries: request.filters?.industries,
      roleType
    };

    // Extract and normalize signal scores from row WITH Phase 7 computation
    const signalScores = extractSignalScores(row, signalContext);

    // Override vectorSimilarity with normalized value from hybrid search
    signalScores.vectorSimilarity = normalizeVectorScore(row.vector_score);

    // Compute weighted score from signals (including Phase 7)
    const weightedScore = computeWeightedScore(signalScores, resolvedWeights);

    // Use weighted score as base, then apply existing modifiers
    let hybridScore = weightedScore;

    // Apply skill coverage boost (existing logic)
    if (coverage > 0) {
      hybridScore += coverage * 0.1;
    }

    // Apply confidence penalty (existing logic)
    const confidence = Number(row.analysis_confidence ?? 0);
    if (confidence < this.config.search.confidenceFloor) {
      hybridScore *= 0.9;
      matchReasons.push('Lower profile confidence score');
    }

    // Clamp to 0-1 range
    hybridScore = Math.max(0, Math.min(1, hybridScore));

    const compliance = {
      legalBasis: row.legal_basis ?? undefined,
      consentRecord: row.consent_record ?? undefined,
      transferMechanism: row.transfer_mechanism ?? undefined
    };
    const hasCompliance = Object.values(compliance).some((value) => typeof value === 'string' && value.length > 0);

    return {
      candidateId: row.candidate_id,
      score: hybridScore,
      vectorScore: baseVector,
      textScore: baseText,
      // RRF fields - only present when RRF is enabled
      rrfScore: row.rrf_score != null ? Number(row.rrf_score) : undefined,
      vectorRank: row.vector_rank != null ? Number(row.vector_rank) : undefined,
      textRank: row.text_rank != null ? Number(row.text_rank) : undefined,
      confidence,
      fullName: row.full_name ?? undefined,
      title: row.current_title ?? undefined,
      headline: row.headline ?? undefined,
      location: row.location ?? undefined,
      country: row.country ?? undefined,
      industries: row.industries ?? undefined,
      yearsExperience: row.years_experience ?? undefined,
      skills:
        (row.skills ?? []).map((skill) => ({
          name: skill,
          weight: normalizedMatches.has(skill.toLowerCase()) ? 1 : 0.3
        })),
      matchReasons,
      metadata: row.metadata ?? undefined,
      compliance: hasCompliance ? compliance : undefined,
      // Signal scoring fields
      signalScores,
      weightsApplied: resolvedWeights,
      roleTypeUsed: roleType
    } satisfies HybridSearchResultItem;
  }

  private rankCandidates(candidates: HybridSearchResultItem[], request: HybridSearchRequest): HybridSearchResultItem[] {
    const requestedSkills = new Set((request.filters?.skills ?? []).map((skill) => skill.toLowerCase()));
    const tenantBoost = this.config.search.ecoBoostFactor;

    const scored = candidates.map((candidate) => {
      let score = candidate.score;

      if (requestedSkills.size > 0 && candidate.skills?.length) {
        const matched = candidate.skills.filter((skill) => requestedSkills.has(skill.name.toLowerCase()));
        if (matched.length > 0) {
          score += matched.length * 0.05 * tenantBoost;
        }
      }

      if (candidate.location && request.filters?.locations?.length) {
        const normalized = candidate.location.toLowerCase();
        if (request.filters.locations.some((loc) => loc.toLowerCase() === normalized)) {
          score += 0.05;
        }
      }

      if (candidate.confidence >= 0.9) {
        score += 0.05;
      }

      return { ...candidate, score } satisfies HybridSearchResultItem;
    });

    return scored.sort((a, b) => b.score - a.score);
  }


  private async applyRerankIfEnabled(
    context: SearchContext,
    request: HybridSearchRequest,
    candidates: HybridSearchResultItem[],
    limit: number
  ): Promise<{ results: HybridSearchResultItem[]; timingsMs?: number; metadata?: Record<string, unknown> } | null> {
    if (!this.config.rerank.enabled || !this.rerankClient || !this.rerankClient.isEnabled()) {
      return null;
    }

    if (candidates.length === 0) {
      return null;
    }

    const jobDescription = request.jobDescription ?? request.query ?? '';
    if (jobDescription.trim().length === 0) {
      this.logger.warn({ requestId: context.requestId }, 'Skipping rerank; job description missing.');
      return null;
    }

    const candidateLimit = Math.min(this.config.search.rerankCandidateLimit, candidates.length);
    const topCandidates = candidates.slice(0, candidateLimit);

    const rerankRequest = this.buildRerankRequest(request, jobDescription, topCandidates, limit);
    const start = Date.now();

    try {
      const rerankResponse = await this.rerankClient.rerank(rerankRequest, {
        tenantId: context.tenant.id,
        requestId: context.requestId
      });

      const merged = this.mergeRerankResults(candidates, rerankResponse);
      const metadata: Record<string, unknown> = {
        cacheHit: rerankResponse.cacheHit,
        usedFallback: rerankResponse.usedFallback
      };
      if (rerankResponse.metadata) {
        metadata.details = rerankResponse.metadata;
      }

      return {
        results: merged,
        timingsMs: rerankResponse.timings?.totalMs ?? Date.now() - start,
        metadata
      };
    } catch (error) {
      this.logger.warn({ error, requestId: context.requestId }, 'Rerank request failed, using base ranking.');
      return { results: candidates };
    }
  }

  private buildRerankRequest(
    request: HybridSearchRequest,
    jobDescription: string,
    candidates: HybridSearchResultItem[],
    limit: number
  ): RerankRequest {
    const docsetHash = createHash('sha1');
    candidates.forEach((candidate) => {
      docsetHash.update(candidate.candidateId);
      docsetHash.update(String(candidate.vectorScore ?? 0));
      docsetHash.update(String(candidate.textScore ?? 0));
    });

    const rerankCandidates: RerankCandidate[] = candidates.map((candidate) => ({
      candidateId: candidate.candidateId,
      summary: candidate.headline ?? candidate.title ?? candidate.fullName,
      highlights: candidate.matchReasons ?? [],
      initialScore: candidate.score,
      features: {
        vectorScore: candidate.vectorScore,
        textScore: candidate.textScore,
        confidence: candidate.confidence,
        yearsExperience: candidate.yearsExperience,
        matchReasons: candidate.matchReasons,
        skills: candidate.skills?.map((skill) => skill.name),
        metadata: candidate.metadata
      },
      payload: candidate.metadata ?? {}
    }));

    return {
      jobDescription,
      query: request.query,
      jdHash: request.jdHash,
      docsetHash: docsetHash.digest('hex'),
      limit,
      candidates: rerankCandidates,
      includeReasons: this.config.search.rerankIncludeReasons,
      requestMetadata: {
        source: 'hh-search-svc',
        includeDebug: request.includeDebug === true
      }
    } satisfies RerankRequest;
  }

  private mergeRerankResults(
    allCandidates: HybridSearchResultItem[],
    rerankResponse: RerankResponse
  ): HybridSearchResultItem[] {
    const candidateMap = new Map(allCandidates.map((candidate) => [candidate.candidateId, candidate]));
    const seen = new Set<string>();
    const reranked: HybridSearchResultItem[] = [];

    rerankResponse.results.forEach((result) => {
      const existing = candidateMap.get(result.candidateId);
      if (!existing) {
        return;
      }

      seen.add(existing.candidateId);
      const mergedMatchReasons = existing.matchReasons ? [...existing.matchReasons] : [];
      result.reasons?.forEach((reason) => {
        if (!mergedMatchReasons.includes(reason)) {
          mergedMatchReasons.push(reason);
        }
      });

      const metadata = existing.metadata ? { ...existing.metadata } : {};
      if (result.payload && Object.keys(result.payload).length > 0) {
        metadata.rerankPayload = result.payload;
      }

      reranked.push({
        ...existing,
        score: result.score,
        matchReasons: mergedMatchReasons,
        metadata
      });
    });

    allCandidates.forEach((candidate) => {
      if (!seen.has(candidate.candidateId)) {
        reranked.push(candidate);
      }
    });

    return reranked;
  }


  /**
   * Detect target seniority level from request
   */
  private detectTargetLevel(request: HybridSearchRequest): string {
    // Check explicit seniority filter
    if (request.filters?.seniorityLevels?.length) {
      return request.filters.seniorityLevels[0];
    }

    // Try to detect from job description or query
    const text = (request.jobDescription || request.query || '').toLowerCase();

    if (text.includes('director') || text.includes('vp') || text.includes('vice president')) {
      return 'director';
    }
    if (text.includes('manager') || text.includes('lead')) {
      return 'manager';
    }
    if (text.includes('staff') || text.includes('principal')) {
      return 'staff';
    }
    if (text.includes('senior') || text.includes('sr.')) {
      return 'senior';
    }
    if (text.includes('junior') || text.includes('entry')) {
      return 'junior';
    }

    return 'mid'; // Default
  }

  /**
   * Extract target companies from request metadata
   */
  private extractTargetCompanies(request: HybridSearchRequest): string[] | undefined {
    // Could be extended to parse from job description
    // For now, check if metadata has target companies
    if (request.filters?.metadata?.targetCompanies) {
      const companies = request.filters.metadata.targetCompanies;
      return Array.isArray(companies) ? companies.map(String) : undefined;
    }
    return undefined;
  }

  private async fetchFromFirestore(tenantId: string, limit: number): Promise<FirestoreCandidateRecord[]> {
    try {
      if (!this.firestore) {
        this.firestore = getFirestore();
      }

      const snapshot = await this.firestore
        .collection('candidates')
        .where('tenant_id', '==', tenantId)
        .orderBy('analysis_confidence', 'desc')
        .limit(limit)
        .get();

      return snapshot.docs.map((doc) => ({
        candidate_id: doc.id,
        ...(doc.data() as Record<string, unknown>)
      })) as FirestoreCandidateRecord[];
    } catch (error) {
      this.logger.error({ error }, 'Firestore fallback failed.');
      return [];
    }
  }

  /**
   * Add LLM-generated match rationales for top candidates.
   * @see TRNS-03
   */
  private async addMatchRationales(
    context: SearchContext,
    request: HybridSearchRequest,
    candidates: HybridSearchResultItem[]
  ): Promise<HybridSearchResultItem[]> {
    if (!this.rerankClient || !this.rerankClient.isEnabled()) {
      this.logger.debug({ requestId: context.requestId }, 'Match rationale skipped - rerank client not available.');
      return candidates;
    }

    const rationaleLimit = request.rationaleLimit ?? 10;
    const topCandidates = candidates.slice(0, rationaleLimit);
    const jobDescription = request.jobDescription ?? request.query ?? '';

    if (jobDescription.trim().length === 0) {
      this.logger.warn({ requestId: context.requestId }, 'Match rationale skipped - no job description.');
      return candidates;
    }

    // Compute JD hash for cache key
    const jdHash = request.jdHash ?? createHash('sha1').update(jobDescription).digest('hex').slice(0, 16);

    // Generate rationales in parallel with Redis caching
    const rationaleResults = await Promise.all(
      topCandidates.map(async (candidate) => {
        // Check cache first
        const cacheKey = `rationale:${candidate.candidateId}:${jdHash}`;

        if (this.redisClient && !this.redisClient.isDisabled()) {
          try {
            const cached = await this.redisClient.get<MatchRationale>(cacheKey);
            if (cached && typeof cached === 'object' && 'summary' in cached) {
              this.logger.debug({ candidateId: candidate.candidateId }, 'Match rationale cache hit.');
              return { candidateId: candidate.candidateId, rationale: cached };
            }
          } catch (error) {
            this.logger.warn({ error, candidateId: candidate.candidateId }, 'Failed to read rationale from cache.');
          }
        }

        // Generate new rationale
        const topSignals = this.getTopSignals(candidate.signalScores, 3);
        const candidateSummary = this.buildCandidateSummary(candidate);

        try {
          const rationale = await this.rerankClient!.generateMatchRationale(
            {
              jobDescription,
              candidateSummary,
              topSignals
            },
            {
              tenantId: context.tenant.id,
              requestId: context.requestId
            }
          );

          // Cache for 24 hours (86400 seconds)
          if (this.redisClient && !this.redisClient.isDisabled()) {
            try {
              await this.redisClient.set(cacheKey, rationale, 86400);
              this.logger.debug({ candidateId: candidate.candidateId }, 'Match rationale cached.');
            } catch (error) {
              this.logger.warn({ error, candidateId: candidate.candidateId }, 'Failed to cache rationale.');
            }
          }

          return { candidateId: candidate.candidateId, rationale };
        } catch (error) {
          this.logger.warn({ error, candidateId: candidate.candidateId }, 'Failed to generate match rationale.');
          return { candidateId: candidate.candidateId, rationale: null };
        }
      })
    );

    // Build a map of candidate ID to rationale
    const rationaleMap = new Map<string, MatchRationale>();
    for (const result of rationaleResults) {
      if (result.rationale) {
        rationaleMap.set(result.candidateId, result.rationale);
      }
    }

    // Merge rationales into candidates
    return candidates.map((candidate) => ({
      ...candidate,
      matchRationale: rationaleMap.get(candidate.candidateId)
    }));
  }

  /**
   * Get the top N signal scores with human-readable names.
   */
  private getTopSignals(
    scores: SignalScores | undefined,
    limit: number
  ): Array<{ name: string; score: number }> {
    if (!scores) return [];

    const signalNames: Record<string, string> = {
      skillsExactMatch: 'Skills Match',
      trajectoryFit: 'Career Trajectory',
      seniorityAlignment: 'Seniority Fit',
      recencyBoost: 'Skill Recency',
      companyRelevance: 'Company Fit',
      vectorSimilarity: 'Semantic Match',
      levelMatch: 'Level Match',
      specialtyMatch: 'Specialty Match',
      techStackMatch: 'Tech Stack',
      functionMatch: 'Function Fit',
      companyPedigree: 'Company Quality',
      skillsInferred: 'Inferred Skills',
      skillsMatch: 'Skills Match'
    };

    return Object.entries(scores)
      .filter(([, score]) => typeof score === 'number' && score > 0)
      .sort(([, a], [, b]) => (b as number) - (a as number))
      .slice(0, limit)
      .map(([key, score]) => ({
        name: signalNames[key] || key,
        score: score as number
      }));
  }

  /**
   * Build a concise candidate summary for rationale generation.
   */
  private buildCandidateSummary(candidate: HybridSearchResultItem): string {
    const parts: string[] = [];

    if (candidate.fullName) {
      parts.push(candidate.fullName);
    }
    if (candidate.title) {
      parts.push(candidate.title);
    }
    if (candidate.yearsExperience) {
      parts.push(`${candidate.yearsExperience} years exp`);
    }
    if (candidate.skills && candidate.skills.length > 0) {
      const topSkills = candidate.skills
        .slice(0, 5)
        .map((s) => s.name)
        .join(', ');
      parts.push(topSkills);
    }
    if (candidate.headline) {
      parts.push(candidate.headline.slice(0, 100));
    }

    return parts.join(' | ') || 'No candidate details available';
  }
}
