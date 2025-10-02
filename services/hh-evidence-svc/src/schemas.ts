import type { FastifySchema } from 'fastify';

const evidenceSectionSchema = {
  type: 'object',
  properties: {
    id: { type: 'string' },
    title: { type: 'string' },
    highlights: {
      type: 'array',
      items: { type: 'string' }
    },
    score: { type: 'number' },
    confidence: { type: 'number' },
    lastUpdated: { type: 'string' }
  },
  additionalProperties: false
} satisfies FastifySchema['response'];

export const evidenceRouteSchema: FastifySchema = {
  params: {
    type: 'object',
    required: ['candidateId'],
    properties: {
      candidateId: {
        type: 'string',
        minLength: 3,
        maxLength: 128,
        pattern: '^[a-zA-Z0-9_-]+$'
      }
    }
  },
  querystring: {
    type: 'object',
    properties: {
      sections: {
        type: 'string',
      }
    }
  },
  response: {
    200: {
      type: 'object',
      required: ['sections', 'metadata'],
      properties: {
        sections: {
          type: 'object',
          additionalProperties: evidenceSectionSchema
        },
        metadata: {
          type: 'object',
          required: ['candidateId', 'orgId', 'sectionsAvailable', 'cacheHit'],
          properties: {
            candidateId: { type: 'string' },
            orgId: { type: 'string' },
            locale: { type: 'string' },
            version: { type: 'string' },
            generatedAt: { type: 'string' },
            redacted: { type: 'boolean' },
            cacheHit: { type: 'boolean' },
            sectionsAvailable: {
              type: 'array',
              items: { type: 'string' }
            }
          },
          additionalProperties: true
        }
      },
      additionalProperties: false
    },
    404: {
      type: 'object',
      required: ['code', 'message'],
      properties: {
        code: { type: 'string' },
        message: { type: 'string' }
      }
    }
  }
};

export const healthSchema: FastifySchema = {
};
