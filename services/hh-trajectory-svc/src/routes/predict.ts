import type { FastifyInstance } from 'fastify';
import type { PredictRequest, PredictResponse, TrajectoryPrediction } from '../types';

interface State {
  isReady: boolean;
  modelLoaded: boolean;
}

export async function predictRoutes(server: FastifyInstance, state: State): Promise<void> {
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
    // Check if model is loaded
    if (!state.modelLoaded) {
      return reply.code(503).send({
        error: 'Service not ready',
        message: 'ONNX model not loaded yet'
      } as any);
    }

    const { candidateId, titleSequence } = request.body;

    // Stub prediction response (actual ONNX inference in Plan 02)
    const stubPrediction: TrajectoryPrediction = {
      nextRole: 'Senior Engineer',
      nextRoleConfidence: 0.75,
      tenureMonths: {
        min: 18,
        max: 36
      },
      hireability: 78,
      lowConfidence: false
    };

    const response: PredictResponse = {
      candidateId,
      prediction: stubPrediction,
      timestamp: new Date().toISOString(),
      modelVersion: 'stub-v0.1.0'
    };

    request.log.info({
      candidateId,
      titleSequenceLength: titleSequence.length,
      prediction: stubPrediction
    }, 'Trajectory prediction (stub)');

    return reply.code(200).send(response);
  });
}
