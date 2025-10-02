import { forbiddenError, getLogger, unauthorizedError } from '@hh/common';

import type { AdminIamConfig } from './config';
import type { RefreshContext } from './types';

const logger = getLogger({ module: 'admin-iam-validator' });


export class AdminIamValidator {
  constructor(private readonly config: AdminIamConfig) {}

  ensureRefreshAccess(context: RefreshContext, targetTenantId: string | undefined, forceRequested: boolean, forceAllowed = true): void {
    const { user, tenant } = context;
    if (!user) {
      throw unauthorizedError('Authentication required for admin operations.');
    }

    if (!this.hasRole(user, this.config.refreshRole) && !this.hasRole(user, this.config.globalRole)) {
      this.audit('refresh-denied', context, { targetTenantId, reason: 'missing_role' });
      throw forbiddenError('Missing admin refresh permission.');
    }

    if (!tenant && !this.hasRole(user, this.config.globalRole) && !targetTenantId) {
      this.audit('refresh-denied', context, { reason: 'missing_tenant' });
      throw forbiddenError('Tenant context is required.');
    }

    if (targetTenantId && tenant && tenant.id !== targetTenantId && !this.hasRole(user, this.config.globalRole)) {
      this.audit('refresh-denied', context, { targetTenantId, reason: 'tenant_mismatch' });
      throw forbiddenError('Tenant mismatch for refresh operation.');
    }

    if (forceRequested && !forceAllowed && !this.hasRole(user, this.config.globalRole)) {
      this.audit('refresh-denied', context, { targetTenantId, reason: 'force_disallowed' });
      throw forbiddenError('Force refresh is disabled.');
    }

    this.audit('refresh-granted', context, { targetTenantId, forceRequested });
  }

  ensureMonitoringAccess(context: RefreshContext): void {
    const { user } = context;
    if (!user) {
      throw unauthorizedError('Authentication required for admin operations.');
    }

    if (!this.hasRole(user, this.config.monitorRole) && !this.hasRole(user, this.config.globalRole)) {
      this.audit('monitor-denied', context, { reason: 'missing_role' });
      throw forbiddenError('Missing monitoring permission.');
    }

    this.audit('monitor-granted', context, {});
  }

  private hasRole(user: RefreshContext['user'], role: string): boolean {
    if (!user || !role) {
      return false;
    }

    const claims = user.claims ?? {};
    const roleList = this.getClaimList(claims, 'roles');
    const permissions = this.getClaimList(claims, 'permissions');

    if (roleList.includes(role) || permissions.includes(role)) {
      return true;
    }

    const directClaim = claims[role];
    if (typeof directClaim === 'boolean') {
      return directClaim;
    }

    if (Array.isArray(directClaim)) {
      return directClaim.some((value) => value === true || value === role);
    }

    return false;
  }

  private getClaimList(claims: Record<string, unknown>, key: string): string[] {
    const raw = claims[key];
    if (!raw) {
      return [];
    }

    if (Array.isArray(raw)) {
      return raw.filter((value): value is string => typeof value === 'string').map((value) => value.trim());
    }

    if (typeof raw === 'string') {
      return raw
        .split(',')
        .map((segment) => segment.trim())
        .filter((segment) => segment.length > 0);
    }

    return [];
  }

  private audit(event: string, context: RefreshContext, details: Record<string, unknown>): void {
    logger.info(
      {
        metric: this.config.auditLogMetric,
        event,
        tenantId: context.tenant?.id,
        userId: context.user?.uid,
        email: context.user?.email,
        ...details
      },
      'Admin IAM decision logged.'
    );
  }
}
