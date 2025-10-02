# Ella Skills Node.js SDK

The Ella Skills SDK provides a typed client for the API Gateway. It handles the
OAuth2 client-credentials flow, token caching, rate-limit awareness, and request
logging so that integrators can focus on business logic.

## Installation

```bash
npm install @ella/ella-sdk-node
```

> Requirements: Node.js 18+, access to tenant-specific client credentials issued
> via `scripts/configure_oauth2_clients.sh`.

## Quick Start

```ts
import { EllaGatewayClient } from '@ella/ella-sdk-node';

const client = new EllaGatewayClient({
  baseUrl: 'https://ella-skills-gateway-xyz.uc.gateway.dev',
  tenantId: 'tenant-123',
  clientId: process.env.ELLA_CLIENT_ID!,
  clientSecret: process.env.ELLA_CLIENT_SECRET!,
  audience: 'https://ella.skills.api/prod'
});

const { data } = await client.hybridSearch({
  query: 'machine learning engineer',
  pageSize: 10
});

console.log(data.results[0]);
```

## Configuration Options

| Option | Description | Default |
| --- | --- | --- |
| `baseUrl` | Gateway hostname (no trailing slash). | – |
| `tenantId` | Value for the `X-Tenant-ID` header. | – |
| `clientId` / `clientSecret` | Credentials issued per tenant. | – |
| `audience` | Audience claim for access tokens. | `undefined` |
| `tokenEndpoint` | OAuth2 token endpoint. | Google OAuth2 token URL |
| `requestTimeoutMs` | Per-request timeout in milliseconds. | `15000` |
| `retry` | Retry/backoff settings `{ retries, factor, minTimeoutMs, maxTimeoutMs }`. | `{2, 2, 250, 4000}` |
| `logger` | Callback invoked with request/response events. | `undefined` |
| `tokenCacheOffsetSeconds` | Seconds to subtract from token expiry when caching. | `30` |

## Available Methods

All methods return a `Promise<GatewayResponse<T>>` which includes the parsed data
and rate-limit metadata.

| Method | Description |
| --- | --- |
| `createEmbeddingsBatch(request)` | Submit embeddings job. |
| `getEmbeddingsStatus(jobId)` | Retrieve embeddings job status. |
| `hybridSearch(request)` | Perform hybrid search. |
| `rerank(request)` | Rerank candidate list. |
| `listEvidenceDocuments(params)` | List evidence documents with pagination. |
| `getEvidenceDocument(id)` | Fetch evidence document details. |
| `listOccupations(params)` / `getOccupation(id)` | Occupation catalogue APIs. |
| `listSkills(params)` | Skills metadata. |
| `getMarketInsights(request)` | Labour market insights. |
| `getRoleRecommendations(request)` | Role recommendations. |
| `listTenants()` | Admin tenant listing (requires elevated credentials). |

## Handling Rate Limits

Each response includes `rateLimit` metadata derived from Gateway headers:

```ts
const { data, rateLimit } = await client.hybridSearch({ query: 'designer' });

if (rateLimit?.remaining === 0) {
  console.log(`Quota exhausted. Window resets at ${new Date((rateLimit.reset ?? 0) * 1000)}`);
}
```

When the Gateway responds with HTTP 429 the client automatically retries using
exponential backoff. You can customise the behaviour via the `retry` option.

## Request Logging

Pass a logger to capture diagnostic events:

```ts
const client = new EllaGatewayClient({
  /* ... */
  logger: (event) => {
    if (event.type === 'error') {
      console.error('[Gateway]', event);
    } else {
      console.debug('[Gateway]', event);
    }
  }
});
```

## Custom Fetch Implementation

By default the SDK uses the Node.js global `fetch` (or [`undici`](https://undici.nodejs.org/)).
You can inject a custom implementation, e.g. to support proxies:

```ts
import fetch from 'node-fetch';

const client = new EllaGatewayClient({
  /* ... */
  fetch
});
```

## Error Handling

Non-success responses throw a `GatewayError` containing:

```ts
try {
  await client.getEvidenceDocument('invalid-id');
} catch (error) {
  if (error instanceof GatewayError) {
    console.error('Gateway error', error.status, error.payload);
  }
}
```

## Publishing

1. Run `npm run build` to compile the package.
2. Execute `npm pack` (or `npm run publish:dry-run`) to inspect the tarball.
3. Publish with `npm publish --access public` once validation passes.

## Troubleshooting

- `401 Unauthorized`: ensure the tenant credentials are rotated via
  `scripts/configure_oauth2_clients.sh`.
- `429 Too Many Requests`: monitor per-tenant quotas using the Cloud Monitoring
  dashboard installed by `scripts/setup_gateway_monitoring.sh`.
- Token caching issues: call `client.clearTokenCache()` before retrying.

## License

MIT © Ella Skills
