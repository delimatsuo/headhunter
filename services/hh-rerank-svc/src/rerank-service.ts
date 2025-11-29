import { createHash } from 'crypto';
import { badRequestError, getLogger } from '@hh/common';
import type { Logger } from 'pino';

import type { RerankServiceConfig } from './config.js';
import type {
  RerankCacheDescriptor,
  RerankContext,
  RerankRequest,
  RerankResponse,
  TogetherChatCompletionResponsePayload,
  TogetherChatCompletionRequestPayload,
  TogetherChatMessage,
  TogetherRerankCandidate,
  RerankResult
} from './types.js';
import { TogetherClient } from './together-client.js';
import { GeminiClient, type GeminiRerankRequest, type GeminiRerankResponse } from './gemini-client.js';
import { RerankRedisClient } from './redis-client.js';

interface RerankOptions {
  context: RerankContext;
  request: RerankRequest;
}

interface ParsedTogetherResult {
  id: string;
  score: number;
}

export class RerankService {
  private readonly logger: Logger;

  constructor(
    private readonly dependencies: {
      config: RerankServiceConfig;
      togetherClient: TogetherClient;
      geminiClient: GeminiClient;
      redisClient?: RerankRedisClient;
      logger?: Logger;
    }
  ) {
    this.logger = dependencies.logger ?? getLogger({ module: 'rerank-service' });
  }

  buildCacheDescriptor(
    request: RerankRequest,
    options?: { togetherCandidates?: TogetherRerankCandidate[]; includePayload?: boolean }
  ): RerankCacheDescriptor {
    const jdHash = request.jdHash && request.jdHash.trim().length > 0 ? request.jdHash : this.computeHash(request.jobDescription);
    const includePayload = options?.includePayload ?? this.shouldIncludePayload(request);
    const togetherCandidates =
      options?.togetherCandidates ?? this.buildTogetherCandidates(request.candidates, includePayload);
    const docsetHash =
      request.docsetHash && request.docsetHash.trim().length > 0
        ? request.docsetHash
        : this.computeDocsetHash(togetherCandidates);

    return { jdHash, docsetHash } satisfies RerankCacheDescriptor;
  }

  async rerank({ context, request }: RerankOptions): Promise<RerankResponse> {
    const start = Date.now();
    const { runtime, together, gemini } = this.dependencies.config;

    if (!request.candidates || request.candidates.length === 0) {
      throw badRequestError('At least one candidate is required for reranking.');
    }

    if (request.candidates.length < runtime.minCandidates) {
      this.logger.debug({ tenantId: context.tenant.id, count: request.candidates.length }, 'Not enough candidates for Together rerank; returning passthrough ordering.');
      return this.buildPassthroughResponse(context, request, request.candidates, Math.min(request.limit ?? runtime.defaultLimit, request.candidates.length));
    }

    if (request.candidates.length > runtime.maxCandidates) {
      this.logger.warn({ received: request.candidates.length, max: runtime.maxCandidates }, 'Received more candidates than configured maximum; truncating set before rerank.');
    }

    const limit = Math.min(request.limit ?? runtime.defaultLimit, runtime.maxCandidates, request.candidates.length);
    const truncatedCandidates = request.candidates.slice(0, runtime.maxCandidates);
    const includePayload = this.shouldIncludePayload(request);

    const promptStart = Date.now();
    const togetherCandidates = this.buildTogetherCandidates(truncatedCandidates, includePayload);
    const normalizedJobDescription = this.normalizeJobDescription(request.jobDescription, runtime.maxPromptCharacters);
    const messages = this.buildChatMessages(normalizedJobDescription, togetherCandidates, limit);
    const promptMs = Date.now() - promptStart;

    const descriptor = this.buildCacheDescriptor(
      { ...request, candidates: truncatedCandidates },
      { togetherCandidates, includePayload }
    );

    // Check cache if enabled
    if (this.dependencies.redisClient && !request.disableCache) {
      const cacheKey = this.dependencies.redisClient.buildKey(context.tenant.id, descriptor);
      const cached = await this.dependencies.redisClient.get<RerankResult[]>(cacheKey);

      if (cached) {
        const cacheMs = Date.now() - start;
        this.logger.info({ requestId: context.requestId, cacheMs }, 'Rerank cache hit');

        return {
          results: cached,
          cacheHit: true,
          usedFallback: false,
          requestId: context.requestId,
          timings: {
            totalMs: cacheMs,
            cacheMs
          },
          metadata: {
            candidateCount: truncatedCandidates.length,
            limit,
            docsetHash: descriptor.docsetHash,
            jdHash: descriptor.jdHash,
            llmProvider: 'cache'
          }
        };
      }
    }

    const elapsed = Date.now() - start;
    const rawBudgetMs = runtime.slaTargetMs - elapsed - promptMs - 20;
    const budgetMs = Math.max(0, rawBudgetMs);

    // Log budget calculation for debugging
    this.logger.info({
      slaTargetMs: runtime.slaTargetMs,
      elapsed,
      promptMs,
      rawBudgetMs,
      budgetMs,
      geminiEnabled: gemini.enable,
      togetherEnabled: together.enable
    }, 'LLM budget calculated');

    const includeReasons = request.includeReasons ?? true;
    let results = this.buildPassthroughOrdering(truncatedCandidates, limit, includeReasons);
    let usedFallback = true;
    let llmProvider: 'gemini' | 'together' | 'none' = 'none';
    let llmMs: number | undefined;

    // Try Gemini first (if enabled)
    if (gemini.enable) {
      try {
        this.logger.info({ requestId: context.requestId }, 'Attempting Gemini rerank');

        const geminiRequest: GeminiRerankRequest = {
          jobDescription: normalizedJobDescription,
          candidates: truncatedCandidates.map(c => ({
            candidateId: c.candidateId,
            summary: c.summary,
            highlights: c.highlights,
            skills: c.features?.skills
          })),
          topN: limit,
          includeReasons
        };

        const geminiResult = await this.dependencies.geminiClient.rerank(geminiRequest, {
          requestId: context.requestId,
          tenantId: context.tenant.id,
          topN: limit,
          budgetMs
        });

        if (geminiResult?.data) {
          const geminiData = geminiResult.data as GeminiRerankResponse;
          const parsedResults: ParsedTogetherResult[] = geminiData.candidates.map(c => ({
            id: c.candidateId,
            score: c.score
          }));

          if (parsedResults.length > 0) {
            results = this.mergeRerankResults(parsedResults, truncatedCandidates, limit, includeReasons);
            usedFallback = false;
            llmProvider = 'gemini';
            llmMs = geminiResult.latencyMs;
            this.logger.info({ requestId: context.requestId, latencyMs: llmMs, resultCount: parsedResults.length }, 'Gemini rerank succeeded');
          } else {
            this.logger.warn({ requestId: context.requestId }, 'Gemini returned empty results');
          }
        }
      } catch (error) {
        this.logger.warn(
          { error: error instanceof Error ? error.message : error, requestId: context.requestId },
          'Gemini rerank failed, will try Together AI fallback'
        );
      }
    }

    // Fallback to Together AI if Gemini failed or disabled
    if (usedFallback && together.enable) {
      try {
        this.logger.info({ requestId: context.requestId }, 'Attempting Together AI rerank');

        const togetherPayload: TogetherChatCompletionRequestPayload = {
          model: together.model,
          messages,
          temperature: 0,
          max_tokens: 128,
          response_format: { type: 'json_object' },
          user: context.user?.uid,
          context: {
            tenantId: context.tenant.id,
            requestId: context.requestId,
            query: request.query ?? null,
            docsetHash: descriptor.docsetHash,
            limit
          }
        } satisfies TogetherChatCompletionRequestPayload;

        const togetherResult = await this.dependencies.togetherClient.rerank(togetherPayload, {
          requestId: context.requestId,
          tenantId: context.tenant.id,
          topN: limit,
          context: togetherPayload.context,
          budgetMs
        });

        if (togetherResult?.data) {
          const parsedResults = this.parseTogetherResults(togetherResult.data);
          if (parsedResults.length > 0) {
            results = this.mergeRerankResults(parsedResults, truncatedCandidates, limit, includeReasons);
            usedFallback = false;
            llmProvider = 'together';
            llmMs = togetherResult.latencyMs;
            this.logger.info({ requestId: context.requestId, latencyMs: llmMs, resultCount: parsedResults.length }, 'Together AI rerank succeeded');
          } else if (!runtime.allowGracefulDegradation) {
            throw badRequestError('Rerank vendor did not return any results.');
          }
        } else if (!runtime.allowGracefulDegradation) {
          throw badRequestError('Rerank vendor unavailable and graceful degradation disabled.');
        }
      } catch (error) {
        this.logger.warn(
          { error: error instanceof Error ? error.message : error, requestId: context.requestId },
          'Together AI rerank failed'
        );
        if (!runtime.allowGracefulDegradation) {
          throw badRequestError('Rerank vendor returned invalid response.');
        }
      }
    }

    // Final check: if both failed and graceful degradation not allowed
    if (usedFallback && !runtime.allowGracefulDegradation) {
      throw badRequestError('All rerank providers failed and graceful degradation disabled.');
    }

    const totalMs = Date.now() - start;

    if (totalMs > runtime.slowLogMs) {
      this.logger.warn(
        {
          totalMs,
          geminiMs: llmProvider === 'gemini' ? llmMs : undefined,
          togetherMs: llmProvider === 'together' ? llmMs : undefined,
          candidateCount: truncatedCandidates.length,
          limit,
          requestId: context.requestId,
          tenantId: context.tenant.id,
          fallback: usedFallback,
          llmProvider
        },
        'Slow rerank invocation.'
      );
    }

    const response: RerankResponse = {
      results,
      cacheHit: false,
      usedFallback,
      requestId: context.requestId,
      timings: {
        totalMs,
        togetherMs: llmProvider === 'together' ? llmMs : undefined,
        geminiMs: llmProvider === 'gemini' ? llmMs : undefined,
        promptMs
      },
      metadata: {
        candidateCount: truncatedCandidates.length,
        limit,
        docsetHash: descriptor.docsetHash,
        jdHash: descriptor.jdHash,
        llmProvider
      }
    } satisfies RerankResponse;

    // Cache successful results if not fallback (or if fallback is acceptable to cache?)
    // Usually we only cache LLM results, not passthrough fallback.
    // But here usedFallback=true means we used Together or Passthrough?
    // Wait, usedFallback=false means we used Gemini (primary).
    // usedFallback=true means we used Together (fallback) or Passthrough.
    // If llmProvider is 'gemini' or 'together', we should cache.
    if (this.dependencies.redisClient && !request.disableCache && (llmProvider === 'gemini' || llmProvider === 'together')) {
      const cacheKey = this.dependencies.redisClient.buildKey(context.tenant.id, descriptor);
      // Fire and forget cache write
      this.dependencies.redisClient.set(cacheKey, results).catch(err => {
        this.logger.warn({ error: err }, 'Failed to write to rerank cache');
      });
    }

    return response;
  }

  private mergeRerankResults(
    reranked: ParsedTogetherResult[],
    candidates: RerankRequest['candidates'],
    limit: number,
    includeReasons: boolean
  ) {
    const lookup = new Map(candidates.map((candidate) => [candidate.candidateId, candidate]));
    const passthrough = this.getPassthroughSortedCandidates(candidates);
    const seen = new Set<string>();

    const mapped: { candidate: RerankRequest['candidates'][number]; score: number }[] = [];

    for (const entry of reranked) {
      const candidate = lookup.get(entry.id);
      if (!candidate || seen.has(candidate.candidateId)) {
        continue;
      }

      const numericScore = Number.isFinite(entry.score) ? Number(entry.score) : 0;
      mapped.push({ candidate, score: numericScore });
      seen.add(candidate.candidateId);

      if (mapped.length >= limit) {
        break;
      }
    }

    if (mapped.length < limit) {
      for (const candidate of passthrough) {
        if (seen.has(candidate.candidateId)) {
          continue;
        }

        mapped.push({ candidate, score: this.getCandidateBaseScore(candidate) });
        seen.add(candidate.candidateId);

        if (mapped.length >= limit) {
          break;
        }
      }
    }

    return mapped.slice(0, limit).map(({ candidate, score }, index) => ({
      candidateId: candidate.candidateId,
      rank: index + 1,
      score,
      reasons: includeReasons ? this.buildReasons(candidate, score) : [],
      summary: candidate.summary,
      payload: candidate.payload
    }));
  }

  private buildPassthroughOrdering(
    candidates: RerankRequest['candidates'],
    limit: number,
    includeReasons: boolean
  ) {
    const sorted = this.getPassthroughSortedCandidates(candidates);

    return sorted.slice(0, limit).map((candidate, index) => {
      const score = this.getCandidateBaseScore(candidate);
      return {
        candidateId: candidate.candidateId,
        rank: index + 1,
        score,
        reasons: includeReasons ? this.buildReasons(candidate, score) : [],
        summary: candidate.summary,
        payload: candidate.payload
      };
    });
  }

  private buildPassthroughResponse(
    context: RerankContext,
    request: RerankRequest,
    candidates: RerankRequest['candidates'],
    limit: number
  ): RerankResponse {
    const includePayload = this.shouldIncludePayload(request);
    const togetherCandidates = this.buildTogetherCandidates(candidates, includePayload);
    const descriptor = this.buildCacheDescriptor(
      { ...request, candidates },
      { togetherCandidates, includePayload }
    );

    return {
      results: this.buildPassthroughOrdering(candidates, limit, request.includeReasons ?? true),
      cacheHit: false,
      usedFallback: true,
      requestId: context.requestId,
      timings: {
        totalMs: 0
      },
      metadata: {
        docsetHash: descriptor.docsetHash,
        jdHash: descriptor.jdHash
      }
    } satisfies RerankResponse;
  }

  private buildTogetherCandidates(
    candidates: RerankRequest['candidates'],
    includePayload: boolean
  ): TogetherRerankCandidate[] {
    return candidates.map((candidate) => this.buildTogetherCandidate(candidate, includePayload));
  }

  private buildTogetherCandidate(
    candidate: RerankRequest['candidates'][number],
    includePayload: boolean
  ): TogetherRerankCandidate {
    const { runtime } = this.dependencies.config;
    const parts: string[] = [];

    if (candidate.summary) {
      parts.push(candidate.summary.trim());
    }

    const highlights = candidate.highlights?.filter((value) => value && value.trim().length > 0).slice(0, runtime.maxHighlights);
    if (highlights?.length) {
      parts.push(`Highlights: ${highlights.join(' | ')}`);
    }

    const featureSegments: string[] = [];
    if (candidate.features?.currentTitle) {
      featureSegments.push(`Title: ${candidate.features.currentTitle}`);
    }
    if (candidate.features?.location) {
      featureSegments.push(`Location: ${candidate.features.location}`);
    }
    if (typeof candidate.features?.yearsExperience === 'number') {
      featureSegments.push(`Experience: ${candidate.features.yearsExperience} years`);
    }
    const skills = candidate.features?.skills?.filter((value) => value && value.trim().length > 0).slice(0, runtime.maxSkills);
    if (skills?.length) {
      featureSegments.push(`Skills: ${skills.join(', ')}`);
    }
    const matchReasons = candidate.features?.matchReasons
      ?.filter((value) => value && value.trim().length > 0)
      .slice(0, runtime.reasonLimit);
    if (matchReasons?.length) {
      featureSegments.push(`Match reasons: ${matchReasons.join('; ')}`);
    }
    if (featureSegments.length) {
      parts.push(featureSegments.join(' | '));
    }

    if (includePayload && candidate.payload) {
      parts.push(`Payload: ${JSON.stringify(candidate.payload)}`);
    }

    const content = parts
      .map((value) => value.trim())
      .filter((value) => value.length > 0)
      .join('\n')
      .slice(0, runtime.maxPromptCharacters);

    return {
      id: candidate.candidateId,
      content
    } satisfies TogetherRerankCandidate;
  }

  private buildChatMessages(
    jobDescription: string,
    candidates: TogetherRerankCandidate[],
    limit: number
  ): TogetherChatMessage[] {
    const systemMessage: TogetherChatMessage = {
      role: 'system',
      content:
        'You are an expert recruiting assistant who ranks candidates. Always respond with valid JSON exactly matching {"results":[{"id":string,"score":number}]} sorted best to worst. Scores must be between 0 and 1.'
    };

    const candidateSections = candidates
      .map((candidate, index) => `Candidate ${index + 1} (id=${candidate.id}): ${candidate.content}`)
      .join('\n---\n');

    const userParts = [
      `Job description:\n${jobDescription}`,
      `Candidates (return up to ${limit}):`,
      candidateSections,
      'Respond only with the JSON object.'
    ].filter((part) => part && part.trim().length > 0);

    const userMessage: TogetherChatMessage = {
      role: 'user',
      content: userParts.join('\n\n')
    };

    return [systemMessage, userMessage];
  }

  private parseTogetherResults(data: TogetherChatCompletionResponsePayload): ParsedTogetherResult[] {
    const choice = data?.choices?.find((item) => item?.message?.content?.trim().length);
    const content = choice?.message?.content?.trim();

    if (!content) {
      return [];
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(content);
    } catch (error) {
      throw new Error('Together chat completion returned non-JSON content.');
    }

    if (!parsed || typeof parsed !== 'object' || !Array.isArray((parsed as Record<string, unknown>).results)) {
      throw new Error('Together chat completion JSON missing results array.');
    }

    const results = (parsed as { results: Array<{ id?: unknown; score?: unknown }> }).results;

    return results
      .filter((item): item is { id: string; score?: unknown } => typeof item?.id === 'string')
      .map((item) => {
        const score = typeof item.score === 'number' ? item.score : Number(item.score ?? 0);
        return {
          id: item.id,
          score: Number.isFinite(score) ? score : 0
        } satisfies ParsedTogetherResult;
      });
  }

  private getPassthroughSortedCandidates(candidates: RerankRequest['candidates']) {
    return [...candidates].sort((a, b) => this.getCandidateBaseScore(b) - this.getCandidateBaseScore(a));
  }

  private getCandidateBaseScore(candidate: RerankRequest['candidates'][number]): number {
    if (typeof candidate.initialScore === 'number') {
      return candidate.initialScore;
    }
    if (typeof candidate.features?.vectorScore === 'number') {
      return candidate.features.vectorScore;
    }
    if (typeof candidate.features?.textScore === 'number') {
      return candidate.features.textScore;
    }
    return 0;
  }

  private buildReasons(candidate: RerankRequest['candidates'][number], score: number): string[] {
    const reasons: string[] = [];

    if (typeof candidate.initialScore === 'number') {
      reasons.push(`Initial score ${candidate.initialScore.toFixed(2)}`);
    } else if (typeof candidate.features?.vectorScore === 'number') {
      reasons.push(`Vector score ${candidate.features.vectorScore.toFixed(2)}`);
    }

    if (candidate.features?.matchReasons?.length) {
      reasons.push(...candidate.features.matchReasons.slice(0, this.dependencies.config.runtime.reasonLimit));
    }

    if (candidate.features?.skills?.length) {
      reasons.push(
        `Skills: ${candidate.features.skills
          .slice(0, this.dependencies.config.runtime.maxSkills)
          .join(', ')}`
      );
    }

    if (Number.isFinite(score)) {
      reasons.push(`Model score ${score.toFixed(4)}`);
    }

    return reasons.slice(0, this.dependencies.config.runtime.reasonLimit);
  }

  private shouldIncludePayload(request: RerankRequest): boolean {
    return request.requestMetadata?.includePayload === true;
  }

  private normalizeJobDescription(jobDescription: string, maxLength: number): string {
    return jobDescription.trim().slice(0, maxLength);
  }

  private computeHash(value: string): string {
    return createHash('sha256').update(value.trim()).digest('hex').slice(0, 24);
  }

  private computeDocsetHash(candidates: TogetherRerankCandidate[]): string {
    const hash = createHash('sha256');
    candidates.forEach((candidate) => {
      hash.update(`${candidate.id}::${candidate.content}`);
    });
    return hash.digest('hex').slice(0, 24);
  }
}
