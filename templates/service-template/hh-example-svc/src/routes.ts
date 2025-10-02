import type { FastifyInstance } from 'fastify';

import { badRequestError } from '@hh/common';

export async function registerRoutes(app: FastifyInstance): Promise<void> {
  app.get('/v1/profile', async (request) => {
    if (!request.user || !request.tenant) {
      throw badRequestError('Request context is missing user or tenant information.');
    }

    return {
      requestId: request.requestContext.requestId,
      user: {
        id: request.user.uid,
        email: request.user.email,
        orgId: request.user.orgId
      },
      tenant: {
        id: request.tenant.id,
        name: request.tenant.name
      }
    };
  });

  app.post('/v1/echo', async (request, reply) => {
    const body = request.body as Record<string, unknown> | undefined;
    if (!body || typeof body !== 'object') {
      throw badRequestError('Request body must be a JSON object.');
    }

    return reply.code(201).send({
      requestId: request.requestContext.requestId,
      data: body
    });
  });
}
