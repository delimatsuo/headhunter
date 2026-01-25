/**
 * Trajectory predictor orchestrating ONNX inference, encoding, and calibration.
 */
import * as ort from 'onnxruntime-node';
import { ONNXSession } from './onnx-session';
import { InputEncoder } from './input-encoder';
import { Calibrator } from './calibrator';
import type { PredictRequest, TrajectoryPrediction } from '../types';
import type { TrajectoryServiceConfig } from '../config';

export class TrajectoryPredictor {
  private session: ort.InferenceSession | null = null;
  private encoder: InputEncoder | null = null;
  private calibrator: Calibrator | null = null;
  private config: TrajectoryServiceConfig;

  constructor(config: TrajectoryServiceConfig) {
    this.config = config;
  }

  /**
   * Initialize predictor by loading ONNX model, vocabulary, and calibrator.
   */
  async initialize(): Promise<void> {
    console.log('[TrajectoryPredictor] Initializing...');

    try {
      // Load ONNX model
      this.session = await ONNXSession.getInstance(this.config.modelPath);

      // Load vocabulary for input encoding
      const vocabPath = this.config.modelPath.replace('.onnx', '-vocab.json');
      this.encoder = new InputEncoder(vocabPath);

      // Load calibrator (optional - if file exists)
      const calibrationPath = this.config.modelPath.replace('.onnx', '-calibration.json');
      try {
        this.calibrator = new Calibrator(calibrationPath, this.config.confidenceThreshold);
      } catch (error) {
        console.warn('[TrajectoryPredictor] Calibration data not found, using raw confidences');
        this.calibrator = new Calibrator(undefined, this.config.confidenceThreshold);
      }

      console.log('[TrajectoryPredictor] Initialization complete');
    } catch (error) {
      console.error('[TrajectoryPredictor] Initialization failed:', error);
      throw error;
    }
  }

  /**
   * Predict career trajectory for a candidate.
   *
   * @param request - Prediction request with title sequence
   * @returns Trajectory prediction with calibrated confidence
   */
  async predict(request: PredictRequest): Promise<TrajectoryPrediction> {
    if (!this.session || !this.encoder || !this.calibrator) {
      throw new Error('Predictor not initialized');
    }

    const startTime = Date.now();

    try {
      // Encode title sequence
      const titleIds = this.encoder.encode(request.titleSequence);
      const sequenceLength = BigInt(request.titleSequence.length);

      // Create ONNX tensors
      const titleIdsTensor = new ort.Tensor('int64', titleIds, [1, titleIds.length]);
      const lengthsTensor = new ort.Tensor('int64', new BigInt64Array([sequenceLength]), [1]);

      // Run inference
      const feeds = {
        title_ids: titleIdsTensor,
        lengths: lengthsTensor,
      };

      const results = await this.session.run(feeds);

      // Extract outputs
      const nextRoleLogits = results.next_role_logits.data as Float32Array;
      const tenurePred = results.tenure_pred.data as Float32Array;
      const hireability = results.hireability.data as Float32Array;

      // Apply softmax to get probabilities
      const probs = this.softmax(Array.from(nextRoleLogits));

      // Get top prediction
      let maxProb = 0;
      let maxIdx = 0;
      for (let i = 0; i < probs.length; i++) {
        if (probs[i] > maxProb) {
          maxProb = probs[i];
          maxIdx = i;
        }
      }

      // Decode predicted role
      const nextRole = this.encoder.decode(maxIdx);

      // Calibrate confidence
      const rawConfidence = maxProb;
      const calibratedConfidence = this.calibrator.calibrate(rawConfidence);
      const lowConfidence = this.calibrator.isLowConfidence(calibratedConfidence);

      // Determine uncertainty reason if low confidence
      let uncertaintyReason: string | undefined;
      if (lowConfidence) {
        uncertaintyReason = this.getUncertaintyReason(
          request.titleSequence,
          probs,
          maxIdx
        );
      }

      // Extract tenure predictions (min, max in months)
      const tenureMin = Math.max(1, Math.round(tenurePred[0]));
      const tenureMax = Math.max(tenureMin, Math.round(tenurePred[1]));

      // Extract hireability score (convert to 0-100 scale)
      const hireabilityScore = Math.round(hireability[0] * 100);

      const duration = Date.now() - startTime;
      console.log(
        `[TrajectoryPredictor] Inference completed in ${duration}ms (raw=${rawConfidence.toFixed(3)}, calibrated=${calibratedConfidence.toFixed(3)})`
      );

      return {
        nextRole,
        nextRoleConfidence: calibratedConfidence,
        tenureMonths: {
          min: tenureMin,
          max: tenureMax,
        },
        hireability: hireabilityScore,
        lowConfidence,
        uncertaintyReason,
      };
    } catch (error) {
      console.error('[TrajectoryPredictor] Prediction failed:', error);
      throw error;
    }
  }

  /**
   * Apply softmax to logits to get probabilities.
   *
   * @param logits - Array of logit values
   * @returns Array of probabilities
   */
  private softmax(logits: number[]): number[] {
    const maxLogit = Math.max(...logits);
    const expLogits = logits.map(x => Math.exp(x - maxLogit)); // Subtract max for numerical stability
    const sumExp = expLogits.reduce((a, b) => a + b, 0);
    return expLogits.map(x => x / sumExp);
  }

  /**
   * Determine reason for low confidence prediction.
   *
   * @param titleSequence - Input title sequence
   * @param probs - Probability distribution over all roles
   * @param _predictedIdx - Index of predicted role (unused but kept for future enhancements)
   * @returns Uncertainty reason string
   */
  private getUncertaintyReason(
    titleSequence: string[],
    probs: number[],
    _predictedIdx: number
  ): string {
    // Insufficient career history
    if (titleSequence.length < 3) {
      return 'Limited career history data (fewer than 3 positions)';
    }

    // Check for ambiguous prediction (small gap between top-2)
    const sortedProbs = [...probs].sort((a, b) => b - a);
    const topProb = sortedProbs[0];
    const secondProb = sortedProbs[1];
    const gap = topProb - secondProb;

    if (gap < 0.1) {
      return 'Ambiguous next role (multiple likely paths)';
    }

    // High entropy (uniform distribution suggests uncertainty)
    const entropy = this.calculateEntropy(probs);
    const maxEntropy = Math.log(probs.length);
    const normalizedEntropy = entropy / maxEntropy;

    if (normalizedEntropy > 0.8) {
      return 'Unusual career pattern detected';
    }

    // Generic fallback
    return 'Low model confidence for this career trajectory';
  }

  /**
   * Calculate entropy of probability distribution.
   *
   * @param probs - Probability array
   * @returns Entropy value
   */
  private calculateEntropy(probs: number[]): number {
    let entropy = 0;
    for (const p of probs) {
      if (p > 0) {
        entropy -= p * Math.log(p);
      }
    }
    return entropy;
  }

  /**
   * Check if predictor is initialized.
   *
   * @returns True if all components loaded
   */
  isInitialized(): boolean {
    return this.session !== null && this.encoder !== null && this.calibrator !== null;
  }
}
