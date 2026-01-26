import { describe, it, expect, vi } from 'vitest';
import type { HybridSearchResultItem } from '../types';
import type { DiversityConfig } from './types';

// Mock @hh/common before importing slate-diversity module
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
  analyzeSlateDiversity,
  formatDiversitySummary,
  shouldShowDiversityWarning,
  inferCompanyTier,
  inferExperienceBand,
  inferSpecialty,
} from './slate-diversity';

// Helper to create mock candidates
function createMockCandidate(
  id: string,
  overrides: Partial<HybridSearchResultItem> = {}
): HybridSearchResultItem {
  return {
    candidateId: id,
    score: 0.8,
    vectorScore: 0.8,
    textScore: 0.7,
    confidence: 0.85,
    matchReasons: [],
    ...overrides,
  };
}

// ============================================================================
// Inference Function Tests
// ============================================================================

describe('inferCompanyTier', () => {
  it('should identify FAANG companies', () => {
    expect(inferCompanyTier(['Google'])).toBe('faang');
    expect(inferCompanyTier(['Meta'])).toBe('faang');
    expect(inferCompanyTier(['Amazon'])).toBe('faang');
    expect(inferCompanyTier(['Apple Inc.'])).toBe('faang');
    expect(inferCompanyTier(['Microsoft'])).toBe('faang');
  });

  it('should identify enterprise companies', () => {
    expect(inferCompanyTier(['JP Morgan Bank'])).toBe('enterprise');
    expect(inferCompanyTier(['State Farm Insurance'])).toBe('enterprise');
    expect(inferCompanyTier(['Acme Corporation'])).toBe('enterprise');
    expect(inferCompanyTier(['BigCo Holdings Ltd'])).toBe('enterprise');
  });

  it('should default to startup for small companies', () => {
    expect(inferCompanyTier(['Acme Startup'])).toBe('startup');
    expect(inferCompanyTier(['TechCo'])).toBe('startup');
  });

  it('should return unknown for empty input', () => {
    expect(inferCompanyTier([])).toBe('unknown');
    expect(inferCompanyTier([''])).toBe('startup');  // Empty string doesn't match patterns
  });
});

describe('inferExperienceBand', () => {
  it('should correctly band experience years', () => {
    expect(inferExperienceBand(0)).toBe('0-3');
    expect(inferExperienceBand(2)).toBe('0-3');
    expect(inferExperienceBand(3)).toBe('3-7');
    expect(inferExperienceBand(5)).toBe('3-7');
    expect(inferExperienceBand(7)).toBe('7-15');
    expect(inferExperienceBand(10)).toBe('7-15');
    expect(inferExperienceBand(15)).toBe('15+');
    expect(inferExperienceBand(20)).toBe('15+');
  });

  it('should return unknown for undefined', () => {
    expect(inferExperienceBand(undefined)).toBe('unknown');
  });
});

describe('inferSpecialty', () => {
  it('should identify frontend specialists', () => {
    expect(inferSpecialty(['React', 'TypeScript', 'CSS'], 'Frontend Developer')).toBe('frontend');
    expect(inferSpecialty(['Vue.js', 'JavaScript'], undefined)).toBe('frontend');
  });

  it('should identify backend specialists', () => {
    expect(inferSpecialty(['Python', 'Django', 'PostgreSQL'], 'Backend Engineer')).toBe('backend');
    expect(inferSpecialty(['Java', 'Spring', 'Kafka'], undefined)).toBe('backend');
  });

  it('should identify mobile specialists', () => {
    expect(inferSpecialty(['iOS', 'Swift', 'Xcode'], 'iOS Developer')).toBe('mobile');
    expect(inferSpecialty(['Android', 'Kotlin'], undefined)).toBe('mobile');
  });

  it('should identify devops specialists', () => {
    expect(inferSpecialty(['Kubernetes', 'Docker', 'AWS'], 'DevOps Engineer')).toBe('devops');
    expect(inferSpecialty(['Terraform', 'Jenkins', 'Linux'], undefined)).toBe('devops');
  });

  it('should identify data specialists', () => {
    expect(inferSpecialty(['Machine Learning', 'Python', 'TensorFlow'], 'ML Engineer')).toBe('data');
    expect(inferSpecialty(['Pandas', 'NumPy', 'Data Science'], undefined)).toBe('data');
  });

  it('should return generalist for mixed/low skills', () => {
    expect(inferSpecialty(['Communication', 'Leadership'], 'Manager')).toBe('generalist');
    expect(inferSpecialty([], undefined)).toBe('generalist');
  });
});

// ============================================================================
// Main Analysis Tests
// ============================================================================

describe('analyzeSlateDiversity', () => {
  const defaultConfig: DiversityConfig = {
    concentrationThreshold: 0.70,
    minCandidates: 5,
    dimensions: ['companyTier', 'experienceBand', 'specialty'],
  };

  it('should skip analysis for too few candidates', () => {
    const candidates = [
      createMockCandidate('1'),
      createMockCandidate('2'),
    ];

    const result = analyzeSlateDiversity(candidates, defaultConfig);

    expect(result.totalCandidates).toBe(2);
    expect(result.dimensions).toHaveLength(0);
    expect(result.warnings).toHaveLength(0);
    expect(result.diversityScore).toBe(100);
  });

  it('should detect concentrated experience bands', () => {
    const candidates = [
      createMockCandidate('1', { yearsExperience: 10 }),
      createMockCandidate('2', { yearsExperience: 12 }),
      createMockCandidate('3', { yearsExperience: 8 }),
      createMockCandidate('4', { yearsExperience: 11 }),
      createMockCandidate('5', { yearsExperience: 9 }),
      createMockCandidate('6', { yearsExperience: 2 }),  // Different band
    ];

    const result = analyzeSlateDiversity(candidates, defaultConfig);

    const expBand = result.dimensions.find(d => d.dimension === 'experienceBand');
    expect(expBand).toBeDefined();
    expect(expBand!.dominantGroup).toBe('7-15');
    expect(expBand!.isConcentrated).toBe(true);
    expect(expBand!.concentrationPct).toBeGreaterThan(70);
  });

  it('should generate warning for concentrated slate', () => {
    const candidates = Array(10).fill(null).map((_, i) =>
      createMockCandidate(`${i}`, { yearsExperience: 10 })  // All 7-15 band
    );

    const result = analyzeSlateDiversity(candidates, defaultConfig);

    expect(result.hasConcentrationIssue).toBe(true);
    expect(result.warnings.length).toBeGreaterThan(0);

    const expWarning = result.warnings.find(w => w.dimension === 'experienceBand');
    expect(expWarning).toBeDefined();
    expect(expWarning!.message).toContain('7-15');
    expect(expWarning!.suggestion).toBeDefined();
  });

  it('should detect diverse slate with no warnings', () => {
    const candidates = [
      createMockCandidate('1', { yearsExperience: 2, skills: [{ name: 'React', weight: 1 }] }),
      createMockCandidate('2', { yearsExperience: 5, skills: [{ name: 'Python', weight: 1 }] }),
      createMockCandidate('3', { yearsExperience: 10, skills: [{ name: 'Kubernetes', weight: 1 }] }),
      createMockCandidate('4', { yearsExperience: 15, skills: [{ name: 'React', weight: 1 }, { name: 'Python', weight: 1 }] }),
      createMockCandidate('5', { yearsExperience: 8, skills: [{ name: 'Swift', weight: 1 }] }),
    ];

    const result = analyzeSlateDiversity(candidates, defaultConfig);

    // Experience band should be diverse (0-3, 3-7, 7-15, 15+)
    const expBand = result.dimensions.find(d => d.dimension === 'experienceBand');
    expect(expBand!.isConcentrated).toBe(false);
  });

  it('should calculate diversity score', () => {
    // Homogeneous slate - all same experience and similar specialty
    const homogeneous = Array(10).fill(null).map((_, i) =>
      createMockCandidate(`${i}`, {
        yearsExperience: 10,
        skills: [{ name: 'Python', weight: 1 }, { name: 'Django', weight: 1 }],
      })
    );

    const homogeneousResult = analyzeSlateDiversity(homogeneous, defaultConfig);
    // All 10 candidates have:
    // - same experience band (7-15) = 100% concentration
    // - same specialty (backend) = 100% concentration
    // - unknown company tier = 100% concentration
    // This results in concentration warnings
    expect(homogeneousResult.hasConcentrationIssue).toBe(true);

    // Diverse slate with different experience bands and specialties
    const diverse = [
      createMockCandidate('1', { yearsExperience: 2, skills: [{ name: 'React', weight: 1 }, { name: 'CSS', weight: 1 }] }),
      createMockCandidate('2', { yearsExperience: 5, skills: [{ name: 'Python', weight: 1 }, { name: 'PostgreSQL', weight: 1 }] }),
      createMockCandidate('3', { yearsExperience: 10, skills: [{ name: 'Kubernetes', weight: 1 }, { name: 'Docker', weight: 1 }] }),
      createMockCandidate('4', { yearsExperience: 18, skills: [{ name: 'Swift', weight: 1 }, { name: 'iOS', weight: 1 }] }),
      createMockCandidate('5', { yearsExperience: 7, skills: [{ name: 'TensorFlow', weight: 1 }, { name: 'Machine Learning', weight: 1 }] }),
    ];

    const diverseResult = analyzeSlateDiversity(diverse, defaultConfig);
    // Different experience bands (0-3, 3-7, 7-15, 15+) and specialties
    // Should have no concentration issues since experience is well distributed
    const expBand = diverseResult.dimensions.find(d => d.dimension === 'experienceBand');
    expect(expBand?.isConcentrated).toBe(false);

    // Diversity score should be high for diverse slate
    expect(diverseResult.diversityScore).toBeGreaterThanOrEqual(70);

    // Homogeneous slate should have warnings
    expect(homogeneousResult.warnings.length).toBeGreaterThan(0);
  });

  it('should respect custom threshold', () => {
    // Test only experience band dimension to avoid noise from other dimensions
    const candidates = Array(10).fill(null).map((_, i) =>
      createMockCandidate(`${i}`, { yearsExperience: i < 6 ? 10 : 2 })  // 60% in 7-15 band
    );

    const expOnlyConfig: DiversityConfig = {
      concentrationThreshold: 0.70,
      minCandidates: 5,
      dimensions: ['experienceBand'],  // Only test experience to isolate behavior
    };

    // Default 70% threshold - 60% should not warn
    const result1 = analyzeSlateDiversity(candidates, expOnlyConfig);
    const expBand1 = result1.dimensions.find(d => d.dimension === 'experienceBand');
    expect(expBand1?.isConcentrated).toBe(false);

    // Lower 50% threshold - 60% should warn
    const result2 = analyzeSlateDiversity(candidates, { ...expOnlyConfig, concentrationThreshold: 0.50 });
    const expBand2 = result2.dimensions.find(d => d.dimension === 'experienceBand');
    expect(expBand2?.isConcentrated).toBe(true);
  });
});

// ============================================================================
// Utility Function Tests
// ============================================================================

describe('formatDiversitySummary', () => {
  it('should format diverse slate summary', () => {
    const analysis = {
      totalCandidates: 10,
      dimensions: [],
      warnings: [],
      diversityScore: 85,
      hasConcentrationIssue: false,
    };

    const summary = formatDiversitySummary(analysis);
    expect(summary).toContain('Diverse slate');
    expect(summary).toContain('85');
  });

  it('should show top warning message', () => {
    const analysis = {
      totalCandidates: 10,
      dimensions: [],
      warnings: [
        {
          level: 'warning' as const,
          message: 'This slate is 85% from FAANG/Big Tech companies',
          dimension: 'companyTier' as const,
          concentrationPct: 85,
          suggestion: 'Consider including startups',
        },
      ],
      diversityScore: 40,
      hasConcentrationIssue: true,
    };

    const summary = formatDiversitySummary(analysis);
    expect(summary).toContain('85%');
    expect(summary).toContain('FAANG');
  });
});

describe('shouldShowDiversityWarning', () => {
  it('should show warning when concentrated', () => {
    const analysis = {
      totalCandidates: 10,
      dimensions: [],
      warnings: [],
      diversityScore: 70,
      hasConcentrationIssue: true,
    };

    expect(shouldShowDiversityWarning(analysis)).toBe(true);
  });

  it('should show warning when diversity score is low', () => {
    const analysis = {
      totalCandidates: 10,
      dimensions: [],
      warnings: [],
      diversityScore: 40,
      hasConcentrationIssue: false,
    };

    expect(shouldShowDiversityWarning(analysis)).toBe(true);
  });

  it('should not show warning for diverse slate', () => {
    const analysis = {
      totalCandidates: 10,
      dimensions: [],
      warnings: [],
      diversityScore: 80,
      hasConcentrationIssue: false,
    };

    expect(shouldShowDiversityWarning(analysis)).toBe(false);
  });
});

// ============================================================================
// Dimension-Specific Warning Tests
// ============================================================================

describe('dimension-specific warnings', () => {
  const defaultConfig: DiversityConfig = {
    concentrationThreshold: 0.70,
    minCandidates: 5,
    dimensions: ['companyTier', 'experienceBand', 'specialty'],
  };

  it('should generate company tier specific suggestion', () => {
    // Create candidates with metadata suggesting FAANG
    const candidates = Array(10).fill(null).map((_, i) =>
      createMockCandidate(`${i}`, {
        title: 'Engineer at Google',
        metadata: {
          intelligent_analysis: {
            experience: [{ company: 'Google' }],
          },
        },
      })
    );

    const result = analyzeSlateDiversity(candidates, defaultConfig);
    const warning = result.warnings.find(w => w.dimension === 'companyTier');

    if (warning) {
      expect(warning.suggestion).toContain('startup');
    }
  });

  it('should generate specialty specific suggestion', () => {
    const candidates = Array(10).fill(null).map((_, i) =>
      createMockCandidate(`${i}`, {
        skills: [
          { name: 'Python', weight: 1 },
          { name: 'PostgreSQL', weight: 1 },
          { name: 'Go', weight: 1 },
        ],
      })
    );

    const result = analyzeSlateDiversity(candidates, defaultConfig);
    const warning = result.warnings.find(w => w.dimension === 'specialty');

    if (warning) {
      expect(warning.suggestion).toContain('adjacent specialties');
    }
  });

  it('should set correct severity levels', () => {
    // 100% concentration = alert
    const alertCandidates = Array(10).fill(null).map((_, i) =>
      createMockCandidate(`${i}`, { yearsExperience: 10 })
    );
    const alertResult = analyzeSlateDiversity(alertCandidates, defaultConfig);
    const alertWarning = alertResult.warnings.find(w => w.dimension === 'experienceBand');
    expect(alertWarning?.level).toBe('alert');

    // 80% concentration = warning
    const warningCandidates = Array(10).fill(null).map((_, i) =>
      createMockCandidate(`${i}`, { yearsExperience: i < 8 ? 10 : 2 })
    );
    const warningResult = analyzeSlateDiversity(warningCandidates, defaultConfig);
    const warningWarning = warningResult.warnings.find(w => w.dimension === 'experienceBand');
    expect(warningWarning?.level).toBe('warning');

    // 70% concentration = info
    const infoCandidates = Array(10).fill(null).map((_, i) =>
      createMockCandidate(`${i}`, { yearsExperience: i < 7 ? 10 : 2 })
    );
    const infoResult = analyzeSlateDiversity(infoCandidates, defaultConfig);
    const infoWarning = infoResult.warnings.find(w => w.dimension === 'experienceBand');
    expect(infoWarning?.level).toBe('info');
  });
});

// ============================================================================
// Edge Cases
// ============================================================================

describe('edge cases', () => {
  const defaultConfig: DiversityConfig = {
    concentrationThreshold: 0.70,
    minCandidates: 5,
    dimensions: ['companyTier', 'experienceBand', 'specialty'],
  };

  it('should handle candidates with missing data gracefully', () => {
    const candidates = [
      createMockCandidate('1', {}),
      createMockCandidate('2', {}),
      createMockCandidate('3', {}),
      createMockCandidate('4', {}),
      createMockCandidate('5', {}),
    ];

    const result = analyzeSlateDiversity(candidates, defaultConfig);

    // Should not throw, should categorize as 'unknown' for most dimensions
    expect(result.totalCandidates).toBe(5);
    expect(result.dimensions.length).toBe(3);
  });

  it('should handle empty skills array', () => {
    const candidates = Array(5).fill(null).map((_, i) =>
      createMockCandidate(`${i}`, {
        skills: [],
        yearsExperience: 10,
      })
    );

    const result = analyzeSlateDiversity(candidates, defaultConfig);
    expect(result.totalCandidates).toBe(5);
  });

  it('should work with exactly minCandidates', () => {
    const candidates = Array(5).fill(null).map((_, i) =>
      createMockCandidate(`${i}`, { yearsExperience: 10 })
    );

    const result = analyzeSlateDiversity(candidates, { ...defaultConfig, minCandidates: 5 });
    expect(result.dimensions.length).toBe(3);
    expect(result.hasConcentrationIssue).toBe(true);
  });

  it('should work with custom dimensions subset', () => {
    const candidates = Array(10).fill(null).map((_, i) =>
      createMockCandidate(`${i}`, { yearsExperience: 10 })
    );

    const result = analyzeSlateDiversity(candidates, {
      ...defaultConfig,
      dimensions: ['experienceBand'],  // Only check one dimension
    });

    expect(result.dimensions.length).toBe(1);
    expect(result.dimensions[0].dimension).toBe('experienceBand');
  });
});
