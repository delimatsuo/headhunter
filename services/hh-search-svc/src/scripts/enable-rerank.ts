#!/usr/bin/env ts-node
import process from 'node:process';

type EnvSource = 'production' | 'staging' | 'local';

interface CliArgs {
  secretProject: string;
  secretName: string;
  key: string;
  value: string;
  environment: EnvSource;
}

function parseArgs(argv: string[]): CliArgs {
  const options: Record<string, string> = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg.startsWith('--')) {
      const key = arg.slice(2);
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) {
        throw new Error(`Missing value for flag --${key}`);
      }
      options[key] = value;
      i += 1;
    }
  }

  const environment = (options.env ?? 'production') as EnvSource;
  if (!['production', 'staging', 'local'].includes(environment)) {
    throw new Error(`Unsupported environment: ${environment}`);
  }

  return {
    secretProject: options.project ?? process.env.GCP_PROJECT ?? 'headhunter-ai-0088',
    secretName: options.secret ?? 'hh-search-config',
    key: options.key ?? 'ENABLE_RERANK',
    value: options.value ?? 'true',
    environment
  } satisfies CliArgs;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  if (args.environment !== 'production') {
    console.log(`Skipping update because environment is ${args.environment}`);
    return;
  }

  console.error('NOTE: Automatic secret updates are disabled in this script.');
  console.error('Please run:');
  console.error(
    `  gcloud secrets versions add ${args.secretName} --data-file=<(printf '%s=%s\n' '${args.key}' '${args.value}') --project=${args.secretProject}`
  );
  console.error('Then redeploy hh-search-svc to pick up the new config.');
}

void main();
