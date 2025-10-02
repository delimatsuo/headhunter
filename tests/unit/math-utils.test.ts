import { describe, it, expect } from 'vitest';

import {
  calculatePmi,
  applyRecencyDecay,
  calculateEma,
  calculateZScores
} from '../../services/hh-msgs-svc/src/math-utils';

describe('calculatePmi', () => {
  it('returns 0 when any count is zero or negative', () => {
    expect(
      calculatePmi({ jointCount: 0, baseCount: 10, relatedCount: 5, totalDocuments: 100 })
    ).toBe(0);
    expect(
      calculatePmi({ jointCount: 5, baseCount: -1, relatedCount: 5, totalDocuments: 100 })
    ).toBe(0);
    expect(
      calculatePmi({ jointCount: 5, baseCount: 10, relatedCount: 0, totalDocuments: 100 })
    ).toBe(0);
    expect(
      calculatePmi({ jointCount: 5, baseCount: 10, relatedCount: 5, totalDocuments: -10 })
    ).toBe(0);
  });

  it('returns positive PMI for correlated counts and scales with decayFactor', () => {
    const pmi = calculatePmi({
      jointCount: 20,
      baseCount: 25,
      relatedCount: 30,
      totalDocuments: 100,
      decayFactor: 0.5
    });

    expect(pmi).toBeGreaterThan(0);
    expect(pmi).toBeCloseTo(0.707, 3);
  });

  it('clamps negative PMI to zero', () => {
    const pmi = calculatePmi({
      jointCount: 1,
      baseCount: 50,
      relatedCount: 50,
      totalDocuments: 100
    });

    expect(pmi).toBe(0);
  });
});

describe('applyRecencyDecay', () => {
  it('returns 1 for non-positive daysSinceSeen', () => {
    expect(applyRecencyDecay(0)).toBe(1);
    expect(applyRecencyDecay(-5)).toBe(1);
  });

  it('halves approximately every half-life and decreases monotonically', () => {
    const atHalfLife = applyRecencyDecay(30, 30);
    const atDoubleHalfLife = applyRecencyDecay(60, 30);

    expect(atHalfLife).toBeCloseTo(0.5, 3);
    expect(atDoubleHalfLife).toBeLessThan(atHalfLife);
    expect(atDoubleHalfLife).toBeGreaterThan(0);
  });

  it('remains finite when half-life is non-positive', () => {
    const value = applyRecencyDecay(10, 0);

    expect(Number.isFinite(value)).toBe(true);
    expect(value).toBeGreaterThan(0);
    expect(value).toBeLessThan(1);
  });
});

describe('calculateEma', () => {
  it('returns the original series when span is less than or equal to 1', () => {
    const series = [5, 7, 9];

    expect(calculateEma(series, 1)).toEqual(series);
    expect(calculateEma(series, 0)).toEqual(series);
  });

  it('produces expected values for a known sequence', () => {
    const ema = calculateEma([10, 20, 30, 40], 3);

    expect(ema).toHaveLength(4);
    expect(ema[0]).toBeCloseTo(10, 6);
    expect(ema[1]).toBeCloseTo(15, 6);
    expect(ema[2]).toBeCloseTo(22.5, 6);
    expect(ema[3]).toBeCloseTo(31.25, 6);
  });

  it('returns a constant series when input is constant', () => {
    const ema = calculateEma([5, 5, 5, 5], 4);

    expect(ema).toEqual([5, 5, 5, 5]);
  });
});

describe('calculateZScores', () => {
  it('returns an empty array when series is empty', () => {
    expect(calculateZScores([])).toEqual([]);
  });

  it('returns zeros when series has no variance', () => {
    expect(calculateZScores([3, 3, 3])).toEqual([0, 0, 0]);
  });

  it('standardizes mixed series around zero mean', () => {
    const zscores = calculateZScores([1, 2, 3, 4, 5]);

    expect(zscores).toHaveLength(5);
    expect(zscores[0]).toBeCloseTo(-1.2649, 3);
    expect(zscores[1]).toBeCloseTo(-0.6325, 3);
    expect(zscores[2]).toBeCloseTo(0, 6);
    expect(zscores[3]).toBeCloseTo(0.6325, 3);
    expect(zscores[4]).toBeCloseTo(1.2649, 3);
    const mean = zscores.reduce((sum, value) => sum + value, 0) / zscores.length;
    expect(mean).toBeCloseTo(0, 6);
  });
});
