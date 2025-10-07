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

interface HybridSearchDependencies {
  config: SearchServiceConfig;
  pgClient: PgVectorClient;
  embedClient: EmbedClient;
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

export class SearchService {
  private readonly config: SearchServiceConfig;
  private readonly pgClient: PgVectorClient;
  private readonly embedClient: EmbedClient;
  private readonly logger: Logger;
  private firestore: Firestore | null = null;

  constructor(deps: HybridSearchDependencies) {
    this.config = deps.config;
    this.pgClient = deps.pgClient;
    this.embedClient = deps.embedClient;
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

    let embedding = request.embedding;
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
      warmupMultiplier: this.config.search.warmupMultiplier
    });
    timings.retrievalMs = Date.now() - retrievalStart;

    let candidates = rows.map((row) => this.hydrateResult(row, request));

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
        metadata: record.metadata
      } satisfies HybridSearchResultItem));
    }

    const rankingStart = Date.now();
    const ranked = this.rankCandidates(candidates, request);
    timings.rankingMs = Date.now() - rankingStart;

    const response: HybridSearchResponse = {
      results: ranked.slice(0, limit),
      total: ranked.length,
      cacheHit: false,
      requestId: context.requestId,
      timings,
      metadata: {
        vectorWeight: this.config.search.vectorWeight,
        textWeight: this.config.search.textWeight,
        minSimilarity: this.config.search.minSimilarity
      }
    };

    if (request.includeDebug) {
      response.debug = {
        candidateCount: ranked.length,
        filtersApplied: request.filters ?? {},
        minSimilarity: this.config.search.minSimilarity
      };
    }

    timings.totalMs = Date.now() - totalStart;
    this.logger.info(
      { requestId: context.requestId, tenantId: context.tenant.id, timings, resultCount: response.results.length },
      'Hybrid search completed.'
    );

    return response;
  }

  private hydrateResult(row: PgHybridSearchRow, request: HybridSearchRequest): HybridSearchResultItem {
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
    let hybridScore = Number(row.hybrid_score ?? 0);

    if (coverage > 0) {
      hybridScore += coverage * 0.1;
    }

    const confidence = Number(row.analysis_confidence ?? 0);
    if (confidence < this.config.search.confidenceFloor) {
      hybridScore *= 0.9;
      matchReasons.push('Lower profile confidence score');
    }

    return {
      candidateId: row.candidate_id,
      score: hybridScore,
      vectorScore: baseVector,
      textScore: baseText,
      confidence,
      fullName: row.full_name ?? undefined,
      title: row.current_title ?? undefined,
      headline: row.headline ?? undefined,
      location: row.location ?? undefined,
      industries: row.industries ?? undefined,
      yearsExperience: row.years_experience ?? undefined,
      skills:
        (row.skills ?? []).map((skill) => ({
          name: skill,
          weight: normalizedMatches.has(skill.toLowerCase()) ? 1 : 0.3
        })),
      matchReasons,
      metadata: row.metadata ?? undefined
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
