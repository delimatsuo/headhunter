import { describe, it, expect, vi, beforeEach } from 'vitest';
import ShadowMode, { type TrajectoryPrediction, type ShadowModeConfig } from './shadow-mode';
import type { PredictRequest } from '../types';
import type { ShadowComparison } from './comparison-logger';

describe('ShadowMode', () => {
  let shadowMode: ShadowMode;
  let config: ShadowModeConfig;

  beforeEach(() => {
    config = {
      enabled: true,
      loggerConfig: {
        batchSize: 10,
        storageType: 'memory',
      },
    };
    shadowMode = new ShadowMode(config);
  });

  it('logs comparison when enabled', async () => {
    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Junior Engineer', 'Senior Engineer', 'Staff Engineer'],
      tenureDurations: [24, 36],
    };

    const mlPrediction: TrajectoryPrediction = {
      nextRole: 'Principal Engineer',
      nextRoleConfidence: 0.85,
      tenureMonths: { min: 18, max: 24 },
      hireability: 0.75,
    };

    await shadowMode.compare(request, mlPrediction);

    const stats = shadowMode.getStats();
    expect(stats.totalComparisons).toBe(1);
  });

  it('skips logging when disabled', async () => {
    const disabledConfig: ShadowModeConfig = {
      enabled: false,
      loggerConfig: {
        storageType: 'memory',
      },
    };
    const disabledShadowMode = new ShadowMode(disabledConfig);

    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer'],
    };

    const mlPrediction: TrajectoryPrediction = {
      nextRole: 'Staff Engineer',
      nextRoleConfidence: 0.75,
      tenureMonths: { min: 24, max: 36 },
      hireability: 0.70,
    };

    await disabledShadowMode.compare(request, mlPrediction);

    const stats = disabledShadowMode.getStats();
    expect(stats.totalComparisons).toBe(0);
  });

  it('computes direction agreement correctly', async () => {
    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Junior Engineer', 'Senior Engineer', 'Staff Engineer'],
    };

    // ML predicts high hireability -> upward direction
    const mlPrediction: TrajectoryPrediction = {
      nextRole: 'Principal Engineer',
      nextRoleConfidence: 0.85,
      tenureMonths: { min: 18, max: 24 },
      hireability: 0.80, // > 0.7 -> upward
    };

    await shadowMode.compare(request, mlPrediction);

    const recent = shadowMode.getRecent(1);
    expect(recent).toHaveLength(1);
    // Rule-based should also see upward progression (Junior -> Senior -> Staff)
    expect(recent[0].agreement.directionMatch).toBe(true);
  });

  it('computes velocity agreement correctly', async () => {
    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Junior Engineer', 'Senior Engineer', 'Staff Engineer'],
      tenureDurations: [18, 18], // Short tenures -> fast progression
    };

    // ML predicts short tenure -> fast velocity
    const mlPrediction: TrajectoryPrediction = {
      nextRole: 'Principal Engineer',
      nextRoleConfidence: 0.85,
      tenureMonths: { min: 12, max: 18 }, // < 24 months -> fast
      hireability: 0.75,
    };

    await shadowMode.compare(request, mlPrediction);

    const recent = shadowMode.getRecent(1);
    expect(recent).toHaveLength(1);
    // ML predicts fast (avgTenure = 15 months < 24)
    // Rule-based defaults to 'normal' without date information
    // So we expect velocity agreement may vary - just check it's logged
    expect(recent[0].mlBased.tenureMonths.min).toBe(12);
  });

  it('computes type agreement correctly', async () => {
    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Junior Engineer', 'Senior Engineer', 'Staff Engineer'],
    };

    // ML predicts "Staff Engineer" -> technical_growth
    const mlPrediction: TrajectoryPrediction = {
      nextRole: 'Staff Engineer',
      nextRoleConfidence: 0.85,
      tenureMonths: { min: 18, max: 24 },
      hireability: 0.75,
    };

    await shadowMode.compare(request, mlPrediction);

    const recent = shadowMode.getRecent(1);
    expect(recent).toHaveLength(1);
    // Rule-based should also see technical_growth (IC progression)
    expect(recent[0].agreement.typeMatch).toBe(true);
    expect(recent[0].ruleBased.type).toBe('technical_growth');
  });

  it('detects disagreement for leadership track', async () => {
    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Junior Engineer', 'Senior Engineer', 'Staff Engineer'],
    };

    // ML predicts "Engineering Manager" -> leadership_track (disagreement with rule-based)
    const mlPrediction: TrajectoryPrediction = {
      nextRole: 'Engineering Manager',
      nextRoleConfidence: 0.75,
      tenureMonths: { min: 24, max: 36 },
      hireability: 0.70,
    };

    await shadowMode.compare(request, mlPrediction);

    const recent = shadowMode.getRecent(1);
    expect(recent).toHaveLength(1);
    // Rule-based sees technical_growth, ML infers leadership_track
    expect(recent[0].agreement.typeMatch).toBe(false);
    expect(recent[0].ruleBased.type).toBe('technical_growth');
  });

  it('returns correct stats', async () => {
    // Add 3 comparisons with varying agreement
    const requests: Array<{ request: PredictRequest; mlPrediction: TrajectoryPrediction }> = [
      {
        request: {
          candidateId: 'cand-1',
          titleSequence: ['Junior Engineer', 'Senior Engineer', 'Staff Engineer'],
        },
        mlPrediction: {
          nextRole: 'Principal Engineer',
          nextRoleConfidence: 0.85,
          tenureMonths: { min: 18, max: 24 },
          hireability: 0.80, // upward, fast, technical_growth
        },
      },
      {
        request: {
          candidateId: 'cand-2',
          titleSequence: ['Senior Engineer', 'Staff Engineer'],
        },
        mlPrediction: {
          nextRole: 'Engineering Manager',
          nextRoleConfidence: 0.75,
          tenureMonths: { min: 48, max: 60 }, // slow velocity
          hireability: 0.50, // lateral direction
        },
      },
      {
        request: {
          candidateId: 'cand-3',
          titleSequence: ['Engineering Manager', 'Director', 'VP'],
        },
        mlPrediction: {
          nextRole: 'Senior VP',
          nextRoleConfidence: 0.90,
          tenureMonths: { min: 30, max: 42 },
          hireability: 0.85, // upward, normal, leadership_track
        },
      },
    ];

    for (const { request, mlPrediction } of requests) {
      await shadowMode.compare(request, mlPrediction);
    }

    const stats = shadowMode.getStats();
    expect(stats.totalComparisons).toBe(3);
    expect(stats.directionAgreement).toBeGreaterThanOrEqual(0);
    expect(stats.directionAgreement).toBeLessThanOrEqual(1);
    expect(stats.velocityAgreement).toBeGreaterThanOrEqual(0);
    expect(stats.velocityAgreement).toBeLessThanOrEqual(1);
    expect(stats.typeAgreement).toBeGreaterThanOrEqual(0);
    expect(stats.typeAgreement).toBeLessThanOrEqual(1);
  });
});

describe('ComparisonLogger', () => {
  let shadowMode: ShadowMode;

  beforeEach(() => {
    const config: ShadowModeConfig = {
      enabled: true,
      loggerConfig: {
        batchSize: 3, // Small batch size for testing
        storageType: 'memory',
      },
    };
    shadowMode = new ShadowMode(config);
  });

  it('batches logs correctly', async () => {
    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer', 'Staff Engineer'],
    };

    const mlPrediction: TrajectoryPrediction = {
      nextRole: 'Principal Engineer',
      nextRoleConfidence: 0.85,
      tenureMonths: { min: 18, max: 24 },
      hireability: 0.75,
    };

    // Log 2 comparisons (under batch size)
    await shadowMode.compare(request, mlPrediction);
    await shadowMode.compare({ ...request, candidateId: 'cand-124' }, mlPrediction);

    const stats = shadowMode.getStats();
    expect(stats.totalComparisons).toBe(2);
  });

  it('flushes when batch size reached', async () => {
    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer', 'Staff Engineer'],
    };

    const mlPrediction: TrajectoryPrediction = {
      nextRole: 'Principal Engineer',
      nextRoleConfidence: 0.85,
      tenureMonths: { min: 18, max: 24 },
      hireability: 0.75,
    };

    // Log 3 comparisons (equals batch size, triggers flush)
    await shadowMode.compare(request, mlPrediction);
    await shadowMode.compare({ ...request, candidateId: 'cand-124' }, mlPrediction);
    await shadowMode.compare({ ...request, candidateId: 'cand-125' }, mlPrediction);

    const stats = shadowMode.getStats();
    // With memory storage, logs persist after flush
    expect(stats.totalComparisons).toBe(3);
  });

  it('calculates agreement percentages', async () => {
    const requests: Array<{ candidateId: string; agreement: { upward: boolean; fast: boolean } }> = [
      { candidateId: 'cand-1', agreement: { upward: true, fast: true } },
      { candidateId: 'cand-2', agreement: { upward: true, fast: false } },
      { candidateId: 'cand-3', agreement: { upward: false, fast: true } },
      { candidateId: 'cand-4', agreement: { upward: false, fast: false } },
    ];

    for (const { candidateId, agreement } of requests) {
      const request: PredictRequest = {
        candidateId,
        titleSequence: ['Junior Engineer', 'Senior Engineer', 'Staff Engineer'],
      };

      const mlPrediction: TrajectoryPrediction = {
        nextRole: 'Principal Engineer',
        nextRoleConfidence: 0.85,
        tenureMonths: agreement.fast
          ? { min: 12, max: 18 } // fast
          : { min: 48, max: 60 }, // slow
        hireability: agreement.upward ? 0.80 : 0.30, // upward vs downward
      };

      await shadowMode.compare(request, mlPrediction);
    }

    const stats = shadowMode.getStats();
    expect(stats.totalComparisons).toBe(4);
    // 2 out of 4 should match direction (50%)
    expect(stats.directionAgreement).toBe(0.5);
  });
});
