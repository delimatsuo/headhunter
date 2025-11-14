import type { FastifySchema } from 'fastify';

const embeddingVectorSchema = {
  type: 'array',
  minItems: 8,
  maxItems: 4096,
  items: { type: 'number' }
} as const;

const skillArraySchema = {
  type: 'array',
  minItems: 1,
  maxItems: 50,
  items: { type: 'string', minLength: 1 }
} as const;

const locationArraySchema = {
  type: 'array',
  minItems: 1,
  maxItems: 50,
  items: { type: 'string', minLength: 1 }
} as const;

export const hybridSearchSchema: FastifySchema = {
  body: {
    type: 'object',
    additionalProperties: true,
    anyOf: [
      { required: ['query'] },
      { required: ['embedding'] },
      { required: ['jobDescription'] }
    ],
    properties: {
      query: { type: 'string', minLength: 0, maxLength: 6000 },
      embedding: embeddingVectorSchema,
      jdHash: { type: 'string', minLength: 8, maxLength: 64 },
      jobDescription: { type: 'string', maxLength: 20000 },
      limit: { type: 'integer', minimum: 1, maximum: 200 },
      offset: { type: 'integer', minimum: 0, maximum: 200 },
      includeDebug: { type: 'boolean' },
      filters: {
        type: 'object',
        additionalProperties: true,
        properties: {
          skills: skillArraySchema,
          locations: locationArraySchema,
          industries: {
            type: 'array',
            minItems: 1,
            maxItems: 20,
            items: { type: 'string', minLength: 1 }
          },
          seniorityLevels: {
            type: 'array',
            minItems: 1,
            maxItems: 20,
            items: { type: 'string', minLength: 1 }
          },
          minExperienceYears: { type: 'number', minimum: 0, maximum: 60 },
          maxExperienceYears: { type: 'number', minimum: 0, maximum: 60 },
          metadata: { type: 'object', additionalProperties: true }
        }
      }
    }
  },
  response: {
    200: {
      type: 'object',
      required: ['results', 'total', 'cacheHit', 'requestId', 'timings'],
      properties: {
        results: {
          type: 'array',
          items: {
            type: 'object',
            required: ['candidateId', 'score', 'vectorScore', 'textScore', 'confidence', 'matchReasons'],
            properties: {
              candidateId: { type: 'string', minLength: 1 },
              score: { type: 'number' },
              vectorScore: { type: 'number' },
              textScore: { type: 'number' },
              confidence: { type: 'number', minimum: 0, maximum: 1.5 },
              fullName: { type: 'string' },
              title: { type: 'string' },
              headline: { type: 'string' },
              location: { type: 'string' },
              industries: {
                type: 'array',
                items: { type: 'string' }
              },
              yearsExperience: { type: 'number', minimum: 0, maximum: 80 },
              skills: {
                type: 'array',
                items: {
                  type: 'object',
                  required: ['name', 'weight'],
                  properties: {
                    name: { type: 'string' },
                    weight: { type: 'number' }
                  }
                }
              },
              matchReasons: {
                type: 'array',
                items: { type: 'string' }
              },
              metadata: { type: 'object', additionalProperties: true }
            }
          }
        },
        total: { type: 'integer', minimum: 0 },
        cacheHit: { type: 'boolean' },
        requestId: { type: 'string', minLength: 8 },
        timings: {
          type: 'object',
          required: ['totalMs'],
          properties: {
            totalMs: { type: 'integer', minimum: 0 },
            embeddingMs: { type: 'integer', minimum: 0 },
            retrievalMs: { type: 'integer', minimum: 0 },
            rankingMs: { type: 'integer', minimum: 0 },
            rerankMs: { type: 'integer', minimum: 0 },
            cacheMs: { type: 'integer', minimum: 0 }
          }
        },
        metadata: { type: 'object', additionalProperties: true },
        debug: { type: 'object', additionalProperties: true }
      }
    },
    400: {
      type: 'object',
      required: ['code', 'message'],
      properties: {
        code: { type: 'string' },
        message: { type: 'string' },
        details: { type: 'object', additionalProperties: true }
      }
    }
  }
};

/**
 * Simplified candidate search schema for /v1/search/candidates endpoint.
 * Provides a user-friendly API that wraps the hybrid search functionality.
 */
export const candidateSearchSchema: FastifySchema = {
  body: {
    type: 'object',
    required: ['query'],
    additionalProperties: true,
    properties: {
      query: { type: 'string', minLength: 1, maxLength: 6000 },
      limit: { type: 'integer', minimum: 1, maximum: 100 },
      includeMetadata: { type: 'boolean' },
      filters: {
        type: 'object',
        additionalProperties: true,
        properties: {
          skills: skillArraySchema,
          locations: locationArraySchema,
          industries: {
            type: 'array',
            minItems: 1,
            maxItems: 20,
            items: { type: 'string', minLength: 1 }
          },
          seniorityLevels: {
            type: 'array',
            minItems: 1,
            maxItems: 20,
            items: { type: 'string', minLength: 1 }
          },
          minExperienceYears: { type: 'number', minimum: 0, maximum: 60 },
          maxExperienceYears: { type: 'number', minimum: 0, maximum: 60 }
        }
      }
    }
  },
  response: {
    200: {
      type: 'object',
      required: ['candidates', 'total', 'requestId'],
      properties: {
        candidates: {
          type: 'array',
          items: {
            type: 'object',
            required: ['id', 'score'],
            properties: {
              id: { type: 'string', minLength: 1 },
              entityId: { type: 'string', minLength: 1 },
              score: { type: 'number' },
              similarity: { type: 'number' },
              fullName: { type: 'string' },
              title: { type: 'string' },
              headline: { type: 'string' },
              location: { type: 'string' },
              industries: { type: 'array', items: { type: 'string' } },
              yearsExperience: { type: 'number' },
              skills: {
                type: 'array',
                items: {
                  anyOf: [
                    { type: 'string' },
                    {
                      type: 'object',
                      properties: {
                        name: { type: 'string' },
                        weight: { type: 'number' }
                      }
                    }
                  ]
                }
              },
              metadata: { type: 'object', additionalProperties: true }
            }
          }
        },
        total: { type: 'integer', minimum: 0 },
        requestId: { type: 'string', minLength: 8 },
        cacheHit: { type: 'boolean' },
        timings: {
          type: 'object',
          properties: {
            totalMs: { type: 'integer', minimum: 0 },
            embeddingMs: { type: 'integer', minimum: 0 },
            retrievalMs: { type: 'integer', minimum: 0 },
            rankingMs: { type: 'integer', minimum: 0 }
          }
        }
      }
    },
    400: {
      type: 'object',
      required: ['code', 'message'],
      properties: {
        code: { type: 'string' },
        message: { type: 'string' },
        details: { type: 'object', additionalProperties: true }
      }
    }
  }
};
