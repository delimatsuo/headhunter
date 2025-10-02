import { mean, standardDeviation } from 'simple-statistics';

interface PmiInputs {
  jointCount: number;
  baseCount: number;
  relatedCount: number;
  totalDocuments: number;
  decayFactor?: number;
}

export function calculatePmi({
  jointCount,
  baseCount,
  relatedCount,
  totalDocuments,
  decayFactor = 1
}: PmiInputs): number {
  if (jointCount <= 0 || baseCount <= 0 || relatedCount <= 0 || totalDocuments <= 0) {
    return 0;
  }

  const numerator = jointCount / totalDocuments;
  const denominator = (baseCount / totalDocuments) * (relatedCount / totalDocuments);
  if (denominator <= 0) {
    return 0;
  }

  const raw = Math.log2(numerator / denominator);
  return Math.max(0, raw * decayFactor);
}

export function applyRecencyDecay(daysSinceSeen: number, halfLifeDays = 30): number {
  if (daysSinceSeen <= 0) {
    return 1;
  }
  const lambda = Math.log(2) / Math.max(halfLifeDays, 1);
  return Math.exp(-lambda * daysSinceSeen);
}

export function calculateEma(series: number[], span: number): number[] {
  if (!series.length || span <= 1) {
    return series.map((value) => value);
  }

  const alpha = 2 / (span + 1);
  const ema: number[] = [];
  series.forEach((value, index) => {
    if (index === 0) {
      ema.push(value);
    } else {
      ema.push(value * alpha + ema[index - 1] * (1 - alpha));
    }
  });

  return ema;
}

export function calculateZScores(series: number[]): number[] {
  if (series.length === 0) {
    return [];
  }

  const seriesMean = mean(series);
  const sd = standardDeviation(series);
  if (sd === 0) {
    return series.map(() => 0);
  }

  return series.map((value) => (value - seriesMean) / sd);
}

export function classifyTrend(latest: number, first: number, tolerance = 0.02): 'rising' | 'steady' | 'declining' {
  if (latest - first > tolerance * Math.abs(first || 1)) {
    return 'rising';
  }
  if (first - latest > tolerance * Math.abs(first || 1)) {
    return 'declining';
  }
  return 'steady';
}
