/**
 * Shadow Stats Routes
 *
 * Provides endpoints for monitoring shadow mode validation progress.
 */

import type { FastifyInstance } from 'fastify';
import { getLogger } from '@hh/common';
import type ShadowMode from '../shadow/shadow-mode.js';

const logger = getLogger({ module: 'shadow-stats-routes' });

/**
 * Promotion readiness thresholds per RESEARCH.md validation requirements.
 */
const PROMOTION_THRESHOLDS = {
  directionAgreement: 0.85,     // >85% direction agreement
  velocityAgreement: 0.80,      // >80% velocity agreement
  minComparisons: 1000          // >1000 comparisons for statistical significance
};

/**
 * Response for GET /shadow/stats endpoint.
 */
interface ShadowStatsResponse {
  /** Direction agreement percentage (0-1) */
  directionAgreement: number;
  /** Velocity agreement percentage (0-1) */
  velocityAgreement: number;
  /** Type agreement percentage (0-1) */
  typeAgreement: number;
  /** Total number of comparisons logged */
  totalComparisons: number;
  /** Whether ML model is ready for promotion to production */
  promotionReady: boolean;
  /** Promotion readiness details */
  promotionDetails: {
    directionMet: boolean;
    velocityMet: boolean;
    minComparisonsMet: boolean;
  };
  /** Target thresholds */
  thresholds: {
    directionAgreement: number;
    velocityAgreement: number;
    minComparisons: number;
  };
}

/**
 * Registers shadow stats routes.
 *
 * @param fastify - Fastify instance
 * @param shadowMode - Shadow mode orchestrator
 */
export async function shadowStatsRoutes(
  fastify: FastifyInstance,
  shadowMode: ShadowMode
): Promise<void> {
  /**
   * GET /shadow/stats
   *
   * Returns current shadow mode validation statistics and promotion readiness.
   */
  fastify.get('/shadow/stats', async (_request, reply) => {
    try {
      logger.info('GET /shadow/stats');

      const stats = shadowMode.getStats();

      // Check promotion readiness
      const directionMet = stats.directionAgreement >= PROMOTION_THRESHOLDS.directionAgreement;
      const velocityMet = stats.velocityAgreement >= PROMOTION_THRESHOLDS.velocityAgreement;
      const minComparisonsMet = stats.totalComparisons >= PROMOTION_THRESHOLDS.minComparisons;

      const promotionReady = directionMet && velocityMet && minComparisonsMet;

      const response: ShadowStatsResponse = {
        directionAgreement: stats.directionAgreement,
        velocityAgreement: stats.velocityAgreement,
        typeAgreement: stats.typeAgreement,
        totalComparisons: stats.totalComparisons,
        promotionReady,
        promotionDetails: {
          directionMet,
          velocityMet,
          minComparisonsMet
        },
        thresholds: PROMOTION_THRESHOLDS
      };

      return reply.code(200).send(response);
    } catch (error) {
      logger.error({ error }, 'Failed to get shadow stats');
      return reply.code(500).send({
        error: 'Internal Server Error',
        message: 'Failed to retrieve shadow statistics'
      });
    }
  });

  /**
   * GET /shadow/recent
   *
   * Returns the most recent shadow comparisons for debugging.
   */
  fastify.get('/shadow/recent', async (_request, reply) => {
    try {
      logger.info('GET /shadow/recent');

      // Get last 10 comparisons by default
      const recent = shadowMode.getRecent(10);

      return reply.code(200).send({
        count: recent.length,
        comparisons: recent
      });
    } catch (error) {
      logger.error({ error }, 'Failed to get recent comparisons');
      return reply.code(500).send({
        error: 'Internal Server Error',
        message: 'Failed to retrieve recent comparisons'
      });
    }
  });

  logger.info('Shadow stats routes registered');
}
