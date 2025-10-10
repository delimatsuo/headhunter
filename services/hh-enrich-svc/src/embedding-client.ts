import { request as httpRequest } from 'node:http';
import { request as httpsRequest } from 'node:https';
import { URL } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import type { Logger } from 'pino';
import { getIdTokenManager, getLogger } from '@hh/common';

import type { EnrichServiceConfig } from './config';
import type { EnrichmentJobRecord } from './types';
import { MetricsExporter, type CircuitState } from './metrics-exporter';

interface EmbeddingErrorInfo {
  category: string;
  retryable: boolean;
  message: string;
}

export interface EmbeddingOperationMetrics {
  success: boolean;
  durationMs: number;
  attempts: number;
  statusCode?: number;
  errorCategory?: string;
  skipped?: boolean;
  skipReason?: string;
}

class CircuitBreaker {
  private state: CircuitState = 'closed';
  private failures = 0;
  private nextAttemptAt = 0;

  constructor(
    private readonly name: string,
    private readonly threshold: number,
    private readonly resetMs: number,
    private readonly logger: Logger,
    private readonly stateCallback?: (state: CircuitState) => void
  ) {}

  canExecute(): boolean {
    if (this.state === 'open') {
      if (Date.now() >= this.nextAttemptAt) {
        this.transition('half-open');
        return true;
      }
      return false;
    }
    return true;
  }

  recordSuccess(): void {
    this.failures = 0;
    this.transition('closed');
  }

  recordFailure(): void {
    this.failures += 1;
    if (this.failures >= this.threshold) {
      this.nextAttemptAt = Date.now() + this.resetMs;
      this.transition('open');
      this.logger.warn({ name: this.name, resetMs: this.resetMs }, 'Embedding circuit breaker opened.');
    } else if (this.state === 'half-open') {
      this.nextAttemptAt = Date.now() + this.resetMs;
      this.transition('open');
    }
  }

  stateName(): CircuitState {
    return this.state;
  }

  private transition(state: CircuitState): void {
    if (state !== this.state) {
      this.state = state;
      this.stateCallback?.(state);
      this.logger.debug({ name: this.name, state }, 'Embedding circuit breaker state changed.');
    }
  }
}

export class EmbeddingClient {
  private readonly logger = getLogger({ module: 'enrich-embed-client' });
  private readonly breaker: CircuitBreaker;
  private readonly metricsExporter?: MetricsExporter;
  private readonly idTokenAudience?: string;

  constructor(
    private readonly config: EnrichServiceConfig,
    private readonly healthCallback?: (healthy: boolean, state: CircuitState) => void,
    metricsExporter?: MetricsExporter
  ) {
    this.metricsExporter = metricsExporter;
    this.idTokenAudience = config.embed.idTokenAudience;
    this.breaker = new CircuitBreaker(
      'embedding-service',
      config.embed.circuitBreakerFailures,
      config.embed.circuitBreakerResetMs,
      this.logger.child({ component: 'embed-circuit' }),
      (state) => {
        this.healthCallback?.(state !== 'open', state);
        this.metricsExporter?.recordEmbedCircuitState(state);
      }
    );
  }

  async upsertEmbedding(
    job: EnrichmentJobRecord,
    candidate: Record<string, unknown>,
    jobLogger?: Logger
  ): Promise<EmbeddingOperationMetrics> {
    if (!this.config.embed.enabled) {
      const skipReason = 'embedding_disabled';
      const metrics: EmbeddingOperationMetrics = { success: false, durationMs: 0, attempts: 0, skipped: true, skipReason };
      this.metricsExporter?.recordEmbedOutcome({
        tenantId: job.tenantId,
        success: false,
        skipped: true,
        durationMs: 0,
        attempts: 0,
        skippedReason: skipReason
      });
      return metrics;
    }

    const text = this.buildSearchableProfile(candidate);
    if (!text || text.trim().length === 0) {
      const message = 'Skipping embedding upsert because searchable profile could not be built.';
      this.logger.warn({ jobId: job.jobId }, message);
      jobLogger?.warn({ jobId: job.jobId }, message);
      const skipReason = 'missing_searchable_data';
      const metrics: EmbeddingOperationMetrics = { success: false, durationMs: 0, attempts: 0, skipped: true, skipReason };
      this.metricsExporter?.recordEmbedOutcome({
        tenantId: job.tenantId,
        success: false,
        skipped: true,
        durationMs: 0,
        attempts: 0,
        skippedReason: skipReason
      });
      return metrics;
    }

    if (!this.breaker.canExecute()) {
      const metrics: EmbeddingOperationMetrics = {
        success: false,
        durationMs: 0,
        attempts: 0,
        errorCategory: 'circuit-open'
      };
      this.logger.error({ jobId: job.jobId }, 'Embedding circuit breaker is open. Skipping upsert.');
      jobLogger?.error({ jobId: job.jobId }, 'Embedding circuit breaker is open. Skipping upsert.');
      this.healthCallback?.(false, this.breaker.stateName());
      this.metricsExporter?.recordEmbedOutcome({
        tenantId: job.tenantId,
        success: false,
        skipped: false,
        durationMs: 0,
        attempts: 0
      });
      return metrics;
    }

    const payload = JSON.stringify({
      entityId: `${job.tenantId}:${job.candidateId}`,
      text,
      metadata: {
        source: 'hh-enrich-svc',
        tenantId: job.tenantId,
        modelVersion: this.config.versioning.modelVersion,
        promptVersion: this.config.versioning.promptVersion
      }
    });

    let attempt = 0;
    let lastError: EmbeddingErrorInfo | null = null;
    const start = Date.now();

    while (attempt <= this.config.embed.retryLimit) {
      const attemptStart = Date.now();
      try {
        const response = await this.sendRequest(job, payload);
        const durationMs = Date.now() - attemptStart;
        this.breaker.recordSuccess();
        this.healthCallback?.(true, this.breaker.stateName());

        const metrics: EmbeddingOperationMetrics = {
          success: true,
          durationMs: Date.now() - start,
          attempts: attempt + 1,
          statusCode: response.statusCode
        };

        this.emitMetric('embedding_success', {
          jobId: job.jobId,
          tenantId: job.tenantId,
          statusCode: response.statusCode,
          durationMs,
          attempts: attempt + 1
        });
        this.metricsExporter?.recordEmbedOutcome({
          tenantId: job.tenantId,
          success: true,
          skipped: false,
          durationMs: metrics.durationMs,
          attempts: metrics.attempts
        });
        return metrics;
      } catch (error) {
        const info = this.normalizeError(error);
        lastError = info;
        this.breaker.recordFailure();
        this.healthCallback?.(false, this.breaker.stateName());

        const durationMs = Date.now() - attemptStart;
        const logPayload = {
          jobId: job.jobId,
          tenantId: job.tenantId,
          attempt: attempt + 1,
          category: info.category,
          retryable: info.retryable,
          durationMs,
          breakerState: this.breaker.stateName()
        };

        if (!info.retryable || attempt === this.config.embed.retryLimit) {
          this.logger.error(logPayload, info.message);
          jobLogger?.error(logPayload, info.message);
          break;
        }

        this.logger.warn(logPayload, info.message);
        jobLogger?.warn(logPayload, info.message);
        attempt += 1;
        const delayMs = this.computeDelay(attempt);
        await delay(delayMs);
      }
    }

    const metrics: EmbeddingOperationMetrics = {
      success: false,
      durationMs: Date.now() - start,
      attempts: attempt + 1,
      errorCategory: lastError?.category
    };

    this.emitMetric('embedding_failure', {
      jobId: job.jobId,
      tenantId: job.tenantId,
      category: lastError?.category,
      attempts: metrics.attempts,
      durationMs: metrics.durationMs
    });

    this.metricsExporter?.recordEmbedOutcome({
      tenantId: job.tenantId,
      success: false,
      skipped: false,
      durationMs: metrics.durationMs,
      attempts: metrics.attempts
    });

    return metrics;
  }

  /**
   * Builds a searchable profile from enriched candidate data.
   * Prioritizes structured enrichment fields over raw resume text.
   */
  private buildSearchableProfile(candidate: Record<string, unknown>): string {
    const parts: string[] = [];

    // Type-safe field extraction
    const getField = (path: string): unknown => {
      const keys = path.split('.');
      let current: any = candidate;
      for (const key of keys) {
        if (current && typeof current === 'object') {
          current = current[key];
        } else {
          return undefined;
        }
      }
      return current;
    };

    const getArray = (path: string): string[] => {
      const value = getField(path);
      return Array.isArray(value) ? value.filter((v) => typeof v === 'string') : [];
    };

    const getString = (path: string): string | undefined => {
      const value = getField(path);
      return typeof value === 'string' ? value : undefined;
    };

    const getNumber = (path: string): number | undefined => {
      const value = getField(path);
      return typeof value === 'number' ? value : undefined;
    };

    // 1. Technical Skills (HIGHEST PRIORITY for technical roles)
    const primarySkills = getArray('technical_assessment.primary_skills');
    const coreCompetencies = getArray('skill_assessment.technical_skills.core_competencies');
    const allSkills = [...new Set([...primarySkills, ...coreCompetencies])];
    if (allSkills.length > 0) {
      parts.push(`Technical Skills: ${allSkills.slice(0, 15).join(', ')}`);
    }

    // 2. Current Role and Title
    const currentRole = getString('experience_analysis.current_role');
    const currentTitle = getString('current_title');
    if (currentRole) {
      parts.push(`Current Role: ${currentRole}`);
    } else if (currentTitle) {
      parts.push(`Current Role: ${currentTitle}`);
    }

    // 3. Experience and Seniority
    const totalYears = getNumber('experience_analysis.total_years');
    const yearsExperience = getNumber('career_trajectory.years_experience');
    const years = totalYears ?? yearsExperience;
    if (years !== undefined) {
      parts.push(`Experience: ${years} years`);
    }

    const seniorityLevel = getString('personal_details.seniority_level');
    const currentLevel = getString('career_trajectory.current_level');
    const seniority = seniorityLevel ?? currentLevel;
    if (seniority) {
      parts.push(`Seniority: ${seniority}`);
    }

    // 4. Domain Expertise
    const domainExpertise = getArray('skill_assessment.domain_expertise');
    if (domainExpertise.length > 0) {
      parts.push(`Domain: ${domainExpertise.slice(0, 5).join(', ')}`);
    }

    // 5. Role Type (IC vs Leadership)
    const hasLeadership = getField('leadership_scope.has_leadership');
    const teamSize = getNumber('leadership_scope.team_size');
    if (hasLeadership === true && teamSize) {
      parts.push(`Leadership: Managing ${teamSize} people`);
    } else if (hasLeadership === false) {
      parts.push(`Role Type: Individual Contributor`);
    }

    // 6. Ideal Roles (from recruiter recommendations)
    const idealRoles = getArray('recruiter_recommendations.ideal_roles');
    const bestFitRoles = getArray('recruiter_insights.best_fit_roles');
    const roles = [...new Set([...idealRoles, ...bestFitRoles])];
    if (roles.length > 0) {
      parts.push(`Best Fit: ${roles.slice(0, 5).join(', ')}`);
    }

    // 7. Executive Summary
    const oneLiner = getString('executive_summary.one_line_pitch');
    if (oneLiner) {
      parts.push(`Summary: ${oneLiner}`);
    }

    // 8. Searchability Keywords
    const keywords = getArray('searchability.keywords');
    const searchTags = getArray('search_optimization.keywords');
    const allKeywords = [...new Set([...keywords, ...searchTags])];
    if (allKeywords.length > 0) {
      parts.push(`Keywords: ${allKeywords.slice(0, 20).join(', ')}`);
    }

    // 9. Company Pedigree
    const companyTier = getString('company_pedigree.company_tier');
    if (companyTier) {
      parts.push(`Company Tier: ${companyTier}`);
    }

    // 10. Fallback: use resume_text if no enriched data available
    if (parts.length === 0) {
      const resumeText = getString('resume_text');
      if (resumeText) {
        this.logger.warn('No enriched data found, falling back to resume_text');
        return resumeText;
      }
    }

    return parts.join('\n');
  }

  private async sendRequest(job: EnrichmentJobRecord, payload: string): Promise<{ statusCode: number }> {
    const url = new URL('/v1/embeddings/upsert', this.config.embed.baseUrl);
    const isHttps = url.protocol === 'https:';
    const requestImpl = isHttps ? httpsRequest : httpRequest;
    const authHeader = await this.resolveAuthHeader();

    return new Promise((resolve, reject) => {
      const req = requestImpl(
        url,
        {
          method: 'POST',
          timeout: this.config.embed.timeoutMs,
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload).toString(),
            [this.config.embed.tenantHeader]: job.tenantId,
            ...(authHeader ? { Authorization: authHeader } : {})
          }
        },
        (res) => {
          const chunks: Buffer[] = [];
          res.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
          res.on('end', () => {
            const status = res.statusCode ?? 0;
            if (status >= 200 && status < 300) {
              resolve({ statusCode: status });
            } else {
              const body = Buffer.concat(chunks).toString('utf8');
              reject(new Error(`Embed service responded with ${status}: ${body}`));
            }
          });
        }
      );

      req.on('error', (error) => {
        reject(error);
      });
      req.on('timeout', () => {
        req.destroy(new Error('Embed request timed out'));
      });

      req.write(payload);
      req.end();
    });
  }

  private normalizeError(error: unknown): EmbeddingErrorInfo {
    const message = error instanceof Error ? error.message : String(error);
    const normalized = message.toLowerCase();

    if (normalized.includes('timed out') || normalized.includes('timeout')) {
      return { category: 'timeout', retryable: true, message } satisfies EmbeddingErrorInfo;
    }
    if (normalized.includes('ecconnrefused') || normalized.includes('econnreset') || normalized.includes('network')) {
      return { category: 'network', retryable: true, message } satisfies EmbeddingErrorInfo;
    }
    if (normalized.includes('5') && normalized.includes('responded')) {
      return { category: 'server', retryable: true, message } satisfies EmbeddingErrorInfo;
    }
    if (normalized.includes('401') || normalized.includes('403')) {
      return { category: 'auth', retryable: false, message } satisfies EmbeddingErrorInfo;
    }
    if (normalized.includes('429')) {
      return { category: 'rate-limit', retryable: true, message } satisfies EmbeddingErrorInfo;
    }
    return { category: 'unknown', retryable: false, message } satisfies EmbeddingErrorInfo;
  }

  private computeDelay(attempt: number): number {
    const base = this.config.embed.retryBaseDelayMs;
    const max = this.config.embed.retryMaxDelayMs;
    const delayMs = Math.min(max, base * 2 ** attempt);
    const jitter = Math.floor(Math.random() * Math.min(delayMs, 250));
    return delayMs + jitter;
  }

  private emitMetric(metric: string, payload: Record<string, unknown>): void {
    this.logger.info({ metric, ...payload }, 'embedding metric');
  }

  private async resolveAuthHeader(): Promise<string | undefined> {
    if (this.config.embed.authToken) {
      return `Bearer ${this.config.embed.authToken}`;
    }

    if (!this.idTokenAudience) {
      return undefined;
    }

    try {
      const token = await getIdTokenManager().getToken(this.idTokenAudience);
      return `Bearer ${token}`;
    } catch (error) {
      this.logger.error({ error }, 'Failed to acquire ID token for embedding service calls.');
      throw error instanceof Error ? error : new Error('Failed to acquire ID token');
    }
  }
}
