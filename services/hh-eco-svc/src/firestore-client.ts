import type { Firestore, Query } from '@google-cloud/firestore';
import type { Logger } from 'pino';

import type { EcoFirestoreConfig } from './config.js';

export interface EcoOccupationDocument {
  eco_id: string;
  org_id: string;
  title: string;
  locale: string;
  country?: string;
  description?: string;
  aliases?: string[];
  industries?: string[];
  salary_insights?: Record<string, unknown>;
}

export interface EcoAliasDocument {
  eco_id: string;
  alias: string;
  locale?: string;
  org_id: string;
}

export interface EcoTemplateDocument {
  eco_id: string;
  org_id: string;
  locale?: string;
  summary?: string;
  required_skills?: string[];
  preferred_skills?: string[];
  years_experience_min?: number;
  years_experience_max?: number;
}

export interface EcoCrosswalkDocument {
  eco_id: string;
  org_id: string;
  cbo?: string[];
  esco?: string[];
  onet?: string[];
}

export interface OccupationSearchDataset {
  occupations: EcoOccupationDocument[];
  aliases: EcoAliasDocument[];
}

export class EcoFirestoreClient {
  constructor(
    private readonly firestore: Firestore,
    private readonly config: EcoFirestoreConfig,
    private readonly logger: Logger
  ) {}

  private occupationCollection() {
    return this.firestore.collection(this.config.occupationCollection);
  }

  private aliasCollection() {
    return this.firestore.collection(this.config.aliasCollection);
  }

  private templateCollection() {
    return this.firestore.collection(this.config.templateCollection);
  }

  private crosswalkCollection() {
    return this.firestore.collection(this.config.crosswalkCollection);
  }

  private tenantQuery<T extends { org_id: string }>(
    collection: ReturnType<Firestore['collection']>,
    tenantId: string
  ): Query<T> {
    return collection.where(this.config.orgIdField, '==', tenantId) as Query<T>;
  }

  async loadSearchDataset(tenantId: string, locale?: string): Promise<OccupationSearchDataset> {
    try {
      let occupationQuery = this.tenantQuery<EcoOccupationDocument>(
        this.occupationCollection(),
        tenantId
      );
      if (locale) {
        occupationQuery = occupationQuery.where(this.config.localeField, '==', locale);
      }
      const [occupationSnapshot, aliasSnapshot] = await Promise.all([
        occupationQuery.get(),
        this.tenantQuery<EcoAliasDocument>(this.aliasCollection(), tenantId).get()
      ]);

      const occupations = occupationSnapshot.docs.map((doc) => doc.data());
      const aliases = aliasSnapshot.docs.map((doc) => doc.data());

      return { occupations, aliases } satisfies OccupationSearchDataset;
    } catch (error) {
      this.logger.error({ error, tenantId, locale }, 'Failed to load ECO search dataset.');
      throw error;
    }
  }

  async getOccupation(tenantId: string, ecoId: string): Promise<EcoOccupationDocument | null> {
    try {
      const snapshot = await this.tenantQuery<EcoOccupationDocument>(
        this.occupationCollection(),
        tenantId
      )
        .where('eco_id', '==', ecoId)
        .limit(1)
        .get();

      if (snapshot.empty) {
        return null;
      }

      return snapshot.docs[0]!.data();
    } catch (error) {
      this.logger.error({ error, tenantId, ecoId }, 'Failed to fetch ECO occupation.');
      throw error;
    }
  }

  async getTemplate(tenantId: string, ecoId: string): Promise<EcoTemplateDocument[]> {
    try {
      const snapshot = await this.tenantQuery<EcoTemplateDocument>(
        this.templateCollection(),
        tenantId
      )
        .where('eco_id', '==', ecoId)
        .limit(5)
        .get();

      return snapshot.docs.map((doc) => doc.data());
    } catch (error) {
      this.logger.error({ error, tenantId, ecoId }, 'Failed to fetch ECO template.');
      throw error;
    }
  }

  async getCrosswalk(tenantId: string, ecoId: string): Promise<EcoCrosswalkDocument | null> {
    try {
      const snapshot = await this.tenantQuery<EcoCrosswalkDocument>(
        this.crosswalkCollection(),
        tenantId
      )
        .where('eco_id', '==', ecoId)
        .limit(1)
        .get();

      if (snapshot.empty) {
        return null;
      }
      return snapshot.docs[0]!.data();
    } catch (error) {
      this.logger.error({ error, tenantId, ecoId }, 'Failed to fetch ECO crosswalk.');
      throw error;
    }
  }

  async healthCheck(): Promise<{ status: 'healthy' | 'degraded' | 'unavailable'; message?: string }> {
    try {
      await this.occupationCollection().limit(1).get();
      return { status: 'healthy' };
    } catch (error) {
      this.logger.error({ error }, 'ECO Firestore health check failed.');
      return {
        status: 'degraded',
        message: error instanceof Error ? error.message : 'Unknown Firestore error'
      };
    }
  }
}
