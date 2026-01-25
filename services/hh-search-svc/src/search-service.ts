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
  SearchContext
} from './types';
import type { PgVectorClient } from './pgvector-client';
import type { SearchRedisClient } from './redis-client';
import type { RerankClient, RerankCandidate, RerankRequest, RerankResponse } from './rerank-client';
import type { PerformanceTracker } from './performance-tracker';
import { resolveWeights, type SignalWeightConfig, type RoleType } from './signal-weights';
import { computeWeightedScore, extractSignalScores, normalizeVectorScore, completeSignalScores } from './scoring';

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
    timings.retrievalMs = Date.now() - retrievalStart;

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

    const rankingStart = Date.now();
    let ranked = this.rankCandidates(candidates, request);
    timings.rankingMs = Date.now() - rankingStart;

    const rerankOutcome = await this.applyRerankIfEnabled(context, request, ranked, limit);

    if (rerankOutcome) {
      ranked = rerankOutcome.results;
      if (rerankOutcome.timingsMs !== undefined) {
        timings.rerankMs = rerankOutcome.timingsMs;
      }
    }

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
        }))
      };
    }

    timings.totalMs = Date.now() - totalStart;
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

    // Extract and normalize signal scores from row
    const signalScores = extractSignalScores(row);

    // Override vectorSimilarity with normalized value from hybrid search
    signalScores.vectorSimilarity = normalizeVectorScore(row.vector_score);

    // Compute weighted score from signals
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
}
