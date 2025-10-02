# hh-eco-svc

The **hh-eco-svc** exposes tenant-aware APIs for searching and retrieving ECO (Estrutura de Cargos e Ocupações) occupation data. It mirrors the authentication, tenant validation, logging, and caching conventions found across the Headhunter Cloud Run services.

## Endpoints

### `GET /v1/occupations/search`
Perform fuzzy search over ECO occupations.

| Query | Type | Description |
|-------|------|-------------|
| `title` | string | Required search text (fuzzy matched). |
| `locale` | string | Optional locale filter (default `pt-BR`). |
| `country` | string | Optional ISO country code (default `BR`). |
| `limit` | number | Maximum results (default `10`, max `50`). |
| `useCache` | `true|false` | Disable Redis caching when set to `false`. |

**Example Response**
```json
{
  "results": [
    {
      "ecoId": "eco_2710",
      "title": "Engenheiro de Software",
      "locale": "pt-BR",
      "country": "BR",
      "aliases": ["Software Engineer", "Developer"],
      "score": 0.87,
      "source": "title"
    }
  ],
  "total": 1,
  "query": {
    "title": "engenheiro software",
    "locale": "pt-BR",
    "country": "BR",
    "limit": 10
  },
  "cacheHit": false
}
```

### `GET /v1/occupations/{ecoId}`
Retrieve a single occupation including crosswalk data and hiring templates.

| Query | Type | Description |
|-------|------|-------------|
| `locale` | string | Optional locale override for template selection. |
| `country` | string | Optional country hint for analytics. |

**Example Response**
```json
{
  "occupation": {
    "ecoId": "eco_2710",
    "title": "Engenheiro de Software",
    "locale": "pt-BR",
    "description": "Projeta e desenvolve sistemas computacionais.",
    "aliases": ["Software Engineer"],
    "crosswalk": {
      "cbo": ["2124-05"],
      "esco": ["2512.2"],
      "onet": ["15-1252.00"]
    },
    "template": {
      "summary": "Responsável pelo ciclo completo de desenvolvimento.",
      "requiredSkills": ["Java", "Microservices"],
      "preferredSkills": ["Kubernetes"],
      "yearsExperienceMin": 4,
      "yearsExperienceMax": 8
    }
  },
  "cacheHit": false
}
```

### Health Checks
- `GET /health` – Aggregates Redis and Firestore health status (`503` when degraded).
- `GET /ready` – Provided by the common bootstrap for readiness probes.

## Search Behaviour

- Fuzzy matching leverages Fuse.js against occupation titles, with complementary alias ranking for localized synonyms.
- Accents are removed during comparison (`ação` == `acao`) when `ECO_NORMALIZE_ACCENTS=true`.
- Alias matches receive a minor boost (`ECO_ALIAS_BOOST`) to highlight curated taxonomy synonyms.
- Minimum relevance is controlled via `ECO_MIN_SCORE`; results falling below are discarded.

## Caching

Redis keys are tenant-prefixed:
- Search results: `hh:eco:search:{tenantId}:{hash}`
- Occupation detail: `hh:eco:occupation:{tenantId}:{ecoId}:{locale}:{country}`

> Migration: if the service was previously deployed, clear legacy occupation keys that still include the composite cache token (they contain a `|` character) before rolling out this build, e.g. `redis-cli --scan --pattern "hh:eco:occupation:*:*|*" | xargs redis-cli del`.

`useCache=false` query flag bypasses Redis while leaving global caching untouched. TTLs are configurable per search/detail payload via environment variables.

## Firestore Collections

| Collection | Description |
|------------|-------------|
| `eco_occupation` | Canonical occupation records with fields `eco_id`, `title`, `locale`, `country`, `aliases`, `industries`, `salary_insights`. |
| `eco_alias` | Additional localized aliases (`eco_id`, `alias`, `locale`). |
| `eco_template` | Hiring templates (`summary`, `required_skills`, `preferred_skills`, `years_experience_*`). |
| `occupation_crosswalk` | Mappings to other taxonomies (`cbo`, `esco`, `onet`). |

All collections must include the tenant field defined by `ECO_ORG_FIELD` (default `org_id`).

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ECO_REDIS_HOST` | inherited | Redis host (comma-separated for clusters). |
| `ECO_REDIS_PORT` | inherited | Redis port. |
| `ECO_REDIS_PASSWORD` | `undefined` | Optional Redis password. |
| `ECO_REDIS_TLS` | `false` | Enables TLS connection. |
| `ECO_REDIS_SEARCH_PREFIX` | `hh:eco:search` | Key prefix for search cache. |
| `ECO_REDIS_OCC_PREFIX` | `hh:eco:occupation` | Key prefix for detail cache. |
| `ECO_SEARCH_TTL_SECONDS` | `120` | TTL for search results. |
| `ECO_OCCUPATION_TTL_SECONDS` | `3600` | TTL for occupation detail. |
| `ECO_CACHE_DISABLED` | `false` | Disable caching entirely. |
| `ECO_OCCUPATION_COLLECTION` | `eco_occupation` | Firestore occupation collection name. |
| `ECO_ALIAS_COLLECTION` | `eco_alias` | Alias collection name. |
| `ECO_TEMPLATE_COLLECTION` | `eco_template` | Template collection name. |
| `ECO_CROSSWALK_COLLECTION` | `occupation_crosswalk` | Crosswalk collection name. |
| `ECO_ORG_FIELD` | `org_id` | Firestore field storing tenant id. |
| `ECO_LOCALE_FIELD` | `locale` | Firestore field storing locale. |
| `ECO_SEARCH_LIMIT` | `10` | Default maximum search results. |
| `ECO_SEARCH_THRESHOLD` | `0.45` | Fuse.js threshold (lower = stricter). |
| `ECO_ALIAS_BOOST` | `1.15` | Score multiplier for alias matches. |
| `ECO_MIN_SCORE` | `0.35` | Minimum score for results. |
| `ECO_NORMALIZE_ACCENTS` | `true` | Toggle accent normalization. |
| `ECO_DEFAULT_LOCALE` | `pt-BR` | Default locale when none provided. |
| `ECO_DEFAULT_COUNTRY` | `BR` | Default country hint. |

## Local Development

```bash
cd services
npm install
cd hh-eco-svc
cp .env.example .env
npm run dev
```

Prerequisites:
1. Firebase emulators running (`firebase emulators:start --only firestore`).
2. Redis available locally (default `127.0.0.1:6379`).
3. Seed ECO reference collections for your tenant before hitting the API.

## Testing

Use Vitest for unit suites:
```bash
npm run test
```
Add fixtures for search ranking under `src/__tests__/` and follow `docs/TDD_PROTOCOL.md` for coverage expectations.

## Deployment

```bash
gcloud builds submit --tag gcr.io/$PROJECT_ID/hh-eco-svc
gcloud run deploy hh-eco-svc \
  --image gcr.io/$PROJECT_ID/hh-eco-svc \
  --set-env-vars "SERVICE_NAME=hh-eco-svc" \
  --set-env-vars "ECO_REDIS_HOST=redis:6379" \
  --allow-unauthenticated=false
```

Grant the Cloud Run identity Firestore read permissions and configure Redis credentials via Secret Manager following `docs/HANDOVER.md`.

## Troubleshooting

- **Empty search results** – Confirm alias and occupation collections contain localized data for the tenant.
- **403 errors** – Ensure the Firebase token includes `orgId` matching Firestore documents.
- **Inconsistent scores** – Tune `ECO_SEARCH_THRESHOLD` and `ECO_ALIAS_BOOST` to match business requirements.
- **Slow responses** – Validate Redis connectivity, and prewarm caches by calling `/v1/occupations/search` after deployments.
