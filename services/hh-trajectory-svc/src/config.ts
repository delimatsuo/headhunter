import { getConfig as getBaseConfig, type ServiceConfig } from '@hh/common';

export interface TrajectoryServiceConfig {
  base: ServiceConfig;
  /** Port for the service (default: 7109) */
  port: number;
  /** Path to the ONNX model file */
  modelPath: string;
  /** Enable shadow mode to log predictions without affecting responses (default: true) */
  shadowModeEnabled: boolean;
  /** Redis URL for shadow logging */
  redisUrl: string;
  /** Confidence threshold for low-confidence flagging (default: 0.6) */
  confidenceThreshold: number;
}

let cachedConfig: TrajectoryServiceConfig | null = null;

function parseNumber(value: string | undefined, defaultValue: number): number {
  if (value === undefined) {
    return defaultValue;
  }

  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return defaultValue;
  }

  return parsed;
}

function parseBoolean(value: string | undefined, defaultValue: boolean): boolean {
  if (value === undefined) {
    return defaultValue;
  }

  const normalized = value.trim().toLowerCase();
  if (['true', '1', 'yes', 'y', 'on'].includes(normalized)) {
    return true;
  }
  if (['false', '0', 'no', 'n', 'off'].includes(normalized)) {
    return false;
  }
  return defaultValue;
}

export function getTrajectoryServiceConfig(): TrajectoryServiceConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  const base = getBaseConfig();

  cachedConfig = {
    base,
    port: parseNumber(process.env.PORT, 7109),
    modelPath: process.env.TRAJECTORY_MODEL_PATH ?? '/usr/src/app/models/trajectory-lstm.onnx',
    shadowModeEnabled: parseBoolean(process.env.TRAJECTORY_SHADOW_MODE, true),
    redisUrl: process.env.REDIS_URL ?? 'redis://localhost:6379',
    confidenceThreshold: parseNumber(process.env.TRAJECTORY_CONFIDENCE_THRESHOLD, 0.6)
  };

  return cachedConfig;
}

export function resetTrajectoryServiceConfig(): void {
  cachedConfig = null;
}
