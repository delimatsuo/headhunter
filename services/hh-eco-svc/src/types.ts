import type { TenantContext } from '@hh/common';

export interface OccupationSearchQuery {
  title: string;
  locale?: string;
  country?: string;
  limit?: number;
}

export interface OccupationSearchRequestQuery extends OccupationSearchQuery {
  useCache?: boolean;
}

export interface OccupationSummary {
  ecoId: string;
  title: string;
  locale: string;
  country?: string;
  aliases: string[];
  score: number;
  source: 'title' | 'alias';
}

export interface OccupationSearchResponse {
  results: OccupationSummary[];
  query: OccupationSearchQuery;
  total: number;
  cacheHit: boolean;
}

export interface OccupationTemplate {
  summary: string;
  requiredSkills: string[];
  preferredSkills: string[];
  yearsExperienceMin?: number;
  yearsExperienceMax?: number;
}

export interface OccupationCrosswalk {
  cbo?: string[];
  esco?: string[];
  onet?: string[];
}

export interface OccupationDetail {
  ecoId: string;
  title: string;
  locale: string;
  description?: string;
  aliases: string[];
  crosswalk: OccupationCrosswalk;
  template?: OccupationTemplate;
  industries?: string[];
  salaryInsights?: Record<string, unknown>;
}

export interface OccupationDetailResponse {
  occupation: OccupationDetail;
  cacheHit: boolean;
}

export interface OccupationCacheEntry<T> {
  payload: T;
  storedAt: number;
  expiresAt: number;
}

export interface OccupationSearchPathParams {}

export interface OccupationSearchQuerystring {
  title?: string;
  locale?: string;
  country?: string;
  limit?: number;
  useCache?: string;
}

export interface OccupationDetailParams {
  ecoId: string;
}

export interface OccupationDetailQuerystring {
  locale?: string;
  country?: string;
}

export interface EcoRequestContext extends TenantContext {
  locale?: string;
  country?: string;
}
