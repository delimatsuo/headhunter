import { badRequestError, getLogger } from '@hh/common';

import type { AdminServiceConfig } from './config';
import { AdminJobsClient } from './jobs-client';
import { MonitoringClient } from './monitoring-client';
import { AdminPubSubClient } from './pubsub-client';
import type {
  ExecutionStatus,
  RefreshContext,
  RefreshJobMetadata,
  RefreshJobResponse,
  RefreshJobStatus,
  RefreshPostingsRequest,
  RefreshProfilesRequest,
  RefreshPubSubPayload,
  RefreshScheduleInput,
  SnapshotsResponse
} from './types';

const logger = getLogger({ module: 'admin-service' });

type RefreshScope = 'postings' | 'profiles';

type ExecutionState = 'STATE_UNSPECIFIED' | 'QUEUED' | 'IN_PROGRESS' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED';

export class AdminService {
  constructor(
    private readonly config: AdminServiceConfig,
    private readonly pubsubClient: AdminPubSubClient,
    private readonly jobsClient: AdminJobsClient,
    private readonly monitoringClient: MonitoringClient
  ) {}

  async refreshPostings(context: RefreshContext, request: RefreshPostingsRequest): Promise<RefreshJobResponse> {
    const tenantId = request.tenantId ?? context.tenant?.id;
    if (!tenantId) {
      throw badRequestError('tenantId is required for postings refresh.');
    }

    const force = Boolean(request.force);

    const payload: RefreshPubSubPayload = {
      tenantId,
      requestedBy: context.user?.uid ?? 'system',
      requestedAt: new Date().toISOString(),
      force,
      scope: 'postings',
      priority: this.normalizePriority(this.config.refresh.defaultPriority),
      requestId: context.requestId
    };

    const metadata = this.buildMetadata(context, payload, request.schedule);
    const messageId = await this.pubsubClient.publishPostingsRefresh(payload);
    logger.info({ tenantId, requestId: context.requestId, messageId }, 'Published postings refresh request.');

    if (request.schedule) {
      await this.ensureSchedule('postings', request.schedule, payload);
    }

    const jobName = this.config.jobs.postingsJob;
    const executionName = await this.jobsClient.runJob({ jobName, requestId: context.requestId }).catch((error) => {
      logger.warn({ error, jobName, tenantId }, 'Failed to start postings Cloud Run job.');
      return undefined;
    });

    let status: RefreshJobStatus = 'queued';
    if (executionName) {
      const execution = await this.waitForExecution(executionName).catch((error) => {
        logger.warn({ error, executionName, jobName, tenantId }, 'Error while awaiting postings execution status.');
        return undefined;
      });

      if (execution) {
        status = this.mapExecutionState(execution.state);
        if (execution.errorMessage) {
          logger.warn({ executionName, jobName, errorMessage: execution.errorMessage }, 'Postings refresh execution reported error.');
        }
      } else {
        status = 'running';
      }
    }

    return {
      status,
      messageId,
      job: executionName
        ? {
            jobName,
            executionName
          }
        : undefined,
      metadata
    } satisfies RefreshJobResponse;
  }

  async refreshProfiles(context: RefreshContext, request: RefreshProfilesRequest): Promise<RefreshJobResponse> {
    const tenantId = request.tenantId ?? context.tenant?.id;
    if (!tenantId) {
      throw badRequestError('tenantId is required for profile refresh.');
    }

    const force = Boolean(request.force);

    const sinceIso = request.sinceIso ? this.validateIsoTimestamp(request.sinceIso) : undefined;
    const priority = this.normalizePriority(request.priority ?? this.config.refresh.defaultPriority);

    const payload: RefreshPubSubPayload = {
      tenantId,
      requestedBy: context.user?.uid ?? 'system',
      requestedAt: new Date().toISOString(),
      force,
      scope: 'profiles',
      priority,
      sinceIso,
      requestId: context.requestId
    };

    const metadata = this.buildMetadata(context, payload, request.schedule);
    const messageId = await this.pubsubClient.publishProfilesRefresh(payload);
    logger.info({ tenantId, requestId: context.requestId, messageId }, 'Published profiles refresh request.');

    if (request.schedule) {
      await this.ensureSchedule('profiles', request.schedule, payload);
    }

    const jobName = this.config.jobs.profilesJob;
    const executionName = await this.jobsClient.runJob({ jobName, requestId: context.requestId }).catch((error) => {
      logger.warn({ error, jobName, tenantId }, 'Failed to start profiles Cloud Run job.');
      return undefined;
    });

    let status: RefreshJobStatus = 'queued';
    if (executionName) {
      const execution = await this.waitForExecution(executionName).catch((error) => {
        logger.warn({ error, executionName, jobName, tenantId }, 'Error while awaiting profiles execution status.');
        return undefined;
      });

      if (execution) {
        status = this.mapExecutionState(execution.state);
        if (execution.errorMessage) {
          logger.warn({ executionName, jobName, errorMessage: execution.errorMessage }, 'Profiles refresh execution reported error.');
        }
      } else {
        status = 'running';
      }
    }

    return {
      status,
      messageId,
      job: executionName
        ? {
            jobName,
            executionName
          }
        : undefined,
      metadata
    } satisfies RefreshJobResponse;
  }

  async getSnapshots(context: RefreshContext, tenantId?: string): Promise<SnapshotsResponse> {
    const snapshot = await this.monitoringClient.getSnapshot({
      tenantId: tenantId ?? context.tenant?.id,
      lookbackDays: this.config.monitoring.maxLookbackDays
    });

    return {
      generatedAt: new Date().toISOString(),
      postings: snapshot.postings,
      profiles: snapshot.profiles,
      jobHealth: snapshot.jobHealth
    } satisfies SnapshotsResponse;
  }

  private buildMetadata(context: RefreshContext, payload: RefreshPubSubPayload, schedule?: RefreshScheduleInput): RefreshJobMetadata {
    return {
      requestId: context.requestId,
      tenantId: payload.tenantId,
      triggeredAt: payload.requestedAt,
      triggeredBy: context.user?.uid ?? 'system',
      priority: payload.priority,
      force: payload.force,
      scheduleName: schedule?.name
    } satisfies RefreshJobMetadata;
  }

  private normalizePriority(priority: string | undefined): RefreshPubSubPayload['priority'] {
    switch ((priority ?? 'normal').toLowerCase()) {
      case 'low':
        return 'low';
      case 'high':
        return 'high';
      default:
        return 'normal';
    }
  }

  private async ensureSchedule(scope: RefreshScope, schedule: RefreshScheduleInput, payload: RefreshPubSubPayload): Promise<void> {
    const configuredBaseUrl = this.config.scheduler.targetBaseUrl;
    if (!configuredBaseUrl) {
      logger.warn({ scope }, 'Schedule requested but ADMIN_SCHEDULER_TARGET_BASE_URL is not configured.');
      return;
    }

    const normalizedBase = this.normalizeSchedulerBaseUrl(configuredBaseUrl);
    if (!normalizedBase) {
      logger.warn({ scope, configuredBaseUrl }, 'Unable to determine scheduler target URL; skipping schedule ensure.');
      return;
    }

    const pathSegment = scope === 'postings' ? 'refresh-postings' : 'refresh-profiles';
    const targetUri = `${normalizedBase}/${pathSegment}`;
    const jobId = this.buildScheduleJobId(scope, payload.tenantId, schedule.name);

    await this.jobsClient.ensureSchedule({
      schedule,
      targetUri,
      jobId,
      body: JSON.stringify({
        tenantId: payload.tenantId,
        force: payload.force,
        sinceIso: payload.sinceIso,
        priority: payload.priority
      })
    });
  }

  private normalizeSchedulerBaseUrl(rawBaseUrl: string): string | null {
    try {
      const parsed = new URL(rawBaseUrl);
      const origin = parsed.origin;
      const adminPath = '/v1/admin';
      const trimmedPath = parsed.pathname.replace(/\/+$/, '');

      if (!trimmedPath || trimmedPath === '/') {
        return `${origin}${adminPath}`;
      }

      if (trimmedPath === adminPath) {
        return `${origin}${adminPath}`;
      }

      logger.warn({ configuredPath: trimmedPath }, 'ADMIN_SCHEDULER_TARGET_BASE_URL should point to the service root; ignoring extra path segments.');
      return `${origin}${adminPath}`;
    } catch (error) {
      logger.error({ error, rawBaseUrl }, 'Failed to parse ADMIN_SCHEDULER_TARGET_BASE_URL.');
      return null;
    }
  }

  private buildScheduleJobId(scope: RefreshScope, tenantId: string, scheduleName: string): string {
    const sanitize = (value: string) =>
      value
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');

    const parts = ['hh-admin', scope, tenantId, scheduleName].map(sanitize).filter(Boolean);
    const joined = parts.join('-') || `hh-admin-${scope}`;

    const truncated = joined.length > 512 ? joined.slice(0, 512) : joined;
    const cleaned = truncated.replace(/-+$/, '');
    return cleaned.length > 0 ? cleaned : `hh-admin-${scope}`;
  }

  private validateIsoTimestamp(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      throw badRequestError('sinceIso must be a valid ISO-8601 timestamp.');
    }
    return date.toISOString();
  }

  private async waitForExecution(executionName: string): Promise<ExecutionStatus> {
    const timeoutMs = this.config.refresh.timeoutSeconds * 1000;

    const timeoutPromise = new Promise<ExecutionStatus>((resolve) => {
      setTimeout(
        () =>
          resolve({
            executionName,
            state: 'STATE_UNSPECIFIED',
            errorMessage: 'Timed out while waiting for execution status.'
          }),
        timeoutMs
      );
    });

    const execution = await Promise.race([this.jobsClient.waitForExecution(executionName), timeoutPromise]);
    return execution;
  }

  private mapExecutionState(state: ExecutionState): RefreshJobStatus {
    switch (state) {
      case 'SUCCEEDED':
        return 'completed';
      case 'FAILED':
      case 'CANCELLED':
        return 'failed';
      case 'IN_PROGRESS':
        return 'running';
      case 'QUEUED':
        return 'queued';
      default:
        return 'pending';
    }
  }
}
