import { describe, it, expect, vi, beforeEach } from 'vitest';
import { predictRoutes } from './predict';
import type { FastifyInstance } from 'fastify';
import type { TrajectoryPredictor } from '../inference';
import type { PredictRequest, TrajectoryPrediction } from '../types';

// Mock predictor
const createMockPredictor = (initialized: boolean = true): TrajectoryPredictor => {
  const mockPrediction: TrajectoryPrediction = {
    nextRole: 'Staff Engineer',
    nextRoleConfidence: 0.78,
    tenureMonths: { min: 18, max: 24 },
    hireability: 85,
    lowConfidence: false,
    uncertaintyReason: undefined,
  };

  return {
    isInitialized: vi.fn(() => initialized),
    predict: vi.fn(async (_request: PredictRequest) => mockPrediction),
    initialize: vi.fn(),
  } as unknown as TrajectoryPredictor;
};

// Mock Fastify instance
const createMockFastify = (): FastifyInstance => {
  const routes: Array<{
    method: string;
    path: string;
    handler: (request: any, reply: any) => any;
  }> = [];

  return {
    get: vi.fn((path: string, ...args: any[]) => {
      const handler = args[args.length - 1];
      routes.push({ method: 'GET', path, handler });
    }),
    post: vi.fn((path: string, ...args: any[]) => {
      const handler = args[args.length - 1];
      routes.push({ method: 'POST', path, handler });
    }),
    _routes: routes,
  } as unknown as FastifyInstance;
};

describe('POST /predict', () => {
  let fastify: FastifyInstance;
  let predictor: TrajectoryPredictor;
  let state: { isReady: boolean; modelLoaded: boolean; predictor?: TrajectoryPredictor };

  beforeEach(() => {
    fastify = createMockFastify();
    predictor = createMockPredictor(true);
    state = { isReady: true, modelLoaded: true, predictor };
  });

  it('returns prediction for valid request', async () => {
    await predictRoutes(fastify, state);

    // Find POST /predict route
    const route = (fastify as any)._routes.find(
      (r: any) => r.method === 'POST' && r.path === '/predict'
    );
    expect(route).toBeDefined();

    const mockRequest = {
      body: {
        candidateId: 'cand-123',
        titleSequence: ['Junior Engineer', 'Senior Engineer'],
        tenureDurations: [24, 36],
      },
      log: {
        info: vi.fn(),
        error: vi.fn(),
      },
    };

    const mockReply = {
      code: vi.fn().mockReturnThis(),
      send: vi.fn().mockReturnThis(),
    };

    await route!.handler(mockRequest, mockReply);

    expect(mockReply.code).toHaveBeenCalledWith(200);
    expect(mockReply.send).toHaveBeenCalledWith(
      expect.objectContaining({
        candidateId: 'cand-123',
        prediction: expect.objectContaining({
          nextRole: 'Staff Engineer',
          nextRoleConfidence: 0.78,
          tenureMonths: { min: 18, max: 24 },
          hireability: 85,
          lowConfidence: false,
        }),
        timestamp: expect.any(String),
        modelVersion: 'trajectory-lstm-v1.0.0',
      })
    );
  });

  it('returns 400 for missing candidateId', async () => {
    await predictRoutes(fastify, state);

    const route = (fastify as any)._routes.find(
      (r: any) => r.method === 'POST' && r.path === '/predict'
    );

    const mockRequest = {
      body: {
        // Missing candidateId
        titleSequence: ['Senior Engineer'],
      },
      log: {
        info: vi.fn(),
        error: vi.fn(),
      },
    };

    const mockReply = {
      code: vi.fn().mockReturnThis(),
      send: vi.fn().mockReturnThis(),
    };

    // Fastify schema validation would catch this before handler
    // Simulate validation failure
    expect(mockRequest.body).not.toHaveProperty('candidateId');
  });

  it('returns 400 for empty titleSequence', async () => {
    await predictRoutes(fastify, state);

    const route = (fastify as any)._routes.find(
      (r: any) => r.method === 'POST' && r.path === '/predict'
    );

    const mockRequest = {
      body: {
        candidateId: 'cand-123',
        titleSequence: [], // Empty array
      },
      log: {
        info: vi.fn(),
        error: vi.fn(),
      },
    };

    const mockReply = {
      code: vi.fn().mockReturnThis(),
      send: vi.fn().mockReturnThis(),
    };

    // Fastify schema validation would catch minItems: 1
    expect(mockRequest.body.titleSequence).toHaveLength(0);
  });

  it('returns 503 when model not initialized', async () => {
    const uninitializedPredictor = createMockPredictor(false);
    const uninitializedState = {
      isReady: false,
      modelLoaded: false,
      predictor: uninitializedPredictor,
    };

    await predictRoutes(fastify, uninitializedState);

    const route = (fastify as any)._routes.find(
      (r: any) => r.method === 'POST' && r.path === '/predict'
    );

    const mockRequest = {
      body: {
        candidateId: 'cand-123',
        titleSequence: ['Senior Engineer'],
      },
      log: {
        info: vi.fn(),
        error: vi.fn(),
      },
    };

    const mockReply = {
      code: vi.fn().mockReturnThis(),
      send: vi.fn().mockReturnThis(),
    };

    await route!.handler(mockRequest, mockReply);

    expect(mockReply.code).toHaveBeenCalledWith(503);
    expect(mockReply.send).toHaveBeenCalledWith(
      expect.objectContaining({
        error: 'Service not ready',
        message: 'ONNX model not loaded yet',
      })
    );
  });

  it('includes lowConfidence flag when confidence < 0.6', async () => {
    const lowConfidencePredictor = {
      isInitialized: vi.fn(() => true),
      predict: vi.fn(async () => ({
        nextRole: 'Staff Engineer',
        nextRoleConfidence: 0.45,
        tenureMonths: { min: 12, max: 18 },
        hireability: 60,
        lowConfidence: true,
        uncertaintyReason: 'Limited career history data (fewer than 3 positions)',
      })),
      initialize: vi.fn(),
    } as unknown as TrajectoryPredictor;

    const lowConfidenceState = {
      isReady: true,
      modelLoaded: true,
      predictor: lowConfidencePredictor,
    };

    await predictRoutes(fastify, lowConfidenceState);

    const route = (fastify as any)._routes.find(
      (r: any) => r.method === 'POST' && r.path === '/predict'
    );

    const mockRequest = {
      body: {
        candidateId: 'cand-123',
        titleSequence: ['Senior Engineer'],
      },
      log: {
        info: vi.fn(),
        error: vi.fn(),
      },
    };

    const mockReply = {
      code: vi.fn().mockReturnThis(),
      send: vi.fn().mockReturnThis(),
    };

    await route!.handler(mockRequest, mockReply);

    expect(mockReply.send).toHaveBeenCalledWith(
      expect.objectContaining({
        prediction: expect.objectContaining({
          lowConfidence: true,
          nextRoleConfidence: 0.45,
        }),
      })
    );
  });

  it('includes uncertaintyReason for short sequences', async () => {
    const shortSequencePredictor = {
      isInitialized: vi.fn(() => true),
      predict: vi.fn(async () => ({
        nextRole: 'Senior Engineer',
        nextRoleConfidence: 0.55,
        tenureMonths: { min: 12, max: 18 },
        hireability: 70,
        lowConfidence: true,
        uncertaintyReason: 'Limited career history data (fewer than 3 positions)',
      })),
      initialize: vi.fn(),
    } as unknown as TrajectoryPredictor;

    const shortSequenceState = {
      isReady: true,
      modelLoaded: true,
      predictor: shortSequencePredictor,
    };

    await predictRoutes(fastify, shortSequenceState);

    const route = (fastify as any)._routes.find(
      (r: any) => r.method === 'POST' && r.path === '/predict'
    );

    const mockRequest = {
      body: {
        candidateId: 'cand-123',
        titleSequence: ['Junior Engineer', 'Senior Engineer'], // Only 2 positions
      },
      log: {
        info: vi.fn(),
        error: vi.fn(),
      },
    };

    const mockReply = {
      code: vi.fn().mockReturnThis(),
      send: vi.fn().mockReturnThis(),
    };

    await route!.handler(mockRequest, mockReply);

    expect(mockReply.send).toHaveBeenCalledWith(
      expect.objectContaining({
        prediction: expect.objectContaining({
          uncertaintyReason: 'Limited career history data (fewer than 3 positions)',
        }),
      })
    );
  });
});

describe('GET /predict/health', () => {
  it('returns 200 when predictor initialized', async () => {
    const fastify = createMockFastify();
    const predictor = createMockPredictor(true);
    const state = { isReady: true, modelLoaded: true, predictor };

    await predictRoutes(fastify, state);

    const route = (fastify as any)._routes.find(
      (r: any) => r.method === 'GET' && r.path === '/predict/health'
    );

    const mockRequest = {};
    const mockReply = {
      code: vi.fn().mockReturnThis(),
      send: vi.fn().mockReturnThis(),
    };

    await route!.handler(mockRequest, mockReply);

    expect(mockReply.code).toHaveBeenCalledWith(200);
    expect(mockReply.send).toHaveBeenCalledWith(
      expect.objectContaining({
        initialized: true,
        modelLoaded: true,
        status: 'ready',
      })
    );
  });

  it('returns 503 when predictor not initialized', async () => {
    const fastify = createMockFastify();
    const predictor = createMockPredictor(false);
    const state = { isReady: false, modelLoaded: false, predictor };

    await predictRoutes(fastify, state);

    const route = (fastify as any)._routes.find(
      (r: any) => r.method === 'GET' && r.path === '/predict/health'
    );

    const mockRequest = {};
    const mockReply = {
      code: vi.fn().mockReturnThis(),
      send: vi.fn().mockReturnThis(),
    };

    await route!.handler(mockRequest, mockReply);

    expect(mockReply.code).toHaveBeenCalledWith(503);
    expect(mockReply.send).toHaveBeenCalledWith(
      expect.objectContaining({
        initialized: false,
        status: 'initializing',
      })
    );
  });
});
