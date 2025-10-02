# @hh/common

Shared utilities for Cloud Run services. Configuration is primarily provided through environment variables consumed by `getConfig()`.

## Environment variables

- `FIREBASE_PROJECT_ID` – preferred project identifier. If unset, `GOOGLE_CLOUD_PROJECT` or `GCLOUD_PROJECT` will be used.
- `FIRESTORE_EMULATOR_HOST` – preferred host for connecting to the Firestore emulator (e.g. `localhost:8080`). Falls back to `FIREBASE_EMULATOR_HOST` when present.
- `GOOGLE_APPLICATION_CREDENTIALS` – optional path to a Firebase service account JSON file. If absent, the library falls back to application default credentials. A workspace-local `service-account.json` file is automatically detected when available.
- `ENABLE_REQUEST_LOGGING` – toggle for detailed request logging (defaults to `true`).

Set `SERVICE_NAME`, `LOG_LEVEL`, `COMMON_CACHE_TTL`, and Redis variables as needed; defaults are documented in `config.ts`.
