import type { Firestore, Query } from '@google-cloud/firestore';
import type { Logger } from 'pino';

import type { EvidenceFirestoreConfig } from './config';
import type { EvidenceSectionKey } from './types';

export interface CandidateEvidenceDocument {
  candidate_id: string;
  org_id: string;
  analysis?: Record<string, unknown>;
  metadata?: {
    locale?: string;
    version?: string;
    generated_at?: string;
    restricted_sections?: EvidenceSectionKey[];
    allowed_sections?: EvidenceSectionKey[];
  };
  personal?: {
    name?: string;
  };
}

export interface CandidateEvidenceResult {
  doc: CandidateEvidenceDocument | null;
  notFound: boolean;
}

export class EvidenceFirestoreClient {
  constructor(
    private readonly firestore: Firestore,
    private readonly config: EvidenceFirestoreConfig,
    private readonly logger: Logger
  ) {}

  private collection() {
    return this.firestore.collection(this.config.candidatesCollection);
  }

  private buildQuery(tenantId: string, candidateId: string): Query {
    const base = this.collection().where(this.config.orgIdField, '==', tenantId);
    let query = base.where('candidate_id', '==', candidateId);

    if (this.config.projections.length > 0) {
      query = query.select(...this.config.projections);
    }

    return query.limit(1);
  }

  async fetchCandidateEvidence(tenantId: string, candidateId: string): Promise<CandidateEvidenceResult> {
    try {
      const query = this.buildQuery(tenantId, candidateId);
      const snapshot = await query.get();

      if (snapshot.empty) {
        return { doc: null, notFound: true } satisfies CandidateEvidenceResult;
      }

      const data = snapshot.docs[0]!.data() as CandidateEvidenceDocument;
      return { doc: data, notFound: false } satisfies CandidateEvidenceResult;
    } catch (error) {
      this.logger.error({ error, tenantId, candidateId }, 'Failed to fetch candidate evidence from Firestore.');
      throw error;
    }
  }

  async healthCheck(): Promise<{ status: 'healthy' | 'degraded' | 'unavailable'; message?: string }> {
    try {
      await this.collection().limit(1).get();
      return { status: 'healthy' };
    } catch (error) {
      this.logger.error({ error }, 'Evidence Firestore health check failed.');
      return {
        status: 'degraded',
        message: error instanceof Error ? error.message : 'Unknown Firestore error'
      };
    }
  }
}
