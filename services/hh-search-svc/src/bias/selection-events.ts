/**
 * Selection Event Logging for BIAS-03/BIAS-04
 *
 * Logs candidate selection events (shown, clicked, shortlisted, hired)
 * to enable bias metrics computation using Fairlearn.
 *
 * Events are logged to PostgreSQL for aggregation by the bias_metrics_worker.
 */

import { Pool } from 'pg';
import { getLogger } from '@hh/common';

const logger = getLogger({ module: 'selection-events' });

/**
 * Types of selection events to track.
 * Multiple thresholds enable granular bias analysis.
 */
export type SelectionEventType =
  | 'shown'         // Candidate appeared in search results
  | 'clicked'       // Recruiter clicked to view details
  | 'shortlisted'   // Added to shortlist
  | 'contacted'     // Reached out to candidate
  | 'interviewed'   // Scheduled/completed interview
  | 'hired';        // Made offer/hired

/**
 * Inferred demographic dimensions for bias analysis.
 * We don't collect actual demographics - these are proxy dimensions
 * that can be analyzed without collecting protected information.
 */
export interface InferredDimensions {
  /** Company tier based on prior employers */
  companyTier: 'faang' | 'enterprise' | 'startup' | 'other';

  /** Experience band */
  experienceBand: '0-3' | '3-7' | '7-15' | '15+';

  /** Technical specialty */
  specialty: 'backend' | 'frontend' | 'fullstack' | 'devops' | 'data' | 'ml' | 'mobile' | 'other';
}

/**
 * Selection event to be logged for bias tracking.
 */
export interface SelectionEvent {
  /** Unique event ID */
  eventId: string;

  /** Timestamp of event */
  timestamp: Date;

  /** Candidate ID (for aggregation, not PII) */
  candidateId: string;

  /** Type of selection event */
  eventType: SelectionEventType;

  /** Search/session ID (groups events from same search) */
  searchId: string;

  /** Tenant ID for multi-tenant isolation */
  tenantId: string;

  /** User who performed the action (hashed for privacy) */
  userIdHash: string;

  /** Inferred dimensions for bias grouping */
  dimensions: InferredDimensions;

  /** Candidate's rank in results (for 'shown' events) */
  rank?: number;

  /** Match score at time of event */
  score?: number;
}

/**
 * Infer company tier from company names.
 * Maps to bias analysis dimensions.
 * Note: Named differently from slate-diversity to avoid export conflicts.
 */
export function inferSelectionCompanyTier(companies: string[]): InferredDimensions['companyTier'] {
  const faangLike = [
    'google', 'meta', 'facebook', 'amazon', 'apple', 'microsoft', 'netflix',
    'uber', 'airbnb', 'stripe', 'linkedin', 'twitter', 'salesforce', 'oracle',
    'snap', 'spotify', 'doordash', 'instacart', 'coinbase', 'robinhood'
  ];

  const enterprise = [
    'ibm', 'cisco', 'intel', 'dell', 'hp', 'vmware', 'sap', 'adobe',
    'workday', 'servicenow', 'splunk', 'atlassian', 'twilio', 'datadog',
    'snowflake', 'palantir', 'databricks'
  ];

  const normalized = companies.map(c => c.toLowerCase().replace(/[^a-z]/g, ''));

  for (const company of normalized) {
    if (faangLike.some(f => company.includes(f))) return 'faang';
  }

  for (const company of normalized) {
    if (enterprise.some(e => company.includes(e))) return 'enterprise';
  }

  // Check for startup indicators
  const hasStartupIndicators = companies.some(c =>
    c.toLowerCase().includes('startup') ||
    c.toLowerCase().includes('seed') ||
    c.toLowerCase().includes('series')
  );
  if (hasStartupIndicators) return 'startup';

  return 'other';
}

/**
 * Infer experience band from years of experience.
 * Note: Named differently from slate-diversity to avoid export conflicts.
 */
export function inferSelectionExperienceBand(yearsExperience: number | undefined): InferredDimensions['experienceBand'] {
  if (yearsExperience === undefined) return '3-7'; // Default to mid-range
  if (yearsExperience < 3) return '0-3';
  if (yearsExperience < 7) return '3-7';
  if (yearsExperience < 15) return '7-15';
  return '15+';
}

/**
 * Infer specialty from skills and title.
 * Note: Named differently from slate-diversity to avoid export conflicts.
 */
export function inferSelectionSpecialty(skills: string[], title?: string): InferredDimensions['specialty'] {
  const normalized = skills.map(s => s.toLowerCase());
  const titleLower = (title || '').toLowerCase();

  // Check title first for strong signals
  if (titleLower.includes('frontend') || titleLower.includes('front-end')) return 'frontend';
  if (titleLower.includes('backend') || titleLower.includes('back-end')) return 'backend';
  if (titleLower.includes('fullstack') || titleLower.includes('full-stack')) return 'fullstack';
  if (titleLower.includes('devops') || titleLower.includes('sre') || titleLower.includes('platform')) return 'devops';
  if (titleLower.includes('data engineer') || titleLower.includes('data scientist')) return 'data';
  if (titleLower.includes('ml') || titleLower.includes('machine learning') || titleLower.includes('ai')) return 'ml';
  if (titleLower.includes('mobile') || titleLower.includes('ios') || titleLower.includes('android')) return 'mobile';

  // Fall back to skill analysis
  const frontendSkills = ['react', 'vue', 'angular', 'css', 'html', 'javascript', 'typescript', 'nextjs'];
  const backendSkills = ['java', 'python', 'go', 'rust', 'c++', 'nodejs', 'postgresql', 'mongodb'];
  const devopsSkills = ['kubernetes', 'docker', 'terraform', 'aws', 'gcp', 'azure', 'jenkins', 'ci/cd'];
  const dataSkills = ['sql', 'spark', 'hadoop', 'airflow', 'dbt', 'snowflake', 'bigquery'];
  const mlSkills = ['pytorch', 'tensorflow', 'scikit-learn', 'pandas', 'numpy', 'ml', 'deep learning'];
  const mobileSkills = ['swift', 'kotlin', 'react native', 'flutter', 'ios', 'android'];

  const counts = {
    frontend: normalized.filter(s => frontendSkills.some(f => s.includes(f))).length,
    backend: normalized.filter(s => backendSkills.some(b => s.includes(b))).length,
    devops: normalized.filter(s => devopsSkills.some(d => s.includes(d))).length,
    data: normalized.filter(s => dataSkills.some(d => s.includes(d))).length,
    ml: normalized.filter(s => mlSkills.some(m => s.includes(m))).length,
    mobile: normalized.filter(s => mobileSkills.some(m => s.includes(m))).length,
  };

  const maxCount = Math.max(...Object.values(counts));
  if (maxCount === 0) return 'other';

  // Check for fullstack (both frontend and backend)
  if (counts.frontend >= 2 && counts.backend >= 2) return 'fullstack';

  const maxKey = Object.entries(counts).find(([, v]) => v === maxCount)?.[0];
  return (maxKey as InferredDimensions['specialty']) || 'other';
}

/**
 * Create a selection event from candidate data.
 */
export function createSelectionEvent(
  eventType: SelectionEventType,
  candidateId: string,
  searchId: string,
  tenantId: string,
  userIdHash: string,
  candidateData: {
    companies?: string[];
    yearsExperience?: number;
    skills?: string[];
    title?: string;
    rank?: number;
    score?: number;
  }
): SelectionEvent {
  return {
    eventId: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    timestamp: new Date(),
    candidateId,
    eventType,
    searchId,
    tenantId,
    userIdHash,
    dimensions: {
      companyTier: inferSelectionCompanyTier(candidateData.companies || []),
      experienceBand: inferSelectionExperienceBand(candidateData.yearsExperience),
      specialty: inferSelectionSpecialty(candidateData.skills || [], candidateData.title),
    },
    rank: candidateData.rank,
    score: candidateData.score,
  };
}

/**
 * Log selection event to PostgreSQL for bias metrics.
 */
export async function logSelectionEvent(
  pool: Pool,
  event: SelectionEvent
): Promise<void> {
  const query = `
    INSERT INTO selection_events (
      event_id, timestamp, candidate_id, event_type,
      search_id, tenant_id, user_id_hash,
      company_tier, experience_band, specialty,
      rank, score
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
    ON CONFLICT (event_id) DO NOTHING
  `;

  try {
    await pool.query(query, [
      event.eventId,
      event.timestamp,
      event.candidateId,
      event.eventType,
      event.searchId,
      event.tenantId,
      event.userIdHash,
      event.dimensions.companyTier,
      event.dimensions.experienceBand,
      event.dimensions.specialty,
      event.rank,
      event.score,
    ]);

    logger.debug(
      { eventId: event.eventId, eventType: event.eventType },
      'Selection event logged'
    );
  } catch (error) {
    logger.error(
      { error, eventId: event.eventId },
      'Failed to log selection event'
    );
    // Don't throw - bias logging should not break search
  }
}

/**
 * Batch log multiple selection events (for 'shown' events).
 */
export async function logSelectionEventsBatch(
  pool: Pool,
  events: SelectionEvent[]
): Promise<void> {
  if (events.length === 0) return;

  // Use COPY or multi-value INSERT for efficiency
  const values: unknown[] = [];
  const placeholders: string[] = [];

  events.forEach((event, i) => {
    const offset = i * 12;
    placeholders.push(
      `($${offset + 1}, $${offset + 2}, $${offset + 3}, $${offset + 4}, $${offset + 5}, $${offset + 6}, $${offset + 7}, $${offset + 8}, $${offset + 9}, $${offset + 10}, $${offset + 11}, $${offset + 12})`
    );
    values.push(
      event.eventId,
      event.timestamp,
      event.candidateId,
      event.eventType,
      event.searchId,
      event.tenantId,
      event.userIdHash,
      event.dimensions.companyTier,
      event.dimensions.experienceBand,
      event.dimensions.specialty,
      event.rank,
      event.score
    );
  });

  const query = `
    INSERT INTO selection_events (
      event_id, timestamp, candidate_id, event_type,
      search_id, tenant_id, user_id_hash,
      company_tier, experience_band, specialty,
      rank, score
    ) VALUES ${placeholders.join(', ')}
    ON CONFLICT (event_id) DO NOTHING
  `;

  try {
    await pool.query(query, values);
    logger.info({ count: events.length }, 'Batch selection events logged');
  } catch (error) {
    logger.error({ error, count: events.length }, 'Failed to batch log selection events');
  }
}
