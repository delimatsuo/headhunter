import type { FastifyInstance } from 'fastify';
import type { HealthResponse } from '../types';

interface State {
  isReady: boolean;
  modelLoaded: boolean;
}

export async function healthRoutes(server: FastifyInstance, state: State): Promise<void> {
  // GET /health - Basic liveness check
  server.get<{ Reply: HealthResponse }>('/health', {
    schema: {
      response: {
        200: {
          type: 'object',
          properties: {
            status: { type: 'string', enum: ['ok', 'degraded', 'error'] },
            service: { type: 'string' },
            modelLoaded: { type: 'boolean' },
            timestamp: { type: 'string' }
          },
          required: ['status', 'service', 'modelLoaded', 'timestamp']
        }
      }
    }
  }, async (_request, reply) => {
    const response: HealthResponse = {
      status: state.modelLoaded ? 'ok' : 'degraded',
      service: 'hh-trajectory-svc',
      modelLoaded: state.modelLoaded,
      timestamp: new Date().toISOString()
    };

    return reply.code(200).send(response);
  });
}
