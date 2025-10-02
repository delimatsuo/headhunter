import type { TenantContext } from '@hh/common';

export interface SkillExpandRequestBody {
  skillId: string;
  topK?: number;
  filters?: {
    region?: string;
    industry?: string;
    experience?: string;
  };
  includeRelatedRoles?: boolean;
}

export interface SkillAdjacencyEdge {
  skillId: string;
  label: string;
  score: number;
  support: number;
  recencyDays: number;
  sources: string[];
}

export interface SkillExpandResponse {
  seedSkill: {
    skillId: string;
    label: string;
  };
  adjacent: SkillAdjacencyEdge[];
  cacheHit: boolean;
  generatedAt: string;
  meta: {
    tenantId: string;
    filters?: SkillExpandRequestBody['filters'];
    algorithm: string;
  };
}

export interface RoleTemplateRequestBody {
  ecoId: string;
  locale?: string;
  experienceLevel?: string;
  includeDemand?: boolean;
}

export interface RoleTemplateSkill {
  skillId: string;
  label: string;
  importance: number;
  source: 'required' | 'preferred';
}

export interface RoleTemplateResponse {
  ecoId: string;
  locale: string;
  title: string;
  version: string;
  summary: string;
  requiredSkills: RoleTemplateSkill[];
  preferredSkills: RoleTemplateSkill[];
  yearsExperienceMin?: number;
  yearsExperienceMax?: number;
  demandIndex?: number;
  cacheHit: boolean;
  generatedAt: string;
}

export interface MarketDemandQuerystring {
  skillId: string;
  region?: string;
  industry?: string;
  windowWeeks?: number;
}

export interface DemandPoint {
  weekStart: string;
  postings: number;
  ema: number;
  zScore: number;
}

export interface MarketDemandResponse {
  skillId: string;
  region: string;
  industry?: string;
  points: DemandPoint[];
  trend: 'rising' | 'steady' | 'declining';
  latestEma: number;
  cacheHit: boolean;
  generatedAt: string;
}

export interface MsgsCacheEntry<T> {
  payload: T;
  storedAt: number;
  expiresAt: number;
  version: string;
}

export interface MsgsRequestContext extends TenantContext {
  region?: string;
  industry?: string;
}
