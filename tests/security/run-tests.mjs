#!/usr/bin/env node
import { spawn } from 'node:child_process';

const rawArgs = process.argv.slice(2);
const vitestArgs = ['run'];
const passthrough = [];

for (let index = 0; index < rawArgs.length; index += 1) {
  const arg = rawArgs[index];
  if (arg === '--runTestsByPath') {
    const target = rawArgs[index + 1];
    if (target) {
      passthrough.push(target);
      index += 1;
    }
    continue;
  }
  passthrough.push(arg);
}

const executable = process.platform === 'win32' ? 'vitest.cmd' : 'vitest';
const child = spawn(executable, [...vitestArgs, ...passthrough], {
  stdio: 'inherit',
  env: process.env
});

child.on('exit', (code, signal) => {
  if (signal) {
    console.error(`[security-tests] vitest exited via signal ${signal}`);
    process.exit(1);
  }
  process.exit(code ?? 1);
});

child.on('error', (err) => {
  console.error('[security-tests] Failed to launch vitest:', err);
  process.exit(1);
});
