import type { FastifySchema } from 'fastify';

const refreshResponseSchema = {
  type: 'object',
  required: ['status', 'metadata'],
  properties: {
    status: { type: 'string', enum: ['pending', 'queued', 'running', 'completed', 'failed', 'timeout'] },
    messageId: { type: 'string' },
    job: {
      type: 'object',
      required: ['jobName'],
      properties: {
        jobName: { type: 'string' },
        executionName: { type: 'string' }
      }
    },
    metadata: {
      type: 'object',
      required: ['requestId', 'tenantId', 'triggeredAt', 'triggeredBy', 'priority', 'force'],
      properties: {
        requestId: { type: 'string' },
        tenantId: { type: 'string' },
        triggeredAt: { type: 'string', format: 'date-time' },
        triggeredBy: { type: 'string' },
        priority: { type: 'string', enum: ['low', 'normal', 'high'] },
        force: { type: 'boolean' },
        scheduleName: { type: 'string' }
      }
    }
  }
} as const;

export const refreshPostingsSchema: FastifySchema = {
  body: {
    type: 'object',
    additionalProperties: false,
    properties: {
      tenantId: { type: 'string', minLength: 1 },
      force: { type: 'boolean' },
      schedule: {
        type: 'object',
        required: ['name', 'cron'],
        additionalProperties: false,
        properties: {
          name: { type: 'string', minLength: 3 },
          cron: { type: 'string', minLength: 5 },
          timezone: { type: 'string' },
        }
      }
    }
  },
  response: {
    200: refreshResponseSchema,
    202: refreshResponseSchema
  }
};

export const refreshProfilesSchema: FastifySchema = {
  body: {
    type: 'object',
    additionalProperties: false,
    required: ['tenantId'],
    properties: {
      tenantId: { type: 'string', minLength: 1 },
      sinceIso: { type: 'string', format: 'date-time' },
      priority: { type: 'string', enum: ['low', 'normal', 'high'] },
      force: { type: 'boolean' },
      schedule: {
        type: 'object',
        required: ['name', 'cron'],
        additionalProperties: false,
        properties: {
          name: { type: 'string', minLength: 3 },
          cron: { type: 'string', minLength: 5 },
          timezone: { type: 'string' },
        }
      }
    }
  },
  response: {
    200: refreshResponseSchema,
    202: refreshResponseSchema
  }
};

export const snapshotsSchema: FastifySchema = {
  querystring: {
    type: 'object',
    additionalProperties: false,
    properties: {
      tenantId: { type: 'string', minLength: 1 }
    }
  },
  response: {
    200: {
      type: 'object',
      required: ['generatedAt', 'postings', 'profiles', 'jobHealth'],
      properties: {
        generatedAt: { type: 'string', format: 'date-time' },
        postings: freshnessSectionSchema(),
        profiles: freshnessSectionSchema(),
        jobHealth: {
          type: 'object',
          required: ['recentExecutions', 'recentFailures', 'successRatio', 'alertState'],
          properties: {
            recentExecutions: { type: 'number' },
            recentFailures: { type: 'number' },
            successRatio: { type: 'number' },
            alertState: { type: 'string', enum: ['ok', 'warning', 'critical'] },
            lastFailureAt: { type: 'string', format: 'date-time' }
          }
        }
      }
    }
  }
};

function freshnessSectionSchema() {
  return {
    type: 'object',
    required: ['maxLagDays', 'staleTenants'],
    properties: {
      lastUpdatedAt: {
        anyOf: [
          { type: 'string', format: 'date-time' },
          { type: 'null' }
        ]
      },
      maxLagDays: { type: 'number' },
      staleTenants: {
        type: 'array',
        items: {
          type: 'object',
          required: ['tenantId', 'lagDays'],
          properties: {
            tenantId: { type: 'string' },
            lagDays: { type: 'number' },
            lastUpdatedAt: { type: 'string', format: 'date-time' }
          }
        }
      }
    }
  } as const;
}
