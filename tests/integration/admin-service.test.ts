import { afterAll, beforeAll, beforeEach, describe, expect, it, jest } from '@jest/globals';

import { buildServer } from '@hh/common';

import type { AdminServiceConfig } from '../../services/hh-admin-svc/src/config';
import { AdminService } from '../../services/hh-admin-svc/src/admin-service';
import { AdminIamValidator } from '../../services/hh-admin-svc/src/iam-validator';
import { registerRoutes } from '../../services/hh-admin-svc/src/routes';
import type { RefreshContext } from '../../services/hh-admin-svc/src/types';

const config: AdminServiceConfig = {
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
    executionTimeoutSeconds: 60,
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
    enabled: false,
    projectId: 'test',
    alertThresholdDays: 10,
    maxLookbackDays: 14
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

describe('Admin service routes', () => {
  let server: Awaited<ReturnType<typeof buildServer>>;
  const pubsub = {
    publishPostingsRefresh: jest.fn().mockResolvedValue('msg-1'),
    publishProfilesRefresh: jest.fn().mockResolvedValue('msg-2'),
    healthCheck: jest.fn().mockResolvedValue(true)
  };
  const jobs = {
    runJob: jest.fn().mockResolvedValue('exec-1'),
    waitForExecution: jest.fn().mockResolvedValue({ executionName: 'exec-1', state: 'SUCCEEDED' }),
    ensureSchedule: jest.fn().mockResolvedValue(undefined),
    healthCheck: jest.fn().mockResolvedValue(true)
  };
  const monitoring = {
    getSnapshot: jest.fn().mockResolvedValue({
      postings: { lastUpdatedAt: '2024-06-01T00:00:00Z', maxLagDays: 2, staleTenants: [] },
      profiles: { lastUpdatedAt: '2024-06-01T00:00:00Z', maxLagDays: 1, staleTenants: [] },
      jobHealth: { recentExecutions: 5, recentFailures: 0, successRatio: 1, alertState: 'ok' }
    }),
    healthCheck: jest.fn().mockResolvedValue(true)
  };

  beforeAll(async () => {
    const service = new AdminService(config, pubsub as any, jobs as any, monitoring as any);
    const iam = new AdminIamValidator(config.iam);

    server = await buildServer();
    server.addHook('onRequest', (request, _reply, done) => {
      const ctx: RefreshContext = {
        requestId: request.id,
        user: {
          uid: 'admin-user',
          claims: { roles: ['admin.refresh.write', 'admin.monitor.read'] }
        } as any,
        tenant: {
          id: 'tenant-1',
          isActive: true
        } as any
      };
      request.user = ctx.user;
      request.tenant = ctx.tenant;
      request.requestContext = ctx as any;
      done();
    });

    await registerRoutes(server, {
      config,
      service,
      pubsub: pubsub as any,
      jobs: jobs as any,
      monitoring: monitoring as any,
      iam
    });
  });

  beforeEach(() => {
    jest.clearAllMocks();
    pubsub.publishPostingsRefresh.mockResolvedValue('msg-1');
    pubsub.publishProfilesRefresh.mockResolvedValue('msg-2');
    jobs.runJob.mockResolvedValue('exec-1');
    jobs.waitForExecution.mockResolvedValue({ executionName: 'exec-1', state: 'SUCCEEDED' });
  });

  afterAll(async () => {
    await server.close();
  });

  it('queues postings refresh and returns metadata', async () => {
    const response = await server.inject({
      method: 'POST',
      url: '/v1/admin/refresh-postings',
      payload: { force: false }
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.status).toBe('completed');
    expect(pubsub.publishPostingsRefresh).toHaveBeenCalled();
    expect(jobs.runJob).toHaveBeenCalledWith({ jobName: config.jobs.postingsJob, requestId: expect.any(String) });
  });

  it('schedules profile refresh when schedule provided', async () => {
    const response = await server.inject({
      method: 'POST',
      url: '/v1/admin/refresh-profiles',
      payload: {
        tenantId: 'tenant-1',
        sinceIso: '2024-06-01T00:00:00Z',
        schedule: {
          name: 'nightly-profiles',
          cron: '0 3 * * *'
        }
      }
    });

    expect(response.statusCode).toBe(200);
    expect(jobs.ensureSchedule).toHaveBeenCalled();
    expect(pubsub.publishProfilesRefresh).toHaveBeenCalled();
  });

  it('returns snapshot payload', async () => {
    const response = await server.inject({
      method: 'GET',
      url: '/v1/admin/snapshots'
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.postings.maxLagDays).toBe(2);
    expect(monitoring.getSnapshot).toHaveBeenCalled();
  });
});
