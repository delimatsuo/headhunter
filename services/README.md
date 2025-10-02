# Headhunter Cloud Run Services

This directory hosts the TypeScript Cloud Run services that power the next-generation recruiter APIs. Each service is packaged as an npm workspace that shares a set of common utilities for configuration, authentication, tenant resolution, logging, and error handling.

## Directory Layout

- `common/` – Shared utilities published under the `@hh/common` namespace. All services consume these utilities for consistent middleware, logging, and runtime behaviour.
- `hh-example-svc/` – Reference implementation that illustrates how to bootstrap a Fastify service, register routes, and compose middleware.
- `tsconfig.base.json` – Base TypeScript configuration inherited by all workspace packages.
- `.eslintrc.js` – ESLint configuration that enforces repository coding standards.
- `package.json` – Workspace manifest that defines shared scripts, dependencies, and tooling configuration.

## Getting Started

1. Install dependencies from the repository root: `npm install --workspaces --prefix services`.
2. Compile all services with `npm run build --prefix services`.
3. Run the example service locally by executing `npm run dev --prefix services/hh-example-svc`.

Each service should expose standard health and readiness probes (`/health` and `/ready`) and rely on Firebase authenticated requests forwarded through the API Gateway.

## Configuration

Cloud Run services derive their configuration from environment variables so that local development matches production deployments. The table below outlines the key inputs and their fallbacks.

| Variable(s) | Purpose | Default/Fallback |
| --- | --- | --- |
| `FIREBASE_PROJECT_ID` → `GOOGLE_CLOUD_PROJECT` → `GCLOUD_PROJECT` | Determines the Firebase/Google Cloud project ID used by Firestore and Firebase Admin. | Required – the first defined value is used. |
| `FIRESTORE_EMULATOR_HOST` (alias `FIREBASE_EMULATOR_HOST`) | Points the Firestore client at a local emulator instead of production. | Unset → connect to production Firestore. |
| `GOOGLE_APPLICATION_CREDENTIALS` or `./service-account.json` | Supplies service account credentials for Firebase Admin. | Uses `./service-account.json` when present, otherwise falls back to ADC. |
| `AUTH_CHECK_REVOKED` | Controls whether Firebase ID tokens are checked for revocation when verifying requests. | Defaults to `true`; set to `false` to disable revocation checks for local debugging. |

## Developing a New Service

1. Duplicate `hh-example-svc` into a new workspace directory and update the package metadata.
2. Register the service under the workspace list in `services/package.json`.
3. Implement feature routes using the Fastify server returned by `@hh/common`'s `buildServer()`.
4. Add Jest-based unit tests and ensure `npm run lint --prefix services` passes before submitting a PR.

See `common/src/server.ts` for the shared Fastify bootstrapper and consult the PRD for endpoint-specific requirements.
