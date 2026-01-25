/**
 * Shadow Mode Module - Barrel Exports
 *
 * This module provides shadow mode infrastructure for ML vs rule-based comparison logging.
 */

export { default as RuleBasedBridge } from './rule-based-bridge.js';
export type {
  RuleBasedMetrics,
  TrajectoryDirection,
  TrajectoryVelocity,
  TrajectoryType,
  ExperienceEntry
} from './rule-based-bridge.js';

export { default as ComparisonLogger } from './comparison-logger.js';
export type {
  ShadowComparison,
  ComparisonLoggerConfig,
  ShadowStats
} from './comparison-logger.js';
