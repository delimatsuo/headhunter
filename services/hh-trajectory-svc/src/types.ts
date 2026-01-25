/**
 * Trajectory prediction result from ML model
 */
export interface TrajectoryPrediction {
  /** Predicted next job title/role */
  nextRole: string;
  /** Confidence score for next role prediction (0-1) */
  nextRoleConfidence: number;
  /** Estimated tenure in months (range) */
  tenureMonths: {
    min: number;
    max: number;
  };
  /** Hireability score (0-100) */
  hireability: number;
  /** Flag indicating prediction has low confidence */
  lowConfidence: boolean;
  /** Reason for low confidence (if applicable) */
  uncertaintyReason?: string;
}

/**
 * Request payload for /predict endpoint
 */
export interface PredictRequest {
  /** Candidate identifier */
  candidateId: string;
  /** Sequence of job titles in chronological order */
  titleSequence: string[];
  /** Optional: Tenure durations in months for each title */
  tenureDurations?: number[];
}

/**
 * Response from /predict endpoint
 */
export interface PredictResponse {
  /** Candidate identifier */
  candidateId: string;
  /** Prediction result */
  prediction: TrajectoryPrediction;
  /** Timestamp of prediction */
  timestamp: string;
  /** Model version used for prediction */
  modelVersion: string;
}

/**
 * Shadow mode log entry comparing ML vs rule-based predictions
 */
export interface ShadowLog {
  /** Candidate identifier */
  candidateId: string;
  /** Timestamp of prediction */
  timestamp: Date;
  /** Rule-based prediction (from Phase 8 trajectory calculators) */
  ruleBasedPrediction?: {
    direction: string;
    velocity: string;
    type: string;
    fit: number;
  };
  /** ML prediction from ONNX model */
  mlPrediction: TrajectoryPrediction;
  /** Comparison metrics */
  comparison?: {
    /** Agreement between rule-based and ML (0-1) */
    agreement: number;
    /** Confidence delta */
    confidenceDelta?: number;
  };
}

/**
 * Health check response
 */
export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error';
  service: string;
  modelLoaded: boolean;
  timestamp: string;
}
