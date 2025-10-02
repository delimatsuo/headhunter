import { JobsClient, ExecutionsClient } from '@google-cloud/run';
import { CloudSchedulerClient } from '@google-cloud/scheduler';
import { getLogger } from '@hh/common';

import type { AdminJobsConfig, AdminSchedulerConfig } from './config';
import type { ExecutionStatus, RefreshScheduleInput } from './types';

const logger = getLogger({ module: 'admin-jobs-client' });

interface RunJobOptions {
  jobName: string;
  requestId: string;
}

interface EnsureScheduleOptions {
  schedule: RefreshScheduleInput;
  targetUri: string;
  body?: string;
  jobId: string;
}

export class AdminJobsClient {
  private readonly jobsClient: JobsClient;
  private readonly schedulerClient: CloudSchedulerClient;
  private readonly jobsConfig: AdminJobsConfig;
  private readonly schedulerConfig: AdminSchedulerConfig;
  private readonly executionsClient: ExecutionsClient;

  constructor(
    jobsConfig: AdminJobsConfig,
    schedulerConfig: AdminSchedulerConfig,
    jobsClient?: JobsClient,
    schedulerClient?: CloudSchedulerClient,
    executionsClient?: ExecutionsClient
  ) {
    this.jobsConfig = jobsConfig;
    this.schedulerConfig = schedulerConfig;
    this.jobsClient = jobsClient ?? new JobsClient();
    this.schedulerClient = schedulerClient ?? new CloudSchedulerClient();
    this.executionsClient = executionsClient ?? new ExecutionsClient();
  }

  async runJob(options: RunJobOptions): Promise<string | undefined> {
    try {
      const runJobResponse = (await this.jobsClient.runJob({
        name: options.jobName,
        validateOnly: false
      })) as any;
      const operation = Array.isArray(runJobResponse) ? runJobResponse[0] : runJobResponse;
      const promiseResult =
        operation && typeof operation.promise === 'function'
          ? ((await operation.promise()) as any)
          : [];
      const [execution] = Array.isArray(promiseResult) ? promiseResult : [promiseResult];
      const executionRecord = (execution ?? {}) as any;
      const executionName = typeof executionRecord?.name === 'string' ? executionRecord.name : undefined;
      logger.info({ jobName: options.jobName, executionName, requestId: options.requestId }, 'Triggered Cloud Run job execution.');
      return executionName;
    } catch (error) {
      logger.error({ error, jobName: options.jobName, requestId: options.requestId }, 'Failed to trigger Cloud Run job.');
      throw error;
    }
  }

  async waitForExecution(executionName: string): Promise<ExecutionStatus> {
    const deadline = Date.now() + this.jobsConfig.executionTimeoutSeconds * 1000;

    while (Date.now() < deadline) {
      const status = await this.fetchExecution(executionName);
      if (['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(status.state)) {
        return status;
      }

      await this.sleep(this.jobsConfig.pollIntervalMs);
    }

    return {
      executionName,
      state: 'STATE_UNSPECIFIED',
      errorMessage: 'Execution timed out'
    } satisfies ExecutionStatus;
  }

  async ensureSchedule(options: EnsureScheduleOptions): Promise<void> {
    const parent = this.schedulerClient.locationPath(this.schedulerConfig.projectId, this.schedulerConfig.location);
    const jobName = `${parent}/jobs/${options.jobId}`;
    const body = options.body ? Buffer.from(options.body).toString('base64') : undefined;

    const job = {
      name: jobName,
      description: options.schedule.description ?? 'Admin refresh schedule',
      schedule: options.schedule.cron,
      timeZone: options.schedule.timezone ?? 'Etc/UTC',
      httpTarget: {
        uri: options.targetUri,
        httpMethod: 'POST' as const,
        headers: {
          'Content-Type': 'application/json'
        },
        oidcToken: {
          serviceAccountEmail: this.schedulerConfig.serviceAccountEmail
        },
        body
      }
    };

    try {
      await this.schedulerClient.getJob({ name: jobName });
      await this.schedulerClient.updateJob({
        job,
        updateMask: {
          paths: ['schedule', 'time_zone', 'http_target']
        }
      });
      logger.info({ jobName }, 'Updated existing Cloud Scheduler job.');
    } catch (error: unknown) {
      if (this.isNotFoundError(error)) {
        await this.schedulerClient.createJob({ parent, job });
        logger.info({ jobName }, 'Created Cloud Scheduler job.');
        return;
      }

      logger.error({ error, jobName }, 'Failed to ensure Cloud Scheduler job.');
      throw error;
    }
  }
  async healthCheck(): Promise<boolean> {
    if (!this.jobsConfig.healthCheckEnabled) {
      logger.info('Cloud Run Jobs health check disabled via configuration.');
      return true;
    }
    try {
      await Promise.all([
        this.jobsClient.getJob({ name: this.jobsConfig.postingsJob }),
        this.jobsClient.getJob({ name: this.jobsConfig.profilesJob })
      ]);
      return true;
    } catch (error) {
      logger.warn({ error }, 'Cloud Run Jobs health check failed.');
      return false;
    }
  }


  private async fetchExecution(executionName: string): Promise<ExecutionStatus> {
    const response = (await this.executionsClient.getExecution({ name: executionName })) as any;
    const [execution] = Array.isArray(response) ? response : [response];
    const executionRecord = (execution ?? {}) as any;

    const state = ((executionRecord?.state as any) ?? 'STATE_UNSPECIFIED') as ExecutionStatus['state'];
    const startedAt = this.timestampToIso(executionRecord?.startTime as any);
    const finishedAt = this.timestampToIso((executionRecord?.completionTime ?? executionRecord?.endTime) as any);
    const errorMessage = executionRecord?.error?.message as string | undefined;

    return {
      executionName,
      state,
      startedAt,
      finishedAt,
      errorMessage
    } satisfies ExecutionStatus;
  }

  private timestampToIso(value: any): string | undefined {
    if (!value) {
      return undefined;
    }

    const seconds = typeof value.seconds === 'number' ? value.seconds : undefined;
    const nanos = typeof value.nanos === 'number' ? value.nanos : 0;

    if (seconds === undefined) {
      return undefined;
    }

    const millis = seconds * 1000 + Math.round(nanos / 1_000_000);
    return new Date(millis).toISOString();
  }

  private isNotFoundError(error: unknown): boolean {
    if (typeof error === 'object' && error !== null) {
      const status = (error as { code?: number }).code;
      return status === 5 || status === 404;
    }
    return false;
  }

  private async sleep(ms: number): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve, ms));
  }
}
