import { defineConfig } from 'vitest/config';
import path from 'node:path';

const runTestsByPath = process.env.npm_config_runtestsbypath;
const normalizedPattern = runTestsByPath
  ? [runTestsByPath.replace(/^[./\\]+/, '')]
  : undefined;

export default defineConfig({
  root: __dirname,
  test: {
    environment: 'node',
    include: normalizedPattern
  },
  resolve: {
    alias: {
      '@services/common': path.resolve(__dirname, '../../services/common/src'),
      'fastify-plugin': path.resolve(__dirname, './stubs/fastify-plugin'),
      'firebase-admin/auth': path.resolve(__dirname, './stubs/firebase-admin-auth'),
      'lru-cache': path.resolve(__dirname, './stubs/lru-cache'),
      jose: path.resolve(__dirname, './stubs/jose'),
      pino: path.resolve(__dirname, './stubs/pino')
    }
  }
});
