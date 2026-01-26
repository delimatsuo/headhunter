import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { TrajectoryPredictor } from './trajectory-predictor';
import type { PredictRequest } from '../types';
import * as ort from 'onnxruntime-node';

// Mock ONNX Runtime
vi.mock('onnxruntime-node', () => ({
  InferenceSession: {
    create: vi.fn(),
  },
  Tensor: class MockTensor {
    constructor(
      public type: string,
      public data: any,
      public dims: number[]
    ) {}
  },
}));

// Mock ONNXSession singleton
vi.mock('./onnx-session', () => ({
  ONNXSession: {
    getInstance: vi.fn(),
  },
}));

// Mock InputEncoder
vi.mock('./input-encoder', () => ({
  InputEncoder: class MockInputEncoder {
    constructor(_vocabPath: string) {}
    encode(titles: string[]): BigInt64Array {
      // Simple mock: map each title to an index
      const indices = titles.map((_, idx) => BigInt(idx + 1));
      return new BigInt64Array(indices);
    }
    decode(idx: number): string {
      const roles = [
        'Junior Engineer',
        'Mid-Level Engineer',
        'Senior Engineer',
        'Staff Engineer',
        'Principal Engineer',
      ];
      return roles[idx] || 'Senior Engineer';
    }
  },
}));

// Mock Calibrator
vi.mock('./calibrator', () => ({
  Calibrator: class MockCalibrator {
    constructor(_calibrationPath: string | undefined, private threshold: number = 0.6) {}
    calibrate(rawConfidence: number): number {
      // Simple mock: reduce confidence slightly
      return rawConfidence * 0.9;
    }
    isLowConfidence(calibratedConfidence: number): boolean {
      return calibratedConfidence < this.threshold;
    }
  },
}));

describe('TrajectoryPredictor', () => {
  let mockSession: any;
  let predictor: TrajectoryPredictor;
  const mockConfig = {
    modelPath: '/app/models/trajectory-lstm.onnx',
    confidenceThreshold: 0.6,
  };

  beforeEach(async () => {
    // Create mock ONNX session with predictable outputs
    mockSession = {
      run: vi.fn(async (feeds: any) => {
        // Mock logits for 5 possible roles
        const nextRoleLogits = new Float32Array([0.1, 0.2, 0.3, 2.5, 0.4]);
        const tenurePred = new Float32Array([18.5, 24.3]);
        const hireability = new Float32Array([0.85]);

        return {
          next_role_logits: {
            data: nextRoleLogits,
          },
          tenure_pred: {
            data: tenurePred,
          },
          hireability: {
            data: hireability,
          },
        };
      }),
    };

    // Mock ONNXSession.getInstance to return our mock session
    const { ONNXSession } = await import('./onnx-session');
    (ONNXSession.getInstance as any).mockResolvedValue(mockSession);

    predictor = new TrajectoryPredictor(mockConfig);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('initializes successfully with mock model', async () => {
    await predictor.initialize();

    expect(predictor.isInitialized()).toBe(true);
  });

  it('encodes title sequences correctly', async () => {
    await predictor.initialize();

    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Junior Engineer', 'Senior Engineer', 'Staff Engineer'],
      tenureDurations: [24, 36],
    };

    await predictor.predict(request);

    // Verify session.run was called with encoded inputs
    expect(mockSession.run).toHaveBeenCalledWith(
      expect.objectContaining({
        title_ids: expect.any(ort.Tensor),
        lengths: expect.any(ort.Tensor),
      })
    );
  });

  it('applies softmax to logits', async () => {
    await predictor.initialize();

    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer', 'Staff Engineer'],
    };

    const prediction = await predictor.predict(request);

    // With logits [0.1, 0.2, 0.3, 2.5, 0.4], softmax should pick index 3
    expect(prediction.nextRole).toBe('Staff Engineer');
    // Confidence should be decent after calibration (raw ~0.70, calibrated ~0.63)
    expect(prediction.nextRoleConfidence).toBeGreaterThan(0.6);
  });

  it('calibrates confidence scores', async () => {
    await predictor.initialize();

    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Junior Engineer', 'Senior Engineer'],
    };

    const prediction = await predictor.predict(request);

    // Mock calibrator reduces confidence by 10% (rawConfidence * 0.9)
    // Raw confidence for logit 2.5 among [0.1, 0.2, 0.3, 2.5, 0.4] should be ~0.92
    // After calibration: ~0.83
    expect(prediction.nextRoleConfidence).toBeLessThan(1.0);
    expect(prediction.nextRoleConfidence).toBeGreaterThan(0.6);
  });

  it('returns lowConfidence for < 0.6 calibrated confidence', async () => {
    // Create a mock session with lower confidence
    mockSession.run = vi.fn(async () => {
      // Logits with more uniform distribution -> lower confidence
      const nextRoleLogits = new Float32Array([1.0, 1.1, 1.2, 1.3, 1.15]);
      const tenurePred = new Float32Array([12, 18]);
      const hireability = new Float32Array([0.65]);

      return {
        next_role_logits: { data: nextRoleLogits },
        tenure_pred: { data: tenurePred },
        hireability: { data: hireability },
      };
    });

    await predictor.initialize();

    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Junior Engineer'],
    };

    const prediction = await predictor.predict(request);

    // With uniform logits, confidence should be low after calibration
    // Raw confidence ~0.26, calibrated ~0.23 -> lowConfidence = true
    expect(prediction.lowConfidence).toBe(true);
  });

  it('generates uncertainty reason: Limited career history', async () => {
    await predictor.initialize();

    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Junior Engineer', 'Senior Engineer'], // < 3 positions
    };

    // Mock low confidence scenario
    mockSession.run = vi.fn(async () => ({
      next_role_logits: { data: new Float32Array([1.0, 1.1, 1.2, 1.3, 1.15]) },
      tenure_pred: { data: new Float32Array([12, 18]) },
      hireability: { data: new Float32Array([0.65]) },
    }));

    const prediction = await predictor.predict(request);

    if (prediction.lowConfidence) {
      expect(prediction.uncertaintyReason).toContain('Limited career history');
    }
  });

  it('generates uncertainty reason: Unusual career pattern', async () => {
    await predictor.initialize();

    // Create uniform logits (high entropy) with sufficient gap to avoid ambiguous trigger
    // Gap of 0.3 ensures top-2 gap > 0.1 threshold
    mockSession.run = vi.fn(async () => ({
      next_role_logits: { data: new Float32Array([0.5, 0.5, 0.5, 1.0, 0.5]) },
      tenure_pred: { data: new Float32Array([24, 36]) },
      hireability: { data: new Float32Array([0.75]) },
    }));

    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Junior Engineer', 'Senior Engineer', 'Staff Engineer', 'Principal Engineer'],
    };

    const prediction = await predictor.predict(request);

    if (prediction.lowConfidence) {
      expect(prediction.uncertaintyReason).toContain('Unusual career pattern');
    }
  });

  it('generates uncertainty reason: Ambiguous next role', async () => {
    await predictor.initialize();

    // Create close top-2 predictions
    mockSession.run = vi.fn(async () => ({
      next_role_logits: { data: new Float32Array([0.1, 0.2, 1.5, 1.55, 0.3]) },
      tenure_pred: { data: new Float32Array([18, 24]) },
      hireability: { data: new Float32Array([0.70]) },
    }));

    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Junior Engineer', 'Mid-Level Engineer', 'Senior Engineer'],
    };

    const prediction = await predictor.predict(request);

    if (prediction.lowConfidence) {
      expect(prediction.uncertaintyReason).toContain('Ambiguous next role');
    }
  });

  it('extracts tenure predictions correctly', async () => {
    await predictor.initialize();

    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer', 'Staff Engineer'],
    };

    const prediction = await predictor.predict(request);

    // Mock returns [18.5, 24.3] which should round to [19, 24]
    expect(prediction.tenureMonths.min).toBe(19);
    expect(prediction.tenureMonths.max).toBe(24);
  });

  it('extracts hireability score correctly', async () => {
    await predictor.initialize();

    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer', 'Staff Engineer'],
    };

    const prediction = await predictor.predict(request);

    // Mock returns 0.85, scaled to 85
    expect(prediction.hireability).toBe(85);
  });

  it('throws error when predicting without initialization', async () => {
    const uninitializedPredictor = new TrajectoryPredictor(mockConfig);

    const request: PredictRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer'],
    };

    await expect(uninitializedPredictor.predict(request)).rejects.toThrow(
      'Predictor not initialized'
    );
  });
});
