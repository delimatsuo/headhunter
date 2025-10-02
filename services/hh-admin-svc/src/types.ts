import type { AuthenticatedUser, TenantContext } from '@hh/common';

export type RefreshPriority = 'low' | 'normal' | 'high';

export interface RefreshScheduleInput {
  name: string;
  cron: string;
  timezone?: string;
  description?: string;
}

export interface RefreshPostingsRequest {
  tenantId?: string;
  force?: boolean;
  schedule?: RefreshScheduleInput;
}

export interface RefreshProfilesRequest {
  tenantId: string;
  sinceIso?: string;
  priority?: RefreshPriority;
  force?: boolean;
  schedule?: RefreshScheduleInput;
}

export type RefreshJobStatus = 'pending' | 'queued' | 'running' | 'completed' | 'failed' | 'timeout';

export interface RefreshJobIdentifier {
  jobName: string;
  executionName?: string;
}

export interface RefreshJobMetadata {
  requestId: string;
  tenantId: string;
  triggeredAt: string;
  triggeredBy: string;
  priority: RefreshPriority;
  force: boolean;
  scheduleName?: string;
}

export interface RefreshJobResponse {
  status: RefreshJobStatus;
  messageId?: string;
  job?: RefreshJobIdentifier;
  metadata: RefreshJobMetadata;
}

export interface SnapshotTenantLag {
  tenantId: string;
  lagDays: number;
  lastUpdatedAt?: string;
}

export interface SnapshotSection {
  lastUpdatedAt?: string;
  maxLagDays: number;
  staleTenants: SnapshotTenantLag[];
}

export interface JobHealthSnapshot {
  recentExecutions: number;
  recentFailures: number;
  successRatio: number;
  alertState: 'ok' | 'warning' | 'critical';
  lastFailureAt?: string;
}

export interface SnapshotsResponse {
  generatedAt: string;
  postings: SnapshotSection;
  profiles: SnapshotSection;
  jobHealth: JobHealthSnapshot;
}

export interface RefreshContext {
  tenant?: TenantContext;
  user?: AuthenticatedUser;
  requestId: string;
}

export interface RefreshPubSubPayload {
  tenantId: string;
  requestedBy: string;
  requestedAt: string;
  force: boolean;
  scope: 'postings' | 'profiles';
  priority: RefreshPriority;
  sinceIso?: string;
  requestId?: string;
}

export interface RefreshPubSubAttributes extends Record<string, string> {
  requestId: string;
  tenantId: string;
  scope: 'postings' | 'profiles';
  priority: RefreshPriority;
  force: string;
}

export interface ExecutionStatus {
  executionName: string;
  state: 'STATE_UNSPECIFIED' | 'QUEUED' | 'IN_PROGRESS' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED';
  startedAt?: string;
  finishedAt?: string;
  errorMessage?: string;
}

export interface SchedulerJobConfig {
  name: string;
  description?: string;
  cron: string;
  timezone?: string;
  httpTarget: {
    uri: string;
    httpMethod: 'POST' | 'GET';
    oidcServiceAccountEmail: string;
    body?: string;
  };
}

export interface MonitoringSnapshotOptions {
  tenantId?: string;
  lookbackDays: number;
}

export interface MonitoringSnapshot {
  postings: SnapshotSection;
  profiles: SnapshotSection;
  jobHealth: JobHealthSnapshot;
}

export interface TenantSnapshotSourceResult {
  tenantId: string;
  updatedAt: Date | null;
}
