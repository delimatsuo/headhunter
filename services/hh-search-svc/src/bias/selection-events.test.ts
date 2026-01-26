import { describe, it, expect, vi } from 'vitest';

// Mock @hh/common before importing selection-events module
vi.mock('@hh/common', () => ({
  getLogger: () => ({
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  }),
}));

// Import after mocking
import {
  inferSelectionCompanyTier,
  inferSelectionExperienceBand,
  inferSelectionSpecialty,
  createSelectionEvent,
} from './selection-events';

describe('inferSelectionCompanyTier', () => {
  it('should identify FAANG companies', () => {
    expect(inferSelectionCompanyTier(['Google', 'Startup X'])).toBe('faang');
    expect(inferSelectionCompanyTier(['Meta'])).toBe('faang');
    expect(inferSelectionCompanyTier(['Amazon Web Services'])).toBe('faang');
  });

  it('should identify more FAANG-like companies', () => {
    expect(inferSelectionCompanyTier(['Uber Technologies'])).toBe('faang');
    expect(inferSelectionCompanyTier(['Stripe Inc'])).toBe('faang');
    expect(inferSelectionCompanyTier(['Netflix'])).toBe('faang');
    expect(inferSelectionCompanyTier(['Airbnb'])).toBe('faang');
    expect(inferSelectionCompanyTier(['Coinbase'])).toBe('faang');
  });

  it('should identify enterprise companies', () => {
    expect(inferSelectionCompanyTier(['IBM', 'Small Corp'])).toBe('enterprise');
    expect(inferSelectionCompanyTier(['Cisco Systems'])).toBe('enterprise');
    expect(inferSelectionCompanyTier(['Atlassian'])).toBe('enterprise');
    expect(inferSelectionCompanyTier(['Snowflake'])).toBe('enterprise');
  });

  it('should identify startups', () => {
    expect(inferSelectionCompanyTier(['My Startup', 'Series A Company'])).toBe('startup');
    expect(inferSelectionCompanyTier(['TechStartup Inc', 'Seed Stage'])).toBe('startup');
  });

  it('should return other for unknown companies', () => {
    expect(inferSelectionCompanyTier(['Unknown Corp', 'Random LLC'])).toBe('other');
    expect(inferSelectionCompanyTier([])).toBe('other');
  });

  it('should handle case insensitivity', () => {
    expect(inferSelectionCompanyTier(['GOOGLE'])).toBe('faang');
    expect(inferSelectionCompanyTier(['google llc'])).toBe('faang');
    expect(inferSelectionCompanyTier(['IBM CORPORATION'])).toBe('enterprise');
  });

  it('should prioritize FAANG over enterprise', () => {
    expect(inferSelectionCompanyTier(['Google', 'IBM'])).toBe('faang');
  });
});

describe('inferSelectionExperienceBand', () => {
  it('should categorize experience correctly', () => {
    expect(inferSelectionExperienceBand(0)).toBe('0-3');
    expect(inferSelectionExperienceBand(2)).toBe('0-3');
    expect(inferSelectionExperienceBand(3)).toBe('3-7');
    expect(inferSelectionExperienceBand(5)).toBe('3-7');
    expect(inferSelectionExperienceBand(7)).toBe('7-15');
    expect(inferSelectionExperienceBand(10)).toBe('7-15');
    expect(inferSelectionExperienceBand(15)).toBe('15+');
    expect(inferSelectionExperienceBand(25)).toBe('15+');
  });

  it('should default to 3-7 for undefined', () => {
    expect(inferSelectionExperienceBand(undefined)).toBe('3-7');
  });

  it('should handle edge cases', () => {
    expect(inferSelectionExperienceBand(2.9)).toBe('0-3');
    expect(inferSelectionExperienceBand(6.9)).toBe('3-7');
    expect(inferSelectionExperienceBand(14.9)).toBe('7-15');
  });
});

describe('inferSelectionSpecialty', () => {
  it('should detect frontend from skills', () => {
    expect(inferSelectionSpecialty(['React', 'CSS', 'TypeScript'])).toBe('frontend');
    expect(inferSelectionSpecialty(['Vue', 'HTML', 'JavaScript'])).toBe('frontend');
  });

  it('should detect backend from skills', () => {
    expect(inferSelectionSpecialty(['Python', 'PostgreSQL', 'Go'])).toBe('backend');
    expect(inferSelectionSpecialty(['Java', 'MongoDB', 'NodeJS'])).toBe('backend');
  });

  it('should detect fullstack from mixed skills', () => {
    expect(inferSelectionSpecialty(['React', 'TypeScript', 'Python', 'PostgreSQL'])).toBe('fullstack');
  });

  it('should detect from title first', () => {
    expect(inferSelectionSpecialty(['Python'], 'Frontend Engineer')).toBe('frontend');
    expect(inferSelectionSpecialty(['React'], 'Backend Engineer')).toBe('backend');
    expect(inferSelectionSpecialty([], 'Full-Stack Developer')).toBe('fullstack');
  });

  it('should detect devops', () => {
    expect(inferSelectionSpecialty(['Kubernetes', 'Docker', 'Terraform'])).toBe('devops');
    expect(inferSelectionSpecialty([], 'SRE Engineer')).toBe('devops');
    expect(inferSelectionSpecialty([], 'Platform Engineer')).toBe('devops');
  });

  it('should detect ML', () => {
    expect(inferSelectionSpecialty(['PyTorch', 'TensorFlow', 'scikit-learn'])).toBe('ml');
    expect(inferSelectionSpecialty([], 'Machine Learning Engineer')).toBe('ml');
    expect(inferSelectionSpecialty([], 'AI Research Scientist')).toBe('ml');
  });

  it('should detect mobile', () => {
    expect(inferSelectionSpecialty(['Swift', 'iOS'])).toBe('mobile');
    expect(inferSelectionSpecialty(['Kotlin', 'Android'])).toBe('mobile');
    expect(inferSelectionSpecialty([], 'iOS Developer')).toBe('mobile');
    expect(inferSelectionSpecialty([], 'Android Engineer')).toBe('mobile');
  });

  it('should detect data', () => {
    expect(inferSelectionSpecialty(['Spark', 'Airflow', 'BigQuery'])).toBe('data');
    expect(inferSelectionSpecialty([], 'Data Engineer')).toBe('data');
    expect(inferSelectionSpecialty([], 'Data Scientist')).toBe('data');
  });

  it('should return other for unknown skills', () => {
    expect(inferSelectionSpecialty(['Management', 'Communication'])).toBe('other');
    expect(inferSelectionSpecialty([])).toBe('other');
  });
});

describe('createSelectionEvent', () => {
  it('should create a valid selection event', () => {
    const event = createSelectionEvent(
      'shown',
      'cand-123',
      'search-456',
      'tenant-abc',
      'user-hash-xyz',
      {
        companies: ['Google', 'Startup X'],
        yearsExperience: 8,
        skills: ['Python', 'AWS', 'Docker'],
        title: 'Senior Backend Engineer',
        rank: 5,
        score: 0.85,
      }
    );

    expect(event.eventType).toBe('shown');
    expect(event.candidateId).toBe('cand-123');
    expect(event.searchId).toBe('search-456');
    expect(event.tenantId).toBe('tenant-abc');
    expect(event.dimensions.companyTier).toBe('faang');
    expect(event.dimensions.experienceBand).toBe('7-15');
    expect(event.dimensions.specialty).toBe('backend');
    expect(event.rank).toBe(5);
    expect(event.score).toBe(0.85);
    expect(event.eventId).toBeDefined();
    expect(event.timestamp).toBeInstanceOf(Date);
  });

  it('should handle missing optional fields', () => {
    const event = createSelectionEvent(
      'clicked',
      'cand-789',
      'search-101',
      'tenant-def',
      'user-hash-abc',
      {}
    );

    expect(event.eventType).toBe('clicked');
    expect(event.candidateId).toBe('cand-789');
    expect(event.dimensions.companyTier).toBe('other');
    expect(event.dimensions.experienceBand).toBe('3-7'); // default
    expect(event.dimensions.specialty).toBe('other');
    expect(event.rank).toBeUndefined();
    expect(event.score).toBeUndefined();
  });

  it('should create unique event IDs', () => {
    const event1 = createSelectionEvent('shown', 'c1', 's1', 't1', 'u1', {});
    const event2 = createSelectionEvent('shown', 'c1', 's1', 't1', 'u1', {});

    expect(event1.eventId).not.toBe(event2.eventId);
  });

  it('should handle all event types', () => {
    const eventTypes = ['shown', 'clicked', 'shortlisted', 'contacted', 'interviewed', 'hired'] as const;

    for (const eventType of eventTypes) {
      const event = createSelectionEvent(eventType, 'c1', 's1', 't1', 'u1', {});
      expect(event.eventType).toBe(eventType);
    }
  });
});
