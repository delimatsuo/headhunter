import type { FastifyReply, FastifyRequest } from 'fastify';

export interface AuthenticatedUser {
  uid: string;
  email?: string;
  orgId?: string;
  displayName?: string;
  claims: Record<string, unknown>;
}

export interface TenantContext {
  id: string;
  name?: string;
  isActive: boolean;
  rawRecord?: Record<string, unknown>;
}

export interface RequestContext {
  requestId: string;
  user?: AuthenticatedUser;
  tenant?: TenantContext;
  auth?: AuthContext;
  trace?: TraceContext;
  gateway?: Record<string, unknown>;
}

export interface ErrorResponse {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export type RouteHandler<Req = FastifyRequest, Res = FastifyReply> = (request: Req, reply: Res) => Promise<unknown>;

export interface AuthContext {
  tokenType: 'firebase' | 'gateway';
  issuer?: string;
  audience?: string;
  clientId?: string;
}

export interface TraceContext {
  traceId?: string;
  spanId?: string;
  sampled?: boolean;
  raw?: string;
  projectId?: string;
  traceResource?: string;
}

declare module 'fastify' {
  interface FastifyRequest {
    requestContext: RequestContext;
    user?: AuthenticatedUser;
    tenant?: TenantContext;
  }
}
