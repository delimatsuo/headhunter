import type { FastifyInstance } from 'fastify';
import type { PredictRequest, PredictResponse } from '../types';
import { TrajectoryPredictor } from '../inference';

interface State {
  isReady: boolean;
  modelLoaded: boolean;
  predictor?: TrajectoryPredictor;
}

export async function predictRoutes(server: FastifyInstance, state: State): Promise<void> {
  // GET /predict/health - Predictor health check
  server.get('/predict/health', async (_request, reply) => {
    const isInitialized = state.predictor?.isInitialized() ?? false;

    const health = {
      initialized: isInitialized,
      modelLoaded: state.modelLoaded,
      status: isInitialized ? 'ready' : 'initializing',
    };

    return reply.code(isInitialized ? 200 : 503).send(health);
  });

  // POST /predict - Predict career trajectory
  server.post<{ Body: PredictRequest; Reply: PredictResponse }>('/predict', {
    schema: {
      body: {
        type: 'object',
        properties: {
          candidateId: { type: 'string' },
          titleSequence: {
            type: 'array',
            items: { type: 'string' },
            minItems: 1
          },
          tenureDurations: {
            type: 'array',
            items: { type: 'number' }
          }
        },
        required: ['candidateId', 'titleSequence']
      },
      response: {
        200: {
          type: 'object',
          properties: {
            candidateId: { type: 'string' },
            prediction: {
              type: 'object',
              properties: {
                nextRole: { type: 'string' },
                nextRoleConfidence: { type: 'number' },
                tenureMonths: {
                  type: 'object',
                  properties: {
                    min: { type: 'number' },
                    max: { type: 'number' }
                  },
                  required: ['min', 'max']
                },
                hireability: { type: 'number' },
                lowConfidence: { type: 'boolean' },
                uncertaintyReason: { type: 'string' }
              },
              required: ['nextRole', 'nextRoleConfidence', 'tenureMonths', 'hireability', 'lowConfidence']
            },
            timestamp: { type: 'string' },
            modelVersion: { type: 'string' }
          },
          required: ['candidateId', 'prediction', 'timestamp', 'modelVersion']
        }
      }
    }
  }, async (request, reply) => {
    const startTime = Date.now();

    // Check if predictor is initialized
    if (!state.predictor || !state.predictor.isInitialized()) {
      return reply.code(503).send({
        error: 'Service not ready',
        message: 'ONNX model not loaded yet'
      } as any);
    }

    const { candidateId, titleSequence } = request.body;

    try {
      // Run ML inference
      const prediction = await state.predictor.predict(request.body);

      const response: PredictResponse = {
        candidateId,
        prediction,
        timestamp: new Date().toISOString(),
        modelVersion: 'trajectory-lstm-v1.0.0',
      };

      const duration = Date.now() - startTime;
      request.log.info({
        candidateId,
        titleSequenceLength: titleSequence.length,
        nextRole: prediction.nextRole,
        confidence: prediction.nextRoleConfidence,
        lowConfidence: prediction.lowConfidence,
        duration,
      }, 'Trajectory prediction completed');

      return reply.code(200).send(response);
    } catch (error) {
      const duration = Date.now() - startTime;
      request.log.error({
        candidateId,
        error: error instanceof Error ? error.message : String(error),
        duration,
      }, 'Trajectory prediction failed');

      return reply.code(500).send({
        error: 'Prediction failed',
        message: error instanceof Error ? error.message : 'Unknown error'
      } as any);
    }
  });
}
