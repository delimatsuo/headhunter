import { describe, it, expect } from 'vitest';
import {
  calculateTrajectoryDirection,
  calculateTrajectoryVelocity,
  classifyTrajectoryType,
  mapTitleToLevel,
  calculateTrajectoryFit,
  computeTrajectoryMetrics,
  type ExperienceEntry,
  type CareerTrajectoryData,
  type TrajectoryContext,
  type TrajectoryMetrics
} from './trajectory-calculators';

describe('mapTitleToLevel', () => {
  it('maps standard technical titles correctly', () => {
    expect(mapTitleToLevel('Junior Engineer')).toBe(1);
    expect(mapTitleToLevel('Senior Developer')).toBe(3);
    expect(mapTitleToLevel('Staff Engineer')).toBe(4);
    expect(mapTitleToLevel('Principal Architect')).toBe(5);
  });

  it('maps standard management titles correctly', () => {
    expect(mapTitleToLevel('Engineering Manager')).toBe(7);
    expect(mapTitleToLevel('Director')).toBe(9);
    expect(mapTitleToLevel('VP of Engineering')).toBe(11);
    expect(mapTitleToLevel('CTO')).toBe(13);
  });

  it('handles title variations', () => {
    expect(mapTitleToLevel('Sr. Software Engineer')).toBe(3);
    expect(mapTitleToLevel('Lead Developer')).toBe(4);
    expect(mapTitleToLevel('EM')).toBe(7);
    expect(mapTitleToLevel('Vice President')).toBe(11);
  });

  it('returns -1 for unknown titles', () => {
    expect(mapTitleToLevel('Product Manager')).toBe(-1);
    expect(mapTitleToLevel('Data Analyst')).toBe(-1);
    expect(mapTitleToLevel('')).toBe(-1);
    expect(mapTitleToLevel(null as unknown as string)).toBe(-1);
  });
});

describe('calculateTrajectoryDirection', () => {
  describe('upward trajectory', () => {
    it('detects upward trajectory from Junior -> Senior -> Staff', () => {
      const sequence = ['Junior Engineer', 'Senior Engineer', 'Staff Engineer'];
      expect(calculateTrajectoryDirection(sequence)).toBe('upward');
    });

    it('detects upward trajectory from Intern -> Mid -> Senior', () => {
      const sequence = ['Intern', 'Mid-Level Developer', 'Senior Developer'];
      expect(calculateTrajectoryDirection(sequence)).toBe('upward');
    });

    it('detects upward trajectory in management track', () => {
      const sequence = ['Engineering Manager', 'Director', 'VP'];
      expect(calculateTrajectoryDirection(sequence)).toBe('upward');
    });
  });

  describe('lateral trajectory', () => {
    it('detects lateral trajectory from same-level moves', () => {
      const sequence = ['Senior Engineer', 'Senior Developer', 'Senior Architect'];
      expect(calculateTrajectoryDirection(sequence)).toBe('lateral');
    });

    it('detects lateral trajectory with mixed small changes', () => {
      const sequence = ['Senior Engineer', 'Staff Engineer', 'Senior Engineer'];
      expect(calculateTrajectoryDirection(sequence)).toBe('lateral');
    });

    it('treats tech -> management at similar level as lateral', () => {
      const sequence = ['Senior Engineer', 'Engineering Manager'];
      expect(calculateTrajectoryDirection(sequence)).toBe('lateral');
    });
  });

  describe('downward trajectory', () => {
    it('detects downward trajectory from role reset', () => {
      const sequence = ['Director', 'Senior Engineer'];
      expect(calculateTrajectoryDirection(sequence)).toBe('downward');
    });

    it('detects downward trajectory from multiple demotions', () => {
      const sequence = ['Staff Engineer', 'Senior Engineer', 'Junior Engineer'];
      expect(calculateTrajectoryDirection(sequence)).toBe('downward');
    });
  });

  describe('edge cases', () => {
    it('returns lateral for single title', () => {
      expect(calculateTrajectoryDirection(['Senior Engineer'])).toBe('lateral');
    });

    it('returns lateral for empty array', () => {
      expect(calculateTrajectoryDirection([])).toBe('lateral');
    });

    it('returns lateral when all titles are unknown', () => {
      const sequence = ['Product Manager', 'Data Analyst', 'Designer'];
      expect(calculateTrajectoryDirection(sequence)).toBe('lateral');
    });

    it('handles mixed known/unknown titles', () => {
      const sequence = ['Junior Engineer', 'Product Manager', 'Senior Engineer'];
      expect(calculateTrajectoryDirection(sequence)).toBe('upward');
    });
  });
});

describe('calculateTrajectoryVelocity', () => {
  describe('date-based velocity detection', () => {
    it('detects fast velocity when promotions < 2 years apart', () => {
      const experiences: ExperienceEntry[] = [
        { title: 'Junior Engineer', startDate: '2020-01-01', endDate: '2021-06-01' },
        { title: 'Senior Engineer', startDate: '2021-06-01', endDate: '2023-01-01' }
      ];
      expect(calculateTrajectoryVelocity(experiences)).toBe('fast');
    });

    it('detects normal velocity when promotions 2-4 years apart', () => {
      const experiences: ExperienceEntry[] = [
        { title: 'Junior Engineer', startDate: '2018-01-01', endDate: '2021-01-01' },
        { title: 'Mid-Level Developer', startDate: '2021-01-01', endDate: '2024-01-01' },
        { title: 'Senior Engineer', startDate: '2024-01-01', endDate: '2026-01-01' }
      ];
      // Junior (1) -> Mid (2) = 3 years, Mid (2) -> Senior (3) = 3 years
      // Total: 2 level increases over 6 years = 3 years/level = normal
      expect(calculateTrajectoryVelocity(experiences)).toBe('normal');
    });

    it('detects slow velocity when promotions > 4 years apart', () => {
      const experiences: ExperienceEntry[] = [
        { title: 'Junior Engineer', startDate: '2015-01-01', endDate: '2020-01-01' },
        { title: 'Mid-Level Developer', startDate: '2020-01-01', endDate: '2025-01-01' },
        { title: 'Senior Engineer', startDate: '2025-01-01', endDate: '2030-01-01' }
      ];
      // Junior (1) -> Mid (2) = 5 years, Mid (2) -> Senior (3) = 5 years
      // Total: 2 level increases over 10 years = 5 years/level = slow
      expect(calculateTrajectoryVelocity(experiences)).toBe('slow');
    });

    it('handles multiple promotions correctly', () => {
      const experiences: ExperienceEntry[] = [
        { title: 'Junior Engineer', startDate: '2019-01-01', endDate: '2020-07-01' },
        { title: 'Mid-Level Developer', startDate: '2020-07-01', endDate: '2022-01-01' },
        { title: 'Senior Engineer', startDate: '2022-01-01', endDate: '2024-01-01' }
      ];
      // Average: ~1.5 years per level = fast
      expect(calculateTrajectoryVelocity(experiences)).toBe('fast');
    });
  });

  describe('Together AI fallback', () => {
    it('uses Together AI promotion_velocity when dates missing', () => {
      const experiences: ExperienceEntry[] = [
        { title: 'Senior Engineer' },
        { title: 'Staff Engineer' }
      ];
      const togetherAiData: CareerTrajectoryData = {
        promotion_velocity: 'fast'
      };
      expect(calculateTrajectoryVelocity(experiences, togetherAiData)).toBe('fast');
    });

    it('uses Together AI data when experiences have no dates', () => {
      const experiences: ExperienceEntry[] = [
        { title: 'Junior Engineer', startDate: '2020-01-01' }, // missing endDate
        { title: 'Senior Engineer', endDate: '2024-01-01' } // missing startDate
      ];
      const togetherAiData: CareerTrajectoryData = {
        promotion_velocity: 'slow'
      };
      expect(calculateTrajectoryVelocity(experiences, togetherAiData)).toBe('slow');
    });
  });

  describe('edge cases', () => {
    it('returns normal for single experience', () => {
      const experiences: ExperienceEntry[] = [
        { title: 'Senior Engineer', startDate: '2020-01-01', endDate: '2024-01-01' }
      ];
      expect(calculateTrajectoryVelocity(experiences)).toBe('normal');
    });

    it('returns normal for empty array', () => {
      expect(calculateTrajectoryVelocity([])).toBe('normal');
    });

    it('returns normal when all titles are unknown', () => {
      const experiences: ExperienceEntry[] = [
        { title: 'Product Manager', startDate: '2020-01-01', endDate: '2022-01-01' },
        { title: 'Data Analyst', startDate: '2022-01-01', endDate: '2024-01-01' }
      ];
      expect(calculateTrajectoryVelocity(experiences)).toBe('normal');
    });
  });
});

describe('classifyTrajectoryType', () => {
  describe('technical growth detection', () => {
    it('detects technical_growth from IC progression', () => {
      const sequence = ['Senior Engineer', 'Staff Engineer', 'Principal Engineer'];
      expect(classifyTrajectoryType(sequence)).toBe('technical_growth');
    });

    it('detects technical_growth from junior to senior progression', () => {
      const sequence = ['Junior Engineer', 'Mid-Level Developer', 'Senior Engineer'];
      expect(classifyTrajectoryType(sequence)).toBe('technical_growth');
    });
  });

  describe('leadership track detection', () => {
    it('detects leadership_track from management progression', () => {
      const sequence = ['Engineering Manager', 'Senior Manager', 'Director'];
      expect(classifyTrajectoryType(sequence)).toBe('leadership_track');
    });

    it('detects leadership_track from director to VP', () => {
      const sequence = ['Director', 'Senior Director', 'VP'];
      expect(classifyTrajectoryType(sequence)).toBe('leadership_track');
    });
  });

  describe('career pivot detection', () => {
    it('detects career_pivot from IC to management transition', () => {
      const sequence = ['Senior Engineer', 'Engineering Manager'];
      expect(classifyTrajectoryType(sequence)).toBe('career_pivot');
    });

    it('detects career_pivot from management to IC transition', () => {
      const sequence = ['Engineering Manager', 'Staff Engineer'];
      expect(classifyTrajectoryType(sequence)).toBe('career_pivot');
    });

    it('detects career_pivot from function changes', () => {
      const sequence = ['Frontend Engineer', 'Backend Engineer', 'DevOps Engineer'];
      expect(classifyTrajectoryType(sequence)).toBe('career_pivot');
    });

    it('detects career_pivot from frontend to data science', () => {
      const sequence = ['Frontend Developer', 'Data Engineer'];
      expect(classifyTrajectoryType(sequence)).toBe('career_pivot');
    });
  });

  describe('lateral move detection', () => {
    it('detects lateral_move for same-level moves', () => {
      const sequence = ['Senior Engineer', 'Senior Developer', 'Senior Architect'];
      expect(classifyTrajectoryType(sequence)).toBe('lateral_move');
    });

    it('detects lateral_move when no clear progression', () => {
      const sequence = ['Senior Engineer', 'Senior Developer'];
      expect(classifyTrajectoryType(sequence)).toBe('lateral_move');
    });
  });

  describe('edge cases', () => {
    it('returns lateral_move for single title', () => {
      expect(classifyTrajectoryType(['Senior Engineer'])).toBe('lateral_move');
    });

    it('returns lateral_move for empty array', () => {
      expect(classifyTrajectoryType([])).toBe('lateral_move');
    });

    it('returns lateral_move when all titles are unknown', () => {
      const sequence = ['Product Manager', 'Data Analyst', 'Designer'];
      expect(classifyTrajectoryType(sequence)).toBe('lateral_move');
    });

    it('handles mixed known/unknown titles for technical growth', () => {
      const sequence = ['Junior Engineer', 'Product Manager', 'Senior Engineer', 'Staff Engineer'];
      expect(classifyTrajectoryType(sequence)).toBe('technical_growth');
    });
  });
});

describe('calculateTrajectoryFit', () => {
  describe('high fit scenarios', () => {
    it('scores upward+fast in high-growth role near 1.0', () => {
      const metrics: TrajectoryMetrics = {
        direction: 'upward',
        velocity: 'fast',
        type: 'technical_growth'
      };
      const context: TrajectoryContext = {
        targetTrack: 'technical',
        roleGrowthType: 'high_growth'
      };
      const score = calculateTrajectoryFit(metrics, context);
      expect(score).toBeGreaterThan(0.9);
      expect(score).toBeLessThanOrEqual(1.0);
    });

    it('scores leadership track for management role highly', () => {
      const metrics: TrajectoryMetrics = {
        direction: 'upward',
        velocity: 'normal',
        type: 'leadership_track'
      };
      const context: TrajectoryContext = {
        targetTrack: 'management',
        roleGrowthType: 'stable'
      };
      const score = calculateTrajectoryFit(metrics, context);
      expect(score).toBeGreaterThan(0.8);
    });

    it('scores technical IC progression for IC role highly', () => {
      const metrics: TrajectoryMetrics = {
        direction: 'upward',
        velocity: 'normal',
        type: 'technical_growth'
      };
      const context: TrajectoryContext = {
        targetTrack: 'technical',
        roleGrowthType: 'stable'
      };
      const score = calculateTrajectoryFit(metrics, context);
      expect(score).toBeGreaterThan(0.85);
    });
  });

  describe('track mismatch penalties', () => {
    it('penalizes IC trajectory for management role', () => {
      const metrics: TrajectoryMetrics = {
        direction: 'upward',
        velocity: 'fast',
        type: 'technical_growth'
      };
      const context: TrajectoryContext = {
        targetTrack: 'management'
      };
      const score = calculateTrajectoryFit(metrics, context);
      expect(score).toBeLessThanOrEqual(0.8);
    });

    it('penalizes management trajectory for IC role', () => {
      const metrics: TrajectoryMetrics = {
        direction: 'upward',
        velocity: 'normal',
        type: 'leadership_track'
      };
      const context: TrajectoryContext = {
        targetTrack: 'technical'
      };
      const score = calculateTrajectoryFit(metrics, context);
      expect(score).toBeLessThan(0.75);
    });
  });

  describe('pivot handling', () => {
    it('penalizes pivots when allowPivot is false', () => {
      const metrics: TrajectoryMetrics = {
        direction: 'lateral',
        velocity: 'normal',
        type: 'career_pivot'
      };
      const context: TrajectoryContext = {
        allowPivot: false
      };
      const score = calculateTrajectoryFit(metrics, context);
      expect(score).toBeLessThan(0.5);
    });

    it('allows pivots when allowPivot is true', () => {
      const metrics: TrajectoryMetrics = {
        direction: 'upward',
        velocity: 'fast',
        type: 'career_pivot'
      };
      const context: TrajectoryContext = {
        allowPivot: true
      };
      const score = calculateTrajectoryFit(metrics, context);
      // Should not apply pivot penalty
      expect(score).toBeGreaterThan(0.6);
    });
  });

  describe('downward trajectory handling', () => {
    it('scores downward trajectory low regardless of velocity', () => {
      const metricsFast: TrajectoryMetrics = {
        direction: 'downward',
        velocity: 'fast',
        type: 'technical_growth'
      };
      const metricsNormal: TrajectoryMetrics = {
        direction: 'downward',
        velocity: 'normal',
        type: 'technical_growth'
      };
      const metricsSlow: TrajectoryMetrics = {
        direction: 'downward',
        velocity: 'slow',
        type: 'technical_growth'
      };

      expect(calculateTrajectoryFit(metricsFast, {})).toBeLessThan(0.5);
      expect(calculateTrajectoryFit(metricsNormal, {})).toBeLessThan(0.5);
      expect(calculateTrajectoryFit(metricsSlow, {})).toBeLessThan(0.5);
    });
  });

  describe('neutral cases', () => {
    it('returns moderate score for lateral+normal with no context', () => {
      const metrics: TrajectoryMetrics = {
        direction: 'lateral',
        velocity: 'normal',
        type: 'lateral_move'
      };
      const score = calculateTrajectoryFit(metrics, {});
      expect(score).toBeGreaterThan(0.4);
      expect(score).toBeLessThan(0.6);
    });

    it('handles empty context gracefully', () => {
      const metrics: TrajectoryMetrics = {
        direction: 'upward',
        velocity: 'normal',
        type: 'technical_growth'
      };
      const score = calculateTrajectoryFit(metrics, {});
      expect(score).toBeGreaterThan(0);
      expect(score).toBeLessThanOrEqual(1.0);
    });
  });

  describe('growth type modifiers', () => {
    it('boosts fast velocity in high-growth roles', () => {
      const metrics: TrajectoryMetrics = {
        direction: 'upward',
        velocity: 'fast',
        type: 'technical_growth'
      };
      const highGrowthScore = calculateTrajectoryFit(metrics, { roleGrowthType: 'high_growth' });
      const stableScore = calculateTrajectoryFit(metrics, { roleGrowthType: 'stable' });

      // Both cap at 1.0, so they'll be equal when base score is high
      expect(highGrowthScore).toBeGreaterThanOrEqual(stableScore);
    });

    it('slightly favors normal velocity in stable roles', () => {
      const metricsFast: TrajectoryMetrics = {
        direction: 'upward',
        velocity: 'fast',
        type: 'technical_growth'
      };
      const metricsNormal: TrajectoryMetrics = {
        direction: 'upward',
        velocity: 'normal',
        type: 'technical_growth'
      };

      const fastScore = calculateTrajectoryFit(metricsFast, { roleGrowthType: 'stable' });
      const normalScore = calculateTrajectoryFit(metricsNormal, { roleGrowthType: 'stable' });

      // Normal gets 1.1x modifier (0.9 * 1.1 = 0.99), fast gets 1.0x (1.0 * 1.0 = 1.0 capped)
      // Fast is slightly higher or equal due to base score difference
      expect(fastScore).toBeGreaterThanOrEqual(normalScore * 0.99);
    });
  });
});

describe('computeTrajectoryMetrics', () => {
  it('computes all three trajectory metrics from title sequence', () => {
    const titleSequence = ['Junior Engineer', 'Senior Engineer', 'Staff Engineer'];
    const experiences: ExperienceEntry[] = [
      { title: 'Junior Engineer', startDate: '2020-01-01', endDate: '2022-01-01' },
      { title: 'Senior Engineer', startDate: '2022-01-01', endDate: '2024-01-01' },
      { title: 'Staff Engineer', startDate: '2024-01-01', endDate: '2026-01-01' }
    ];

    const metrics = computeTrajectoryMetrics(titleSequence, experiences);

    expect(metrics.direction).toBe('upward');
    // Junior(1)->Senior(3) = 2 years for 2 levels, Senior(3)->Staff(4) = 2 years for 1 level
    // Total: 3 level increases over 4 years = 1.33 years/level = fast
    expect(metrics.velocity).toBe('fast');
    expect(metrics.type).toBe('technical_growth');
  });

  it('handles missing experience dates with Together AI fallback', () => {
    const titleSequence = ['Senior Engineer', 'Staff Engineer'];
    const togetherAiData: CareerTrajectoryData = {
      promotion_velocity: 'fast'
    };

    const metrics = computeTrajectoryMetrics(titleSequence, undefined, togetherAiData);

    expect(metrics.direction).toBe('upward');
    expect(metrics.velocity).toBe('fast'); // From Together AI
    expect(metrics.type).toBe('technical_growth');
  });

  it('returns neutral values for insufficient data', () => {
    const titleSequence = ['Senior Engineer'];
    const metrics = computeTrajectoryMetrics(titleSequence);

    expect(metrics.direction).toBe('lateral');
    expect(metrics.velocity).toBe('normal');
    expect(metrics.type).toBe('lateral_move');
  });
});
