import { getLogger } from '@hh/common';
import type { Logger } from 'pino';

import type { MsgsServiceConfig } from './config';
import { MsgsCloudSqlClient } from './cloudsql-client';
import type { DemandSeriesRow, RoleTemplateRow, SkillAdjacencyRow } from './cloudsql-client';
import { MsgsRedisClient } from './redis-client';
import {
  classifyTrend,
  calculateEma,
  calculatePmi,
  calculateZScores,
  applyRecencyDecay
} from './math-utils';
import {
  buildSeedMarketDemand,
  buildSeedRoleTemplate,
  buildSeedSkillExpansion
} from './seed-data';
import type {
  MarketDemandQuerystring,
  MarketDemandResponse,
  MsgsCacheEntry,
  RoleTemplateRequestBody,
  RoleTemplateResponse,
  SkillAdjacencyEdge,
  SkillExpandRequestBody,
  SkillExpandResponse
} from './types';

interface MsgsServiceDeps {
  config: MsgsServiceConfig;
  redisClient: MsgsRedisClient;
  dbClient: MsgsCloudSqlClient;
  logger?: Logger;
}

export class MsgsService {
  private readonly logger: Logger;

  constructor(private readonly deps: MsgsServiceDeps) {
    this.logger = deps.logger ?? getLogger({ module: 'msgs-service' });
  }

  private now(): number {
    return Date.now();
  }

  private buildFingerprint(payload: unknown): string {
    return Buffer.from(JSON.stringify(payload)).toString('base64');
  }

  private buildCacheEntry<T>(payload: T, ttlSeconds: number): MsgsCacheEntry<T> {
    const storedAt = this.now();
    return {
      payload,
      storedAt,
      expiresAt: storedAt + ttlSeconds * 1000,
      version: this.deps.config.runtime.templateVersion
    } satisfies MsgsCacheEntry<T>;
  }

  private enrichAdjacency(rows: SkillAdjacencyRow[]): SkillAdjacencyEdge[] {
    return rows.map((row) => ({
      skillId: row.related_skill_id,
      label: row.related_skill_label,
      score: row.score,
      support: row.support,
      recencyDays: row.recency_days,
      sources: row.sources
    }));
  }

  private async computeRoleDemandIndex(
    tenantId: string,
    template: RoleTemplateResponse
  ): Promise<number | undefined> {
    const skills = template.requiredSkills.map((skill) => skill.skillId).filter(Boolean);
    if (!skills.length) {
      return undefined;
    }

    const region = 'BR-SP';
    const windowWeeks = Math.max(
      this.deps.config.calculations.emaMinPoints,
      this.deps.config.calculations.emaZScoreWindow
    );

    if (this.deps.config.runtime.useSeedData) {
      const emaValues = skills
        .map((skillId) =>
          buildSeedMarketDemand({
            skillId,
            region,
            windowWeeks,
            industry: undefined
          })
        )
        .filter((payload): payload is MarketDemandResponse => Boolean(payload))
        .map((payload) => payload.latestEma)
        .filter((value) => Number.isFinite(value));

      if (!emaValues.length) {
        return undefined;
      }

      return emaValues.reduce((sum, value) => sum + value, 0) / emaValues.length;
    }

    const emaValues = await Promise.all(
      skills.map(async (skillId) => {
        const rows = await this.deps.dbClient.fetchDemandSeries(
          tenantId,
          skillId,
          region,
          windowWeeks
        );

        const demand = this.buildDemandFromRows(tenantId, { skillId, region }, rows);
        return demand?.latestEma ?? null;
      })
    );

    const filtered = emaValues.filter((value): value is number => value !== null && Number.isFinite(value));
    if (!filtered.length) {
      return undefined;
    }

    return filtered.reduce((sum, value) => sum + value, 0) / filtered.length;
  }

  async expandSkills(
    tenantId: string,
    request: SkillExpandRequestBody,
    options: { bypassCache?: boolean } = {}
  ): Promise<SkillExpandResponse> {
    const topK = Math.max(1, Math.min(request.topK ?? 10, 25));
    const { skillId: _ignoredSkillId, ...fingerprintSource } = request;
    const fingerprint = this.buildFingerprint({
      ...fingerprintSource,
      topK,
      filters: request.filters ?? undefined
    });

    if (!options.bypassCache && !this.deps.config.redis.disable) {
      const cached = await this.deps.redisClient.readSkillExpansion(tenantId, request.skillId, fingerprint);
      if (cached && cached.expiresAt > this.now()) {
        return {
          ...cached.payload,
          cacheHit: true
        } satisfies SkillExpandResponse;
      }
    }

    let response: SkillExpandResponse | null = null;

    if (this.deps.config.runtime.useSeedData) {
      response = buildSeedSkillExpansion({
        tenantId,
        skillId: request.skillId,
        topK,
        filters: request.filters
      });
    } else {
      const rows = await this.deps.dbClient.fetchSkillAdjacency(tenantId, request.skillId, topK * 2);
      const filtered = rows
        .filter((row) => row.support >= this.deps.config.calculations.pmiMinSupport)
        .map((row) => {
          const decay = applyRecencyDecay(row.recency_days, this.deps.config.calculations.pmiDecayDays);
          const baseScore = row.score ?? 0;
          const fallback = calculatePmi({
            jointCount: row.support,
            baseCount: Math.max(row.support + 10, 1),
            relatedCount: Math.max(row.support + 12, 1),
            totalDocuments: Math.max(row.support + 240, 1),
            decayFactor: decay
          });
          const adjustedScore = (baseScore > 0 ? baseScore * decay : fallback) || 0;
          return {
            ...row,
            score: adjustedScore
          } satisfies SkillAdjacencyRow;
        })
        .filter((row) => row.score >= this.deps.config.calculations.pmiMinScore)
        .sort((a, b) => b.score - a.score)
        .slice(0, topK);

      const adjacent = this.enrichAdjacency(filtered);
      response = {
        seedSkill: {
          skillId: request.skillId,
          label: adjacent.length ? adjacent[0].label : request.skillId
        },
        adjacent,
        cacheHit: false,
        generatedAt: new Date().toISOString(),
        meta: {
          tenantId,
          filters: request.filters,
          algorithm: 'pmi-cloudsql'
        }
      } satisfies SkillExpandResponse;
    }

    if (!response) {
      response = {
        seedSkill: { skillId: request.skillId, label: request.skillId },
        adjacent: [],
        cacheHit: false,
        generatedAt: new Date().toISOString(),
        meta: { tenantId, filters: request.filters, algorithm: 'fallback-empty' }
      } satisfies SkillExpandResponse;
    }

    if (!options.bypassCache && !this.deps.config.redis.disable) {
      const entry = this.buildCacheEntry(response, this.deps.config.redis.skillTtlSeconds);
      await this.deps.redisClient.writeSkillExpansion(tenantId, request.skillId, fingerprint, entry);
    }

    this.logger.info(
      { tenantId, skillId: request.skillId, topK, source: this.deps.config.runtime.useSeedData ? 'seed' : 'cloudsql' },
      'Skill expansion generated.'
    );

    return response;
  }

  private mapRoleTemplateRow(row: RoleTemplateRow): RoleTemplateResponse {
    return {
      ecoId: row.eco_id,
      locale: row.locale,
      title: row.title,
      version: row.version ?? this.deps.config.runtime.templateVersion,
      summary: row.summary,
      requiredSkills: row.required_skills.map((item) => ({
        skillId: item.skill_id,
        label: item.label,
        importance: item.importance,
        source: 'required'
      })),
      preferredSkills: row.preferred_skills.map((item) => ({
        skillId: item.skill_id,
        label: item.label,
        importance: item.importance,
        source: 'preferred'
      })),
      yearsExperienceMin: row.yoe_min ?? undefined,
      yearsExperienceMax: row.yoe_max ?? undefined,
      generatedAt: new Date().toISOString(),
      cacheHit: false
    } satisfies RoleTemplateResponse;
  }

  async getRoleTemplate(
    tenantId: string,
    request: RoleTemplateRequestBody,
    options: { bypassCache?: boolean } = {}
  ): Promise<RoleTemplateResponse | null> {
    const locale = request.locale ?? this.deps.config.runtime.templateDefaultLocale;

    if (!options.bypassCache && !this.deps.config.redis.disable) {
      const cached = await this.deps.redisClient.readRoleTemplate(tenantId, request.ecoId, locale);
      if (cached && cached.expiresAt > this.now()) {
        let payload = { ...cached.payload } satisfies RoleTemplateResponse;

        if (request.includeDemand && (payload.demandIndex === undefined || Number.isNaN(payload.demandIndex))) {
          const demandIndex = await this.computeRoleDemandIndex(tenantId, payload);
          if (typeof demandIndex === 'number' && Number.isFinite(demandIndex)) {
            payload = {
              ...payload,
              demandIndex
            } satisfies RoleTemplateResponse;

            const refreshedEntry = this.buildCacheEntry(
              { ...payload, cacheHit: false } satisfies RoleTemplateResponse,
              this.deps.config.redis.roleTtlSeconds
            );
            await this.deps.redisClient.writeRoleTemplate(tenantId, request.ecoId, locale, refreshedEntry);
          }
        }

        return {
          ...payload,
          cacheHit: true
        } satisfies RoleTemplateResponse;
      }
    }

    let response: RoleTemplateResponse | null = null;

    if (this.deps.config.runtime.useSeedData) {
      const seed = buildSeedRoleTemplate({ ecoId: request.ecoId, locale });
      response = seed ? { ...seed, cacheHit: false } : null;
    } else {
      const row = await this.deps.dbClient.fetchRoleTemplate(tenantId, request.ecoId, locale);
      response = row ? this.mapRoleTemplateRow(row) : null;
    }

    if (response && request.includeDemand) {
      const demandIndex = await this.computeRoleDemandIndex(tenantId, response);
      if (typeof demandIndex === 'number' && Number.isFinite(demandIndex)) {
        response = {
          ...response,
          demandIndex
        } satisfies RoleTemplateResponse;
      }
    }

    if (response && !options.bypassCache && !this.deps.config.redis.disable) {
      const entry = this.buildCacheEntry(response, this.deps.config.redis.roleTtlSeconds);
      await this.deps.redisClient.writeRoleTemplate(tenantId, request.ecoId, locale, entry);
    }

    if (response) {
      this.logger.info(
        {
          tenantId,
          ecoId: request.ecoId,
          locale,
          source: this.deps.config.runtime.useSeedData ? 'seed' : 'cloudsql'
        },
        'Role template resolved.'
      );
    }

    return response;
  }

  private buildDemandFromRows(
    _tenantId: string,
    query: MarketDemandQuerystring,
    rows: DemandSeriesRow[]
  ): MarketDemandResponse | null {
    if (!rows.length) {
      return null;
    }

    const reversed = [...rows].reverse();
    const postings = reversed.map((row) => row.postings_count);
    const emaSeries = calculateEma(postings, this.deps.config.calculations.emaSpan);
    const zScores = calculateZScores(postings);

    const points = reversed.map((row, index) => ({
      weekStart: row.week_start,
      postings: row.postings_count,
      ema: emaSeries[index],
      zScore: zScores[index]
    }));

    const latestEma = emaSeries[emaSeries.length - 1] ?? 0;
    const trend = classifyTrend(latestEma, emaSeries[0] ?? latestEma);

    return {
      skillId: query.skillId,
      region: query.region ?? 'BR-SP',
      industry: query.industry,
      points,
      latestEma,
      trend,
      cacheHit: false,
      generatedAt: new Date().toISOString()
    } satisfies MarketDemandResponse;
  }

  async getMarketDemand(
    tenantId: string,
    query: MarketDemandQuerystring,
    options: { bypassCache?: boolean } = {}
  ): Promise<MarketDemandResponse | null> {
    const region = query.region ?? 'BR-SP';
    const windowWeeks = Math.max(this.deps.config.calculations.emaMinPoints, query.windowWeeks ?? 12);

    if (!options.bypassCache && !this.deps.config.redis.disable) {
      const cached = await this.deps.redisClient.readDemand(tenantId, query.skillId, region, query.industry);
      if (cached && cached.expiresAt > this.now()) {
        return {
          ...cached.payload,
          cacheHit: true
        } satisfies MarketDemandResponse;
      }
    }

    let response: MarketDemandResponse | null = null;

    if (this.deps.config.runtime.useSeedData) {
      response = buildSeedMarketDemand({
        skillId: query.skillId,
        region,
        industry: query.industry,
        windowWeeks
      });
    } else {
      const rows = await this.deps.dbClient.fetchDemandSeries(
        tenantId,
        query.skillId,
        region,
        windowWeeks,
        query.industry
      );
      response = this.buildDemandFromRows(tenantId, { ...query, region }, rows);
    }

    if (response && !options.bypassCache && !this.deps.config.redis.disable) {
      const entry = this.buildCacheEntry(response, this.deps.config.redis.demandTtlSeconds);
      await this.deps.redisClient.writeDemand(tenantId, query.skillId, region, entry, query.industry);
    }

    if (response) {
      this.logger.info(
        {
          tenantId,
          skillId: query.skillId,
          region,
          source: this.deps.config.runtime.useSeedData ? 'seed' : 'cloudsql'
        },
        'Market demand resolved.'
      );
    }

    return response;
  }
}
