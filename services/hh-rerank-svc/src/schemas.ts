import type { FastifySchema } from 'fastify';

const candidateFeaturesSchema = {
  type: 'object',
  additionalProperties: true,
  properties: {
    vectorScore: { type: 'number' },
    textScore: { type: 'number' },
    confidence: { type: 'number' },
    yearsExperience: { type: 'number', minimum: 0, maximum: 80 },
    currentTitle: { type: 'string', maxLength: 500 },
    location: { type: 'string', maxLength: 500 },
    matchReasons: {
      type: 'array',
      items: { type: 'string', maxLength: 500 },
      maxItems: 10
    },
    skills: {
      type: 'array',
      items: { type: 'string', maxLength: 200 },
      maxItems: 50
    },
    metadata: {
      type: 'object',
      additionalProperties: true
    }
  }
} as const;

const candidateSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['candidateId'],
  properties: {
    candidateId: { type: 'string', minLength: 1, maxLength: 128 },
    highlights: {
      type: 'array',
      items: { type: 'string', maxLength: 1000 },
      maxItems: 20
    },
    initialScore: { type: 'number' },
    features: candidateFeaturesSchema,
    payload: {
      type: 'object',
      additionalProperties: true
    }
  }
} as const;

/**
 * Schema for match rationale generation endpoint.
 * @see TRNS-03
 */
export const matchRationaleSchema: FastifySchema = {
  body: {
    type: 'object',
    additionalProperties: false,
    required: ['jobDescription', 'candidateSummary', 'topSignals'],
    properties: {
      jobDescription: { type: 'string', minLength: 10, maxLength: 10000 },
      candidateSummary: { type: 'string', minLength: 1, maxLength: 5000 },
      topSignals: {
        type: 'array',
        items: {
          type: 'object',
          required: ['name', 'score'],
          properties: {
            name: { type: 'string', minLength: 1, maxLength: 100 },
            score: { type: 'number', minimum: 0, maximum: 1 }
          }
        },
        minItems: 0,
        maxItems: 10
      }
    }
  },
  response: {
    200: {
      type: 'object',
      required: ['summary', 'keyStrengths', 'signalHighlights'],
      properties: {
        summary: { type: 'string' },
        keyStrengths: {
          type: 'array',
          items: { type: 'string' }
        },
        signalHighlights: {
          type: 'array',
          items: {
            type: 'object',
            required: ['signal', 'score', 'reason'],
            properties: {
              signal: { type: 'string' },
              score: { type: 'number' },
              reason: { type: 'string' }
            }
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

export const rerankSchema: FastifySchema = {
  body: {
    type: 'object',
    additionalProperties: false,
    required: ['jobDescription', 'candidates'],
    properties: {
      jobDescription: { type: 'string', minLength: 20, maxLength: 20000 },
      jdHash: { type: 'string', minLength: 8, maxLength: 64 },
      docsetHash: { type: 'string', minLength: 8, maxLength: 64 },
      query: { type: 'string', maxLength: 6000 },
      candidates: {
        type: 'array',
        items: candidateSchema,
        minItems: 1,
        maxItems: 200
      },
      limit: { type: 'integer', minimum: 1, maximum: 200 },
      disableCache: { type: 'boolean' },
      includeReasons: { type: 'boolean' },
      requestMetadata: {
        type: 'object',
        additionalProperties: true
      }
    }
  },
  response: {
    200: {
      type: 'object',
      required: ['results', 'cacheHit', 'usedFallback', 'requestId', 'timings'],
      properties: {
        results: {
          type: 'array',
          items: {
            type: 'object',
            required: ['candidateId', 'rank', 'score', 'reasons'],
            properties: {
              candidateId: { type: 'string' },
              rank: { type: 'integer', minimum: 1 },
              score: { type: 'number' },
              reasons: {
                type: 'array',
                items: { type: 'string' },
                maxItems: 5
              },
              payload: { type: 'object', additionalProperties: true }
            }
          }
        },
        cacheHit: { type: 'boolean' },
        usedFallback: { type: 'boolean' },
        requestId: { type: 'string', minLength: 8 },
        timings: {
          type: 'object',
          required: ['totalMs'],
          properties: {
            totalMs: { type: 'integer', minimum: 0 },
            togetherMs: { type: 'integer', minimum: 0 },
            promptMs: { type: 'integer', minimum: 0 },
            cacheMs: { type: 'integer', minimum: 0 }
          }
        },
        metadata: { type: 'object', additionalProperties: true }
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
