import { describe, it, expect } from 'vitest';

import {
  applyRecencyDecay,
  calculateEma,
  calculatePmi,
  calculateZScores
} from '../../src/math-utils';

describe('calculatePmi', () => {
  it('returns zero when any supporting count is non-positive', () => {
    expect(
      calculatePmi({
        jointCount: 0,
        baseCount: 10,
        relatedCount: 10,
        totalDocuments: 100
      })
    ).toBe(0);

    expect(
      calculatePmi({
        jointCount: 5,
        baseCount: 0,
        relatedCount: 10,
        totalDocuments: 100
      })
    ).toBe(0);
  });

  it('applies decay but never returns negative scores', () => {
    const score = calculatePmi({
      jointCount: 50,
      baseCount: 100,
      relatedCount: 80,
      totalDocuments: 200,
      decayFactor: 0.5
    });

    expect(score).toBeGreaterThan(0);

    const decayedScore = calculatePmi({
      jointCount: 50,
      baseCount: 100,
      relatedCount: 80,
      totalDocuments: 200,
      decayFactor: -1
    });

    expect(decayedScore).toBe(0);
  });
});

describe('applyRecencyDecay', () => {
  it('returns 1 for current observations and ~0.5 for half-life', () => {
    expect(applyRecencyDecay(0, 30)).toBe(1);
    const halfLife = applyRecencyDecay(30, 30);
    expect(halfLife).toBeGreaterThan(0.49);
    expect(halfLife).toBeLessThan(0.51);
  });
});

describe('calculateEma', () => {
  it('produces expected smoothing for a known sequence', () => {
    const series = [1, 2, 3, 4];
    const ema = calculateEma(series, 3);

    expect(ema.length).toBe(series.length);
    expect(ema[0]).toBe(1);
    expect(ema[1]).toBeCloseTo(1.5, 1);
    expect(ema[2]).toBeCloseTo(2.25, 2);
    expect(ema[3]).toBeCloseTo(3.125, 3);
  });
});

describe('calculateZScores', () => {
  it('returns all zeros for a constant series', () => {
    expect(calculateZScores([5, 5, 5])).toEqual([0, 0, 0]);
  });

  it('normalises variable series', () => {
    const zscores = calculateZScores([1, 2, 3]);

    expect(zscores.length).toBe(3);
    expect(zscores.reduce((sum, value) => sum + value, 0)).toBeCloseTo(0, 10);
    expect(zscores[0]).toBeLessThan(0);
    expect(zscores[2]).toBeGreaterThan(0);
  });
});
