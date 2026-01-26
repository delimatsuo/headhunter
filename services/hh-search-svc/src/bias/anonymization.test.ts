import { describe, it, expect, vi } from 'vitest';
import type { HybridSearchResultItem, HybridSearchResponse } from '../types';
import type { AnonymizedSearchResponse } from './types';

// Mock @hh/common before importing anonymization module
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
  anonymizeCandidate,
  anonymizeSearchResponse,
  isAnonymizedResponse,
} from './anonymization';

describe('anonymizeCandidate', () => {
  const mockCandidate: HybridSearchResultItem = {
    candidateId: 'cand-123',
    score: 0.85,
    vectorScore: 0.8,
    textScore: 0.7,
    rrfScore: 0.82,
    confidence: 0.9,
    fullName: 'John Smith',
    title: 'Senior Engineer at Google',
    location: 'San Francisco, CA',
    country: 'USA',
    headline: 'Staff Engineer | Ex-Google | Stanford MBA',
    skills: [
      { name: 'Python', weight: 1.0 },
      { name: 'AWS', weight: 0.8 },
    ],
    industries: ['Technology', 'Finance'],
    yearsExperience: 10,
    matchReasons: [
      'Strong skill match for Python',
      'Worked at Google which aligns with target',
      'Based in San Francisco',
    ],
    signalScores: {
      vectorSimilarity: 0.8,
      levelMatch: 0.9,
      specialtyMatch: 0.85,
      techStackMatch: 0.9,
      functionMatch: 0.8,
      trajectoryFit: 0.75,
      companyPedigree: 0.95,
      skillsExactMatch: 0.9,
      skillsInferred: 0.7,
      seniorityAlignment: 0.85,
      recencyBoost: 0.8,
      companyRelevance: 0.9,
    },
    weightsApplied: {
      vectorSimilarity: 0.12,
      levelMatch: 0.1,
      specialtyMatch: 0.1,
      techStackMatch: 0.1,
      functionMatch: 0.1,
      trajectoryFit: 0.1,
      companyPedigree: 0.1,
    },
    metadata: {
      educationInstitutions: ['Stanford University'],
      graduationYear: 2010,
    },
    mlTrajectory: {
      nextRole: 'Staff Engineer',
      nextRoleConfidence: 0.78,
      tenureMonths: { min: 18, max: 24 },
      hireability: 85,
      lowConfidence: false,
    },
  };

  it('should strip PII fields (name, title, location, headline)', () => {
    const anonymized = anonymizeCandidate(mockCandidate);

    expect(anonymized.anonymized).toBe(true);
    expect(anonymized).not.toHaveProperty('fullName');
    expect(anonymized).not.toHaveProperty('title');
    expect(anonymized).not.toHaveProperty('location');
    expect(anonymized).not.toHaveProperty('country');
    expect(anonymized).not.toHaveProperty('headline');
    expect(anonymized).not.toHaveProperty('metadata');
  });

  it('should preserve candidateId for tracking', () => {
    const anonymized = anonymizeCandidate(mockCandidate);
    expect(anonymized.candidateId).toBe('cand-123');
  });

  it('should preserve scores and confidence', () => {
    const anonymized = anonymizeCandidate(mockCandidate);
    expect(anonymized.score).toBe(0.85);
    expect(anonymized.vectorScore).toBe(0.8);
    expect(anonymized.textScore).toBe(0.7);
    expect(anonymized.rrfScore).toBe(0.82);
    expect(anonymized.confidence).toBe(0.9);
  });

  it('should preserve job-relevant data (skills, experience, industries)', () => {
    const anonymized = anonymizeCandidate(mockCandidate);
    expect(anonymized.yearsExperience).toBe(10);
    expect(anonymized.skills).toHaveLength(2);
    expect(anonymized.skills![0].name).toBe('Python');
    expect(anonymized.industries).toEqual(['Technology', 'Finance']);
  });

  it('should preserve ML trajectory predictions', () => {
    const anonymized = anonymizeCandidate(mockCandidate);
    expect(anonymized.mlTrajectory).toBeDefined();
    expect(anonymized.mlTrajectory!.nextRole).toBe('Staff Engineer');
    expect(anonymized.mlTrajectory!.hireability).toBe(85);
  });

  it('should exclude companyPedigree from signal scores', () => {
    const anonymized = anonymizeCandidate(mockCandidate);
    expect(anonymized.signalScores).toBeDefined();
    expect(anonymized.signalScores!.vectorSimilarity).toBe(0.8);
    expect(anonymized.signalScores!.levelMatch).toBe(0.9);
    expect(anonymized.signalScores).not.toHaveProperty('companyPedigree');
    expect(anonymized.signalScores).not.toHaveProperty('companyRelevance');
  });

  it('should exclude companyPedigree from weightsApplied', () => {
    const anonymized = anonymizeCandidate(mockCandidate);
    expect(anonymized.weightsApplied).toBeDefined();
    expect(anonymized.weightsApplied!.vectorSimilarity).toBe(0.12);
    expect(anonymized.weightsApplied).not.toHaveProperty('companyPedigree');
    expect(anonymized.weightsApplied).not.toHaveProperty('companyRelevance');
  });

  it('should filter match reasons that mention companies or locations', () => {
    const anonymized = anonymizeCandidate(mockCandidate);
    expect(anonymized.matchReasons).toHaveLength(1);
    expect(anonymized.matchReasons[0]).toBe('Strong skill match for Python');
  });

  it('should handle candidate without optional fields', () => {
    const minimalCandidate: HybridSearchResultItem = {
      candidateId: 'cand-minimal',
      score: 0.5,
      vectorScore: 0.5,
      textScore: 0.5,
      confidence: 0.5,
      matchReasons: [],
    };

    const anonymized = anonymizeCandidate(minimalCandidate);
    expect(anonymized.candidateId).toBe('cand-minimal');
    expect(anonymized.anonymized).toBe(true);
    expect(anonymized.skills).toBeUndefined();
    expect(anonymized.signalScores).toBeUndefined();
  });

  it('should preserve Phase 7 signal scores when present', () => {
    const anonymized = anonymizeCandidate(mockCandidate);
    expect(anonymized.signalScores!.skillsExactMatch).toBe(0.9);
    expect(anonymized.signalScores!.skillsInferred).toBe(0.7);
    expect(anonymized.signalScores!.seniorityAlignment).toBe(0.85);
    expect(anonymized.signalScores!.recencyBoost).toBe(0.8);
  });

  it('should not include Phase 7 signals when not present', () => {
    const candidateWithoutPhase7: HybridSearchResultItem = {
      candidateId: 'cand-no-phase7',
      score: 0.7,
      vectorScore: 0.7,
      textScore: 0.6,
      confidence: 0.8,
      matchReasons: ['Good match'],
      signalScores: {
        vectorSimilarity: 0.7,
        levelMatch: 0.8,
        specialtyMatch: 0.75,
        techStackMatch: 0.8,
        functionMatch: 0.7,
        trajectoryFit: 0.6,
        companyPedigree: 0.5,
      },
    };

    const anonymized = anonymizeCandidate(candidateWithoutPhase7);
    expect(anonymized.signalScores).toBeDefined();
    expect(anonymized.signalScores!.skillsExactMatch).toBeUndefined();
    expect(anonymized.signalScores!.skillsInferred).toBeUndefined();
  });
});

describe('anonymizeSearchResponse', () => {
  const mockResponse: HybridSearchResponse = {
    results: [
      {
        candidateId: 'cand-1',
        score: 0.9,
        vectorScore: 0.85,
        textScore: 0.8,
        confidence: 0.95,
        fullName: 'Alice Johnson',
        matchReasons: ['Strong Python skills'],
      },
      {
        candidateId: 'cand-2',
        score: 0.8,
        vectorScore: 0.75,
        textScore: 0.7,
        confidence: 0.85,
        fullName: 'Bob Williams',
        matchReasons: ['AWS expertise'],
      },
    ],
    total: 2,
    cacheHit: false,
    requestId: 'req-123',
    timings: {
      totalMs: 150,
      retrievalMs: 100,
    },
    metadata: {
      searchVersion: '2.0',
    },
    debug: {
      query: 'Python developer',
    },
  };

  it('should anonymize all candidates in response', () => {
    const anonymized = anonymizeSearchResponse(mockResponse);

    expect(anonymized.results).toHaveLength(2);
    expect(anonymized.results[0].anonymized).toBe(true);
    expect(anonymized.results[1].anonymized).toBe(true);
    expect(anonymized.results[0]).not.toHaveProperty('fullName');
    expect(anonymized.results[1]).not.toHaveProperty('fullName');
  });

  it('should not include debug information in anonymized response', () => {
    const anonymized = anonymizeSearchResponse(mockResponse);
    expect(anonymized).not.toHaveProperty('debug');
  });

  it('should preserve response-level fields', () => {
    const anonymized = anonymizeSearchResponse(mockResponse);
    expect(anonymized.total).toBe(2);
    expect(anonymized.cacheHit).toBe(false);
    expect(anonymized.requestId).toBe('req-123');
    expect(anonymized.timings.totalMs).toBe(150);
  });

  it('should mark response as anonymized in metadata', () => {
    const anonymized = anonymizeSearchResponse(mockResponse);
    expect(anonymized.metadata.anonymized).toBe(true);
    expect(anonymized.metadata.anonymizedAt).toBeDefined();
    expect(typeof anonymized.metadata.anonymizedAt).toBe('string');
  });

  it('should handle empty results array', () => {
    const emptyResponse: HybridSearchResponse = {
      results: [],
      total: 0,
      cacheHit: false,
      requestId: 'req-empty',
      timings: { totalMs: 10 },
    };

    const anonymized = anonymizeSearchResponse(emptyResponse);
    expect(anonymized.results).toHaveLength(0);
    expect(anonymized.metadata.anonymized).toBe(true);
  });
});

describe('isAnonymizedResponse', () => {
  it('should return true for anonymized response', () => {
    const response: AnonymizedSearchResponse = {
      results: [],
      total: 0,
      cacheHit: false,
      requestId: 'req-123',
      timings: { totalMs: 10 },
      metadata: { anonymized: true, anonymizedAt: '2024-01-01T00:00:00Z' },
    };

    expect(isAnonymizedResponse(response)).toBe(true);
  });

  it('should return false for non-anonymized response', () => {
    const response: HybridSearchResponse = {
      results: [],
      total: 0,
      cacheHit: false,
      requestId: 'req-123',
      timings: { totalMs: 10 },
    };

    expect(isAnonymizedResponse(response)).toBe(false);
  });

  it('should return false when metadata exists but anonymized is false', () => {
    const response: HybridSearchResponse = {
      results: [],
      total: 0,
      cacheHit: false,
      requestId: 'req-123',
      timings: { totalMs: 10 },
      metadata: { anonymized: false },
    };

    expect(isAnonymizedResponse(response)).toBe(false);
  });
});

describe('match reason anonymization', () => {
  it('should filter reasons mentioning specific companies', () => {
    const candidate: HybridSearchResultItem = {
      candidateId: 'cand-1',
      score: 0.8,
      vectorScore: 0.8,
      textScore: 0.7,
      confidence: 0.85,
      matchReasons: [
        'Experience at Microsoft aligns with role',
        'Strong technical skills',
        'Worked at Amazon for 5 years',
      ],
    };

    const anonymized = anonymizeCandidate(candidate);
    expect(anonymized.matchReasons).toEqual(['Strong technical skills']);
  });

  it('should filter reasons mentioning schools', () => {
    const candidate: HybridSearchResultItem = {
      candidateId: 'cand-1',
      score: 0.8,
      vectorScore: 0.8,
      textScore: 0.7,
      confidence: 0.85,
      matchReasons: [
        'Graduated from MIT',
        'Excellent problem-solving skills',
        'Degree from Stanford University',
      ],
    };

    const anonymized = anonymizeCandidate(candidate);
    expect(anonymized.matchReasons).toEqual(['Excellent problem-solving skills']);
  });

  it('should filter reasons mentioning locations', () => {
    const candidate: HybridSearchResultItem = {
      candidateId: 'cand-1',
      score: 0.8,
      vectorScore: 0.8,
      textScore: 0.7,
      confidence: 0.85,
      matchReasons: [
        'Based in New York',
        'Senior level experience',
        'Located in Silicon Valley',
      ],
    };

    const anonymized = anonymizeCandidate(candidate);
    expect(anonymized.matchReasons).toEqual(['Senior level experience']);
  });

  it('should handle empty match reasons', () => {
    const candidate: HybridSearchResultItem = {
      candidateId: 'cand-1',
      score: 0.8,
      vectorScore: 0.8,
      textScore: 0.7,
      confidence: 0.85,
      matchReasons: [],
    };

    const anonymized = anonymizeCandidate(candidate);
    expect(anonymized.matchReasons).toEqual([]);
  });

  it('should preserve generic match reasons', () => {
    const candidate: HybridSearchResultItem = {
      candidateId: 'cand-1',
      score: 0.8,
      vectorScore: 0.8,
      textScore: 0.7,
      confidence: 0.85,
      matchReasons: [
        'Strong skill match for Python',
        'Senior level alignment',
        '10+ years of relevant experience',
        'High trajectory fit score',
      ],
    };

    const anonymized = anonymizeCandidate(candidate);
    expect(anonymized.matchReasons).toHaveLength(4);
    expect(anonymized.matchReasons).toContain('Strong skill match for Python');
    expect(anonymized.matchReasons).toContain('Senior level alignment');
    expect(anonymized.matchReasons).toContain('High trajectory fit score');
  });

  it('should replace years with [year] placeholder', () => {
    const candidate: HybridSearchResultItem = {
      candidateId: 'cand-1',
      score: 0.8,
      vectorScore: 0.8,
      textScore: 0.7,
      confidence: 0.85,
      matchReasons: ['Has been coding since 2015'],
    };

    const anonymized = anonymizeCandidate(candidate);
    expect(anonymized.matchReasons[0]).toBe('Has been coding since [year]');
  });
});

describe('skills preservation', () => {
  it('should preserve all skill names and weights', () => {
    const candidate: HybridSearchResultItem = {
      candidateId: 'cand-1',
      score: 0.8,
      vectorScore: 0.8,
      textScore: 0.7,
      confidence: 0.85,
      matchReasons: [],
      skills: [
        { name: 'Python', weight: 1.0 },
        { name: 'JavaScript', weight: 0.9 },
        { name: 'React', weight: 0.8 },
        { name: 'AWS', weight: 0.7 },
      ],
    };

    const anonymized = anonymizeCandidate(candidate);
    expect(anonymized.skills).toHaveLength(4);
    expect(anonymized.skills!.map((s) => s.name)).toEqual([
      'Python',
      'JavaScript',
      'React',
      'AWS',
    ]);
    expect(anonymized.skills!.map((s) => s.weight)).toEqual([1.0, 0.9, 0.8, 0.7]);
  });

  it('should not include skills when not present', () => {
    const candidate: HybridSearchResultItem = {
      candidateId: 'cand-1',
      score: 0.8,
      vectorScore: 0.8,
      textScore: 0.7,
      confidence: 0.85,
      matchReasons: [],
    };

    const anonymized = anonymizeCandidate(candidate);
    expect(anonymized.skills).toBeUndefined();
  });

  it('should not include skills when array is empty', () => {
    const candidate: HybridSearchResultItem = {
      candidateId: 'cand-1',
      score: 0.8,
      vectorScore: 0.8,
      textScore: 0.7,
      confidence: 0.85,
      matchReasons: [],
      skills: [],
    };

    const anonymized = anonymizeCandidate(candidate);
    expect(anonymized.skills).toBeUndefined();
  });
});

describe('industries preservation', () => {
  it('should preserve all industries', () => {
    const candidate: HybridSearchResultItem = {
      candidateId: 'cand-1',
      score: 0.8,
      vectorScore: 0.8,
      textScore: 0.7,
      confidence: 0.85,
      matchReasons: [],
      industries: ['Technology', 'Finance', 'Healthcare'],
    };

    const anonymized = anonymizeCandidate(candidate);
    expect(anonymized.industries).toEqual(['Technology', 'Finance', 'Healthcare']);
  });

  it('should create a copy of industries array', () => {
    const candidate: HybridSearchResultItem = {
      candidateId: 'cand-1',
      score: 0.8,
      vectorScore: 0.8,
      textScore: 0.7,
      confidence: 0.85,
      matchReasons: [],
      industries: ['Technology'],
    };

    const anonymized = anonymizeCandidate(candidate);
    candidate.industries!.push('Finance');
    expect(anonymized.industries).toEqual(['Technology']);
  });
});
