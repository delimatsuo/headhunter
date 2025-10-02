import { describe, expect, it, jest } from '@jest/globals';

const metricListTimeSeriesMock = jest.fn();
jest.mock('@google-cloud/monitoring', () => ({
  MetricServiceClient: jest.fn().mockImplementation(() => ({
    projectPath: (projectId: string) => `projects/${projectId}`,
    listTimeSeries: metricListTimeSeriesMock
  }))
}));

import { AdminService } from '../../services/hh-admin-svc/src/admin-service';
import type { AdminServiceConfig } from '../../services/hh-admin-svc/src/config';
import { AdminIamValidator } from '../../services/hh-admin-svc/src/iam-validator';
import { AdminJobsClient } from '../../services/hh-admin-svc/src/jobs-client';
import { MonitoringClient } from '../../services/hh-admin-svc/src/monitoring-client';
import { AdminPubSubClient } from '../../services/hh-admin-svc/src/pubsub-client';
import type { ExecutionStatus, RefreshContext } from '../../services/hh-admin-svc/src/types';

const baseConfig: AdminServiceConfig = {
  base: {} as any,
  pubsub: {
    postingsTopic: 'projects/test/topics/postings',
    profilesTopic: 'projects/test/topics/profiles',
    orderingEnabled: false,
    timeoutMs: 5000,
    retryLimit: 1
  },
  jobs: {
    postingsJob: 'projects/test/locations/us-central1/jobs/msgs-refresh-job',
    profilesJob: 'projects/test/locations/us-central1/jobs/profiles-refresh-job',
    executionTimeoutSeconds: 120,
    pollIntervalMs: 10,
    retryLimit: 1
  },
  scheduler: {
    projectId: 'test',
    location: 'us-central1',
    serviceAccountEmail: 'scheduler@test.iam.gserviceaccount.com',
    targetBaseUrl: 'https://admin.test'
  },
  monitoring: {
    enabled: true,
    projectId: 'test',
    alertThresholdDays: 10,
    maxLookbackDays: 14,
    sqlInstance: 'instances/test',
    sqlDatabase: 'headhunter',
    sqlTable: 'msgs.skill_demand',
    firestoreCollection: 'candidate_profiles'
  },
  iam: {
    globalRole: 'admin.global',
    refreshRole: 'admin.refresh.write',
    monitorRole: 'admin.monitor.read',
    auditLogMetric: 'admin.audit'
  },
  refresh: {
    timeoutSeconds: 5,
    defaultPriority: 'normal',
    allowForce: true
  }
};

const context: RefreshContext = {
  requestId: 'req-123',
  user: {
    uid: 'admin-user',
    claims: { roles: ['admin.refresh.write', 'admin.monitor.read'] }
  } as any,
  tenant: {
    id: 'tenant-1',
    isActive: true
  } as any
};

describe('AdminService', () => {
  it('publishes postings refresh and waits for job completion', async () => {
    const publishMock = jest.fn().mockResolvedValue('msg-1');
    const pubsub = {
      publishPostingsRefresh: publishMock
    } as unknown as AdminPubSubClient;

    const execution: ExecutionStatus = {
      executionName: 'exec-1',
      state: 'SUCCEEDED'
    };

    const jobs = {
      runJob: jest.fn().mockResolvedValue('exec-1'),
      waitForExecution: jest.fn().mockResolvedValue(execution),
      ensureSchedule: jest.fn(),
      healthCheck: jest.fn().mockResolvedValue(true)
    } as unknown as AdminJobsClient;

    const monitoring = {
      getSnapshot: jest.fn().mockResolvedValue({
        postings: { lastUpdatedAt: undefined, maxLagDays: 0, staleTenants: [] },
        profiles: { lastUpdatedAt: undefined, maxLagDays: 0, staleTenants: [] },
        jobHealth: { recentExecutions: 0, recentFailures: 0, successRatio: 1, alertState: 'ok' }
      }),
      healthCheck: jest.fn().mockResolvedValue(true)
    } as unknown as MonitoringClient;

    const service = new AdminService(baseConfig, pubsub, jobs, monitoring);
    const response = await service.refreshPostings(context, { tenantId: 'tenant-1', force: false });

    expect(response.status).toBe('completed');
    expect(response.metadata.tenantId).toBe('tenant-1');
    expect(jobs.runJob).toHaveBeenCalled();
    expect(jobs.waitForExecution).toHaveBeenCalledWith('exec-1');
    expect(publishMock).toHaveBeenCalledTimes(1);
  });

  it('throws when sinceIso is malformed', async () => {
    const service = new AdminService(
      baseConfig,
      {
        publishProfilesRefresh: jest.fn(),
        publishPostingsRefresh: jest.fn()
      } as unknown as AdminPubSubClient,
      {
        runJob: jest.fn(),
        waitForExecution: jest.fn(),
        ensureSchedule: jest.fn(),
        healthCheck: jest.fn().mockResolvedValue(true)
      } as unknown as AdminJobsClient,
      {
        getSnapshot: jest.fn(),
        healthCheck: jest.fn().mockResolvedValue(true)
      } as unknown as MonitoringClient
    );

    await expect(
      service.refreshProfiles(context, { tenantId: 'tenant-1', sinceIso: 'invalid-date' })
    ).rejects.toThrow('sinceIso');
  });

  it('returns snapshot payload with generated timestamp', async () => {
    const monitoring = {
      getSnapshot: jest.fn().mockResolvedValue({
        postings: { lastUpdatedAt: '2024-06-01T00:00:00Z', maxLagDays: 3, staleTenants: [] },
        profiles: { lastUpdatedAt: '2024-06-01T00:00:00Z', maxLagDays: 1, staleTenants: [] },
        jobHealth: { recentExecutions: 10, recentFailures: 0, successRatio: 1, alertState: 'ok' }
      })
    } as unknown as MonitoringClient;

    const service = new AdminService(baseConfig, {} as any, {} as any, monitoring);
    const snapshot = await service.getSnapshots(context);

    expect(snapshot.generatedAt).toBeDefined();
    expect(snapshot.postings.maxLagDays).toBe(3);
    expect(snapshot.jobHealth.recentExecutions).toBe(10);
  });
});

const pubsubTopicMock = () => {
  const publishMessage = jest.fn().mockResolvedValue('msg-1');
  const get = jest.fn().mockResolvedValue([{}]);
  return { publishMessage, get };
};

describe('AdminPubSubClient', () => {
  it('publishes refresh request with scoped attributes', async () => {
    const topic = pubsubTopicMock();
    const topicFactory = jest.fn().mockReturnValue(topic);

    const pubsub = {
      topic: topicFactory
    } as any;

    const client = new AdminPubSubClient(baseConfig.pubsub, pubsub);
    const messageId = await client.publishProfilesRefresh({
      tenantId: 'tenant-1',
      requestedBy: 'admin-user',
      requestedAt: new Date().toISOString(),
      force: false,
      scope: 'profiles',
      priority: 'high',
      sinceIso: '2024-06-01T00:00:00Z',
      requestId: 'req-1'
    });

    expect(messageId).toBe('msg-1');
    const published = topic.publishMessage.mock.calls[0][0];
    expect(JSON.parse(published.data.toString()).scope).toBe('profiles');
    expect(published.attributes.priority).toBe('high');
  });
});

describe('AdminJobsClient', () => {
  it('runs job and ensures scheduler when job missing', async () => {
    const operation = {
      promise: jest.fn().mockResolvedValue([{ name: 'exec-1' }])
    };

    const jobsClient = {
      runJob: jest.fn().mockResolvedValue([operation]),
      getExecution: jest.fn().mockResolvedValue([{ state: 'SUCCEEDED', startTime: { seconds: 1 }, completionTime: { seconds: 2 } }]),
      getJob: jest.fn().mockRejectedValue(Object.assign(new Error('not found'), { code: 5 }))
    } as any;

    const schedulerClient = {
      locationPath: jest.fn().mockImplementation((project: string, location: string) => `projects/${project}/locations/${location}`),
      getJob: jest.fn().mockRejectedValue(Object.assign(new Error('not found'), { code: 5 })),
      createJob: jest.fn().mockResolvedValue({}),
      updateJob: jest.fn().mockResolvedValue({})
    } as any;

    const client = new AdminJobsClient(baseConfig.jobs, baseConfig.scheduler, jobsClient, schedulerClient);
    const executionName = await client.runJob({ jobName: baseConfig.jobs.postingsJob, requestId: 'req-1' });
    expect(executionName).toBe('exec-1');

    const status = await client.waitForExecution('exec-1');
    expect(status.state).toBe('SUCCEEDED');

    await client.ensureSchedule({
      schedule: { name: 'weekly', cron: '0 5 * * 1' },
      targetUri: 'https://admin.test/v1/admin/refresh-postings'
    });

    expect(schedulerClient.createJob).toHaveBeenCalled();
  });
});

describe('MonitoringClient', () => {
  it('computes lag and job health from sources', async () => {
    metricListTimeSeriesMock.mockReset();
    metricListTimeSeriesMock
      .mockResolvedValueOnce([
        [
          {
            points: [
              {
                value: { int64Value: 4 },
                interval: { endTime: { seconds: 1_700_000_000 } }
              }
            ]
          }
        ]
      ])
      .mockResolvedValueOnce([
        [
          {
            points: [
              {
                value: { int64Value: 1 },
                interval: { endTime: { seconds: 1_700_000_100 } }
              }
            ]
          }
        ]
      ]);

    const firestore = {
      collection: jest.fn().mockReturnValue({
        where: jest.fn().mockReturnValue({
          orderBy: jest.fn().mockReturnValue({
            limit: jest.fn().mockReturnValue({
              get: jest.fn().mockResolvedValue({
                docs: [
                  {
                    get: (field: string) => (field === 'updatedAt' ? new Date('2024-06-10T00:00:00Z') : 'tenant-1')
                  }
                ]
              })
            })
          })
        })
      })
    } as any;

    const pool = {
      query: jest.fn().mockResolvedValue({
        rows: [
          { tenant_id: 'tenant-1', last_updated_at: new Date('2024-06-09T00:00:00Z') }
        ]
      }),
      on: jest.fn()
    } as any;

    const monitoring = new MonitoringClient(baseConfig.monitoring, firestore, pool);
    const snapshot = await monitoring.getSnapshot({ tenantId: 'tenant-1', lookbackDays: 7 });

    expect(snapshot.postings.maxLagDays).toBeGreaterThanOrEqual(0);
    expect(snapshot.profiles.staleTenants.length).toBe(0);
    expect(snapshot.jobHealth.recentExecutions).toBe(5);
    expect(snapshot.jobHealth.recentFailures).toBe(1);
  });
});

describe('AdminIamValidator', () => {
  const validator = new AdminIamValidator(baseConfig.iam);

  it('allows refresh when user has refresh role', () => {
    const ctx: RefreshContext = {
      requestId: 'req',
      user: { uid: 'user', claims: { roles: ['admin.refresh.write'] } } as any,
      tenant: { id: 'tenant-1' } as any
    };

    expect(() => validator.ensureRefreshAccess(ctx, 'tenant-1', false)).not.toThrow();
  });

  it('throws when force is requested but disabled', () => {
    const ctx: RefreshContext = {
      requestId: 'req',
      user: { uid: 'user', claims: { roles: [] } } as any,
      tenant: { id: 'tenant-1' } as any
    };

    expect(() => validator.ensureRefreshAccess(ctx, 'tenant-1', true, false)).toThrow();
  });

  it('requires monitor role for snapshots', () => {
    const ctx: RefreshContext = {
      requestId: 'req',
      user: { uid: 'user', claims: { roles: [] } } as any,
      tenant: { id: 'tenant-1' } as any
    };

    expect(() => validator.ensureMonitoringAccess(ctx)).toThrow();
  });
});
