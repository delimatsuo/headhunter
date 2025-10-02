const fs = require('node:fs/promises');
const path = require('node:path');

async function setupWrapper() {
  const projectRoot = path.resolve(__dirname, '..');
  const binPath = path.resolve(projectRoot, 'node_modules', '.bin', process.platform === 'win32' ? 'vitest.cmd' : 'vitest');
  const cliPath = path.resolve(projectRoot, 'node_modules', 'vitest', 'vitest.mjs');

  try {
    await fs.access(cliPath);
  } catch (error) {
    // Vitest not installed yet; nothing to wrap.
    return;
  }

  const wrapperPath = binPath;
  const relativeCliPath = path.relative(path.dirname(wrapperPath), cliPath).replace(/\\/g, '/');

  const wrapper = `#!/usr/bin/env node
const { spawn } = require('node:child_process');
const path = require('node:path');

const originalArgs = process.argv.slice(2);
const sanitized = [];

for (let i = 0; i < originalArgs.length; i++) {
  if (originalArgs[i] === '--runTestsByPath') {
    const next = originalArgs[i + 1];
    if (next && !next.startsWith('-')) {
      process.env.npm_config_runtestsbypath = next;
      i += 1;
    }
    continue;
  }
  sanitized.push(originalArgs[i]);
}

const cli = path.resolve(__dirname, '${relativeCliPath}');
const child = spawn(process.execPath, [cli, ...sanitized], { stdio: 'inherit' });

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
  } else {
    process.exit(code ?? 0);
  }
});
`;

  try {
    await fs.rm(wrapperPath, { force: true });
  } catch (error) {
    if (error.code !== 'ENOENT') {
      throw error;
    }
  }

  await fs.writeFile(wrapperPath, wrapper, { mode: 0o755 });
}

setupWrapper().catch((error) => {
  console.warn('[hh-security-tests] Failed to configure Vitest wrapper:', error);
});
