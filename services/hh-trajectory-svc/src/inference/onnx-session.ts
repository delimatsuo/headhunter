/**
 * ONNX session singleton for efficient model loading and inference.
 * Prevents repeated model initialization across requests.
 */
import * as ort from 'onnxruntime-node';

export class ONNXSession {
  private static instance: ort.InferenceSession | null = null;
  private static initPromise: Promise<ort.InferenceSession> | null = null;
  private static modelPath: string | null = null;

  /**
   * Get or create ONNX session singleton.
   *
   * @param modelPath - Path to ONNX model file
   * @returns Promise resolving to InferenceSession
   */
  static async getInstance(modelPath: string): Promise<ort.InferenceSession> {
    // Return cached instance if model path matches
    if (this.instance && this.modelPath === modelPath) {
      return this.instance;
    }

    // Return in-flight initialization if exists
    if (this.initPromise && this.modelPath === modelPath) {
      return this.initPromise;
    }

    // Create new session
    this.modelPath = modelPath;
    this.initPromise = this.createSession(modelPath);

    try {
      this.instance = await this.initPromise;
      return this.instance;
    } catch (error) {
      // Reset on failure to allow retry
      this.initPromise = null;
      this.instance = null;
      this.modelPath = null;
      throw error;
    }
  }

  /**
   * Create ONNX inference session with optimized configuration.
   *
   * @param modelPath - Path to ONNX model file
   * @returns Promise resolving to InferenceSession
   */
  private static async createSession(modelPath: string): Promise<ort.InferenceSession> {
    console.log(`[ONNXSession] Loading model from ${modelPath}...`);

    const options: ort.InferenceSession.SessionOptions = {
      executionProviders: ['cpu'],
      graphOptimizationLevel: 'all',
      enableCpuMemArena: true,
      enableMemPattern: true,
      intraOpNumThreads: 4,
      // Log severity: 0=verbose, 1=info, 2=warning, 3=error, 4=fatal
      logSeverityLevel: 2,
    };

    const startTime = Date.now();
    const session = await ort.InferenceSession.create(modelPath, options);
    const duration = Date.now() - startTime;

    console.log(`[ONNXSession] Model loaded successfully in ${duration}ms`);
    console.log(`[ONNXSession] Input names: ${session.inputNames.join(', ')}`);
    console.log(`[ONNXSession] Output names: ${session.outputNames.join(', ')}`);

    return session;
  }

  /**
   * Check if session is initialized.
   *
   * @returns True if session exists
   */
  static isInitialized(): boolean {
    return this.instance !== null;
  }

  /**
   * Get model path of current session.
   *
   * @returns Model path or null if not initialized
   */
  static getModelPath(): string | null {
    return this.modelPath;
  }

  /**
   * Dispose of session and reset singleton.
   * Used for graceful shutdown.
   */
  static async dispose(): Promise<void> {
    if (this.instance) {
      console.log('[ONNXSession] Disposing model...');
      // ONNX Runtime Node doesn't expose dispose method, session is GC'd
      this.instance = null;
      this.initPromise = null;
      this.modelPath = null;
      console.log('[ONNXSession] Model disposed');
    }
  }
}
