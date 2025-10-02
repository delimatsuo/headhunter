import type { FastifySchema } from 'fastify';

const occupationSummarySchema = {
  type: 'object',
  required: ['ecoId', 'title', 'locale', 'aliases', 'score', 'source'],
  properties: {
    ecoId: { type: 'string' },
    title: { type: 'string' },
    locale: { type: 'string' },
    country: { type: 'string' },
    aliases: {
      type: 'array',
      items: { type: 'string' }
    },
    score: { type: 'number' },
    source: { type: 'string', enum: ['title', 'alias'] }
  },
  additionalProperties: false
};

export const occupationSearchSchema: FastifySchema = {
  querystring: {
    type: 'object',
    required: ['title'],
    properties: {
      title: { type: 'string', minLength: 2, maxLength: 120 },
      locale: { type: 'string', minLength: 2, maxLength: 10 },
      country: { type: 'string', minLength: 2, maxLength: 3 },
      limit: { type: 'integer', minimum: 1, maximum: 50 },
      useCache: { type: 'string', enum: ['true', 'false'] }
    }
  },
  response: {
    200: {
      type: 'object',
      required: ['results', 'total', 'query', 'cacheHit'],
      properties: {
        results: {
          type: 'array',
          items: occupationSummarySchema
        },
        total: { type: 'integer' },
        cacheHit: { type: 'boolean' },
        query: {
          type: 'object',
          required: ['title', 'locale', 'country', 'limit'],
          properties: {
            title: { type: 'string' },
            locale: { type: 'string' },
            country: { type: 'string' },
            limit: { type: 'integer' }
          }
        }
      },
      additionalProperties: false
    }
  }
};

export const occupationDetailSchema: FastifySchema = {
  params: {
    type: 'object',
    required: ['ecoId'],
    properties: {
      ecoId: {
        type: 'string',
        minLength: 3,
        maxLength: 64,
        pattern: '^[A-Za-z0-9_-]+$'
      }
    }
  },
  querystring: {
    type: 'object',
    properties: {
      locale: { type: 'string', minLength: 2, maxLength: 10 },
      country: { type: 'string', minLength: 2, maxLength: 3 }
    }
  },
  response: {
    200: {
      type: 'object',
      required: ['occupation', 'cacheHit'],
      properties: {
        cacheHit: { type: 'boolean' },
        occupation: {
          type: 'object',
          required: ['ecoId', 'title', 'locale', 'aliases', 'crosswalk'],
          properties: {
            ecoId: { type: 'string' },
            title: { type: 'string' },
            locale: { type: 'string' },
            aliases: {
              type: 'array',
              items: { type: 'string' }
            },
            industries: {
              type: 'array',
              items: { type: 'string' }
            },
            salaryInsights: {
              type: 'object'
            },
            crosswalk: {
              type: 'object',
              properties: {
                cbo: {
                  type: 'array',
                  items: { type: 'string' }
                },
                esco: {
                  type: 'array',
                  items: { type: 'string' }
                },
                onet: {
                  type: 'array',
                  items: { type: 'string' }
                }
              },
              additionalProperties: false
            },
            template: {
              type: 'object',
              properties: {
                requiredSkills: {
                  type: 'array',
                  items: { type: 'string' }
                },
                preferredSkills: {
                  type: 'array',
                  items: { type: 'string' }
                },
                yearsExperienceMin: { type: 'number' },
                yearsExperienceMax: { type: 'number' }
              },
              additionalProperties: false
            }
          },
          additionalProperties: false
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

export const ecoHealthSchema: FastifySchema = {
};
