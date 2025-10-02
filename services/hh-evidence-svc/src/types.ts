import type { TenantContext } from '@hh/common';

export type EvidenceSectionKey =
  | 'skills_analysis'
  | 'experience_analysis'
  | 'education_analysis'
  | 'cultural_assessment'
  | 'achievements'
  | 'leadership_assessment'
  | 'compensation_analysis'
  | 'mobility_analysis';

export interface EvidenceSection {
  id: EvidenceSectionKey;
  title: string;
  summary: string;
  highlights: string[];
  score?: number;
  confidence?: number;
  lastUpdated?: string;
}

export interface EvidenceMetadata {
  candidateId: string;
  orgId: string;
  locale?: string;
  version?: string;
  generatedAt?: string;
  redacted?: boolean;
  sectionsAvailable: EvidenceSectionKey[];
  cacheHit: boolean;
}

export interface EvidencePayload {
  sections: Partial<Record<EvidenceSectionKey, EvidenceSection>>;
  metadata: EvidenceMetadata;
}

export interface EvidenceRequestContext {
  tenant: TenantContext;
  candidateId: string;
  includeSections?: EvidenceSectionKey[];
}

export interface EvidenceCacheEntry {
  payload: EvidencePayload;
  storedAt: number;
  expiresAt: number;
}

export interface EvidenceRequestParams {
  candidateId: string;
}

export interface EvidenceQuerystring {
  sections?: string;
}

export interface EvidenceResponse extends EvidencePayload {}

export interface EvidenceHealthStatus {
  redis: {
    status: 'healthy' | 'degraded' | 'disabled' | 'unavailable';
    latencyMs?: number;
    message?: string;
  };
  firestore: {
    status: 'healthy' | 'degraded' | 'unavailable';
    message?: string;
  };
}
