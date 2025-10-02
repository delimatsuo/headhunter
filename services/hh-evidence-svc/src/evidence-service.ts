import { getLogger } from '@hh/common';
import { pick } from 'lodash';
import type { Logger } from 'pino';

import type { EvidenceServiceConfig } from './config';
import type {
  EvidenceCacheEntry,
  EvidencePayload,
  EvidenceRequestContext,
  EvidenceSectionKey
} from './types';
import { EvidenceFirestoreClient } from './firestore-client';
import { EvidenceRedisClient } from './redis-client';

interface EvidenceServiceDeps {
  config: EvidenceServiceConfig;
  firestoreClient: EvidenceFirestoreClient;
  redisClient: EvidenceRedisClient;
  logger?: Logger;
}

export class EvidenceService {
  private readonly logger: Logger;
  private readonly revalidateDebounceMs = 5000;
  private readonly revalidationInflight = new Map<string, Promise<void>>();
  private readonly revalidationLastAttempt = new Map<string, number>();

  constructor(private readonly deps: EvidenceServiceDeps) {
    this.logger = deps.logger ?? getLogger({ module: 'evidence-service' });
  }

  private now(): number {
    return Date.now();
  }

  private cacheKey(context: EvidenceRequestContext): string {
    return `${context.tenant.id}:${context.candidateId}`;
  }

  private normalizeSections(
    analysis: Record<string, unknown> | undefined,
    allowed: EvidenceSectionKey[],
    restrictions: Set<EvidenceSectionKey>,
    include?: EvidenceSectionKey[]
  ): Partial<Record<EvidenceSectionKey, EvidencePayload['sections'][EvidenceSectionKey]>> {
    if (!analysis) {
      return {};
    }

    const result: Partial<Record<EvidenceSectionKey, EvidencePayload['sections'][EvidenceSectionKey]>> = {};
    const requested = include && include.length > 0 ? new Set(include) : null;

    for (const sectionKey of allowed) {
      if (requested && !requested.has(sectionKey)) {
        continue;
      }

      if (restrictions.has(sectionKey)) {
        continue;
      }

      const raw = analysis[sectionKey];
      if (!raw || typeof raw !== 'object') {
        continue;
      }

      const record = raw as Record<string, unknown>;
      const highlights = Array.isArray(record.highlights)
        ? (record.highlights.filter((item): item is string => typeof item === 'string') ?? [])
        : [];

      result[sectionKey] = {
        id: sectionKey,
        title:
          typeof record.title === 'string' && record.title.trim().length > 0
            ? (record.title as string)
            : this.computeTitle(sectionKey),
        summary: typeof record.summary === 'string' ? (record.summary as string) : '',
        highlights,
        score: typeof record.score === 'number' ? (record.score as number) : undefined,
        confidence: typeof record.confidence === 'number' ? (record.confidence as number) : undefined,
        lastUpdated: typeof record.last_updated === 'string' ? (record.last_updated as string) : undefined
      };
    }

    return result;
  }

  private computeTitle(section: EvidenceSectionKey): string {
    switch (section) {
      case 'skills_analysis':
        return 'Skills Analysis';
      case 'experience_analysis':
        return 'Experience Analysis';
      case 'education_analysis':
        return 'Education Analysis';
      case 'cultural_assessment':
        return 'Cultural Assessment';
      case 'achievements':
        return 'Key Achievements';
      case 'leadership_assessment':
        return 'Leadership Assessment';
      case 'compensation_analysis':
        return 'Compensation Analysis';
      case 'mobility_analysis':
        return 'Mobility Analysis';
      default:
        return section;
    }
  }

  private enforceLimits(payload: EvidencePayload): EvidencePayload {
    const { runtime } = this.deps.config;
    const allowedSections = runtime.maxSections;
    const sectionKeys = Object.keys(payload.sections) as EvidenceSectionKey[];

    if (sectionKeys.length > allowedSections) {
      const trimmedKeys = sectionKeys.slice(0, allowedSections);
      payload.sections = pick(payload.sections, trimmedKeys) as EvidencePayload['sections'];
      payload.metadata.sectionsAvailable = trimmedKeys;
    } else {
      payload.metadata.sectionsAvailable = sectionKeys;
    }

    const sizeInKb = Buffer.byteLength(JSON.stringify(payload), 'utf8') / 1024;
    if (sizeInKb > runtime.maxResponseKb) {
      this.logger.warn(
        {
          sizeInKb,
          maxResponseKb: runtime.maxResponseKb,
          candidateId: payload.metadata.candidateId
        },
        'Evidence payload exceeded maxResponseKb. Sections trimmed.'
      );
      const trimmedKeys = sectionKeys.slice(
        0,
        Math.max(1, Math.floor((runtime.maxResponseKb / sizeInKb) * sectionKeys.length))
      );
      payload.sections = pick(payload.sections, trimmedKeys) as EvidencePayload['sections'];
      payload.metadata.sectionsAvailable = trimmedKeys;
    }

    return payload;
  }

  private async fetchAndStageEvidence(context: EvidenceRequestContext): Promise<EvidencePayload> {
    const { firestoreClient, redisClient, config } = this.deps;
    const start = this.now();
    const tenantId = context.tenant.id;
    const candidateId = context.candidateId;

    const result = await firestoreClient.fetchCandidateEvidence(tenantId, candidateId);
    if (!result.doc) {
      const error = new Error('Candidate evidence not found.');
      this.logger.warn({ tenantId, candidateId }, 'Candidate evidence not found.');
      throw error;
    }

    const allowedSections = config.runtime.allowedSections.filter(
      (section): section is EvidenceSectionKey => typeof section === 'string'
    );

    const restrictions = new Set<EvidenceSectionKey>();
    const metadata = result.doc.metadata ?? {};

    if (Array.isArray(metadata.restricted_sections)) {
      for (const value of metadata.restricted_sections) {
        if (typeof value === 'string') {
          restrictions.add(value as EvidenceSectionKey);
        }
      }
    }

    if (config.runtime.redactRestricted && Array.isArray(metadata.allowed_sections)) {
      const allowList = new Set(metadata.allowed_sections);
      for (const section of allowedSections) {
        if (!allowList.has(section)) {
          restrictions.add(section);
        }
      }
    }

    const sections = this.normalizeSections(
      result.doc.analysis as Record<string, unknown> | undefined,
      allowedSections,
      restrictions,
      context.includeSections
    );

    const payload: EvidencePayload = {
      sections,
      metadata: {
        candidateId,
        orgId: tenantId,
        locale: metadata.locale ?? config.runtime.defaultLocale,
        version: metadata.version,
        generatedAt: metadata.generated_at,
        redacted: restrictions.size > 0,
        sectionsAvailable: Object.keys(sections) as EvidenceSectionKey[],
        cacheHit: false
      }
    } satisfies EvidencePayload;

    const sanitized = this.enforceLimits(payload);
    const now = this.now();
    const entry: EvidenceCacheEntry = {
      payload: sanitized,
      storedAt: now,
      expiresAt: now + this.deps.config.redis.ttlSeconds * 1000
    } satisfies EvidenceCacheEntry;

    await redisClient.stage(tenantId, candidateId, entry);
    this.logger.debug(
      {
        tenantId,
        candidateId,
        durationMs: this.now() - start
      },
      'Candidate evidence retrieved from Firestore.'
    );

    return sanitized;
  }

  private scheduleRevalidation(context: EvidenceRequestContext): void {
    if (this.deps.config.redis.disable) {
      return;
    }

    const key = this.cacheKey(context);
    const now = this.now();
    const lastAttempt = this.revalidationLastAttempt.get(key);
    if (lastAttempt && now - lastAttempt < this.revalidateDebounceMs) {
      return;
    }

    if (this.revalidationInflight.has(key)) {
      return;
    }

    const tenantId = context.tenant.id;
    const candidateId = context.candidateId;
    const refreshContext: EvidenceRequestContext = { ...context, includeSections: undefined };

    this.revalidationLastAttempt.set(key, now);
    this.logger.info(
      { tenantId, candidateId, revalidate: true },
      'Evidence cache stale entry scheduled for refresh.'
    );

    const refreshPromise = this.fetchAndStageEvidence(refreshContext)
      .then(() => undefined)
      .catch((error) => {
        this.logger.warn({ error, tenantId, candidateId }, 'Evidence cache revalidation failed.');
      })
      .finally(() => {
        this.revalidationInflight.delete(key);
        this.revalidationLastAttempt.set(key, this.now());
      });

    this.revalidationInflight.set(key, refreshPromise);
  }

  async getEvidence(context: EvidenceRequestContext): Promise<EvidencePayload> {
    const { redisClient } = this.deps;
    const includeSections = context.includeSections ?? [];

    const cacheEntry = await redisClient.read(context.tenant.id, context.candidateId);
    if (cacheEntry) {
      const ttlRemaining = cacheEntry.expiresAt - this.now();
      const payload: EvidencePayload = {
        ...cacheEntry.payload,
        metadata: {
          ...cacheEntry.payload.metadata,
          cacheHit: ttlRemaining > 0
        }
      };

      if (ttlRemaining <= 0) {
        this.scheduleRevalidation(context);
      }

      if (includeSections.length === 0) {
        return payload;
      }

      const filteredSections = pick(payload.sections, includeSections) as EvidencePayload['sections'];
      return {
        ...payload,
        sections: filteredSections,
        metadata: {
          ...payload.metadata,
          sectionsAvailable: Object.keys(filteredSections) as EvidenceSectionKey[]
        }
      } satisfies EvidencePayload;
    }

    return this.fetchAndStageEvidence(context);
  }
}
