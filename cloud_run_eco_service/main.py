import asyncio
import json
import logging
import os
import time
import unicodedata
from typing import Any, Dict, List, Optional

import asyncpg
import firebase_admin
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from firebase_admin import auth as firebase_auth, firestore as firebase_firestore
from pydantic import BaseModel, BaseSettings, Field
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
import redis.asyncio as redis

LOGGER = logging.getLogger("eco_cloud_run_service")
logging.basicConfig(level=logging.INFO)


class Settings(BaseSettings):
    pg_dsn: Optional[str] = Field(None, env="ECO_PG_DSN")
    redis_url: str = Field(..., env="ECO_REDIS_URL")
    cache_ttl_occupation: int = Field(3600, env="ECO_CACHE_TTL_OCCUPATION")
    cache_ttl_crosswalk: int = Field(86400, env="ECO_CACHE_TTL_CROSSWALK")
    rate_limit_per_minute: int = Field(120, env="ECO_RATE_LIMIT_PER_MINUTE")
    firebase_project_id: Optional[str] = Field(None, env="FIREBASE_PROJECT_ID")
    service_name: str = Field("eco-cloud-run-service", env="SERVICE_NAME")
    max_search_limit: int = Field(25, env="ECO_MAX_SEARCH_LIMIT")

    class Config:
        env_file = ".env"
        case_sensitive = False


class OccupationSummary(BaseModel):
    eco_id: str
    display_name: str
    normalized_title: str
    description: Optional[str]
    locale: str
    country: str
    evidence_count: int


class AliasInfo(BaseModel):
    alias: Optional[str]
    normalized_alias: Optional[str]
    confidence: Optional[float]


class CrosswalkInfo(BaseModel):
    system: str
    code: str
    label: Optional[str]


class TemplateInfo(BaseModel):
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    min_years_experience: Optional[int]
    max_years_experience: Optional[int]
    notes: Optional[str]


class OccupationDetail(OccupationSummary):
    aliases: List[AliasInfo] = Field(default_factory=list)
    crosswalks: List[CrosswalkInfo] = Field(default_factory=list)
    templates: List[TemplateInfo] = Field(default_factory=list)


class OccupationSearchResult(BaseModel):
    occupation: OccupationSummary
    alias: Optional[AliasInfo]
    score: float
    source: str = "database"


class SearchResponse(BaseModel):
    query: str
    normalized_query: str
    results: List[OccupationSearchResult]
    cache_hit: bool
    duration_ms: float
    from_cache_only: bool = False


class BatchSearchResponse(BaseModel):
    results: Dict[str, SearchResponse]
    errors: Dict[str, str]


class SuggestCrosswalkRequest(BaseModel):
    title: str
    locale: str = "pt-BR"
    country: str = "BR"
    systems: Optional[List[str]] = None
    limit: int = 5


class SuggestCrosswalkResponse(BaseModel):
    title: str
    normalized_title: str
    occupation: Optional[OccupationSummary]
    crosswalks: List[CrosswalkInfo]
    confidence: Optional[float]
    cache_hit: bool
    from_cache_only: bool = False


class AuthenticatedUser(BaseModel):
    uid: str
    email: Optional[str]
    roles: List[str] = Field(default_factory=list)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 30) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.opened_at: Optional[float] = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        elapsed = time.time() - self.opened_at
        if elapsed >= self.reset_timeout:
            self.failures = 0
            self.opened_at = None
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.time()


REQUEST_COUNTER = Counter(
    "eco_service_requests_total",
    "Total number of requests",
    ["endpoint", "method", "status"],
)
REQUEST_LATENCY = Histogram(
    "eco_service_request_latency_seconds",
    "Request latency",
    ["endpoint"],
)
CACHE_HITS = Counter(
    "eco_service_cache_hits_total",
    "Cache hits",
    ["endpoint"],
)
CACHE_MISSES = Counter(
    "eco_service_cache_misses_total",
    "Cache misses",
    ["endpoint"],
)
DB_FAILURES = Counter(
    "eco_service_db_failures_total",
    "Database failures",
    ["operation"],
)
REDIS_FAILURES = Counter(
    "eco_service_cache_failures_total",
    "Cache failures",
    ["operation"],
)
HEALTH_STATUS = Gauge(
    "eco_service_health_status",
    "Component health status",
    ["component"],
)


def normalize_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().strip()
    return " ".join(normalized.split())


async def ensure_firebase_initialized(settings: Settings) -> None:
    if firebase_admin._apps:
        return
    options: Dict[str, Any] = {}
    if settings.firebase_project_id:
        options["projectId"] = settings.firebase_project_id
    try:
        firebase_admin.initialize_app(options=options or None)
        LOGGER.info("Firebase admin initialized")
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.error("Failed to initialize Firebase admin: %s", exc)
        raise


async def authenticate_request(
    request: Request,
    settings: Settings,
) -> AuthenticatedUser:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")

    token = auth_header.split(" ", 1)[1]
    try:
        decoded = await asyncio.get_event_loop().run_in_executor(None, firebase_auth.verify_id_token, token)
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.warning("Token verification failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token") from exc

    roles = decoded.get("roles") or decoded.get("customClaims", {}).get("roles") or []
    if isinstance(roles, str):
        roles = [roles]

    return AuthenticatedUser(uid=decoded.get("uid"), email=decoded.get("email"), roles=roles)


async def rate_limit(
    redis_client: redis.Redis,
    user: AuthenticatedUser,
    endpoint: str,
    settings: Settings,
) -> None:
    key = f"rl:{user.uid}:{endpoint}:{int(time.time() // 60)}"
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 60)
        if count > settings.rate_limit_per_minute:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
    except redis.RedisError as exc:
        REDIS_FAILURES.labels(operation="rate_limit").inc()
        LOGGER.warning("Rate limit cache failure: %s", exc)


class AppState:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.pg_pool: Optional[asyncpg.Pool] = None
        self.redis: Optional[redis.Redis] = None
        self.circuit_breaker = CircuitBreaker()
        self.supports_trgm = False
        self.last_config_loaded_at: Optional[float] = None
        self.config_refresh_interval = int(os.environ.get("ECO_CONFIG_REFRESH_SECONDS", "300"))
        self.pg_dsn_source = "ECO_PG_DSN"

    async def init_resources(self) -> None:
        if not self.settings.pg_dsn:
            raise RuntimeError("Postgres DSN is not configured")
        self.pg_pool = await asyncpg.create_pool(dsn=self.settings.pg_dsn, min_size=1, max_size=10)
        self.redis = redis.from_url(self.settings.redis_url, encoding="utf-8", decode_responses=True)
        HEALTH_STATUS.labels(component="database").set(1)
        HEALTH_STATUS.labels(component="cache").set(1)
        HEALTH_STATUS.labels(component="service").set(1)

        async with self.pg_pool.acquire() as conn:
            try:
                val = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='pg_trgm')")
                self.supports_trgm = bool(val)
            except asyncpg.PostgresError:
                self.supports_trgm = False
                LOGGER.warning("pg_trgm extension not available, falling back to LIKE search")

    async def close(self) -> None:
        if self.pg_pool:
            await self.pg_pool.close()
        if self.redis:
            await self.redis.close()

    async def refresh_dynamic_config(self, force: bool = False) -> None:
        now = time.time()
        if not force and self.last_config_loaded_at and (now - self.last_config_loaded_at) < self.config_refresh_interval:
            return
        if not firebase_admin._apps:  # type: ignore[attr-defined]
            return
        client = firebase_firestore.client()

        loop = asyncio.get_event_loop()
        try:
            snapshot = await loop.run_in_executor(None, lambda: client.collection("config").document("eco").get())
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.warning("Failed to load ECO config from Firestore: %s", exc)
            return

        data = snapshot.to_dict() if snapshot and snapshot.exists else {}
        cache_cfg = data.get("cache", {}) if isinstance(data, dict) else {}
        updated = False

        occupation_ttl = cache_cfg.get("occupationTtlMinutes")
        if occupation_ttl is not None:
            try:
                ttl_seconds = max(60, int(occupation_ttl) * 60)
                if ttl_seconds != self.settings.cache_ttl_occupation:
                    self.settings.cache_ttl_occupation = ttl_seconds
                    updated = True
            except (TypeError, ValueError):
                LOGGER.debug("Invalid occupationTtlMinutes value in config: %s", occupation_ttl)

        crosswalk_ttl = cache_cfg.get("crosswalkTtlHours")
        if crosswalk_ttl is not None:
            try:
                ttl_seconds = max(3600, int(crosswalk_ttl) * 3600)
                if ttl_seconds != self.settings.cache_ttl_crosswalk:
                    self.settings.cache_ttl_crosswalk = ttl_seconds
                    updated = True
            except (TypeError, ValueError):
                LOGGER.debug("Invalid crosswalkTtlHours value in config: %s", crosswalk_ttl)

        if updated:
            LOGGER.info(
                "Updated cache TTLs from Firestore config (occupation=%ss, crosswalk=%ss)",
                self.settings.cache_ttl_occupation,
                self.settings.cache_ttl_crosswalk,
            )

        self.last_config_loaded_at = now


app = FastAPI(title="ECO Cloud Run Service", version="1.0.0")
settings = Settings()
dsn_source = "ECO_PG_DSN"
if not settings.pg_dsn:
    fallback_dsn = os.environ.get("DATABASE_URL")
    if fallback_dsn:
        settings.pg_dsn = fallback_dsn
        dsn_source = "DATABASE_URL"
if not settings.pg_dsn:
    raise RuntimeError("ECO Cloud Run service requires ECO_PG_DSN or DATABASE_URL to be set")
state = AppState(settings)
state.pg_dsn_source = dsn_source


@app.on_event("startup")
async def on_startup() -> None:
    await ensure_firebase_initialized(settings)
    await state.init_resources()
    await state.refresh_dynamic_config(force=True)
    LOGGER.info("Postgres DSN sourced from %s", state.pg_dsn_source)
    LOGGER.info("Service started with trgm=%s", state.supports_trgm)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await state.close()
    LOGGER.info("Service shutdown complete")


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):  # type: ignore[override]
    if request.url.path == "/metrics":
        return await call_next(request)
    start = time.perf_counter()
    endpoint = request.url.path
    method = request.method.lower()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration = time.perf_counter() - start
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
        REQUEST_COUNTER.labels(endpoint=endpoint, method=method, status=str(status_code)).inc()


async def get_pg_connection() -> asyncpg.Connection:
    if not state.pg_pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized")
    return await state.pg_pool.acquire()


async def release_pg_connection(conn: asyncpg.Connection) -> None:
    if state.pg_pool:
        await state.pg_pool.release(conn)


async def get_redis_client() -> redis.Redis:
    if not state.redis:
        raise HTTPException(status_code=500, detail="Cache not initialized")
    return state.redis

async def run_search_query(
    conn: asyncpg.Connection,
    normalized: str,
    locale: str,
    country: str,
    limit: int,
) -> List[asyncpg.Record]:
    if state.supports_trgm:
        query = """
            WITH params AS (
                SELECT $3::text AS q
            )
            SELECT o.eco_id,
                   o.display_name,
                   o.normalized_title,
                   o.description,
                   o.evidence_count,
                   o.locale,
                   o.country,
                   a.alias,
                   a.normalized_alias,
                   a.confidence,
                   GREATEST(
                       CASE WHEN o.normalized_title = params.q THEN 1.0 ELSE 0 END,
                       COALESCE(similarity(o.normalized_title, params.q), 0),
                       COALESCE(similarity(COALESCE(a.normalized_alias, ''), params.q), 0)
                   ) AS score
            FROM params
            JOIN eco_occupation o ON o.locale = $1 AND o.country = $2
            LEFT JOIN eco_alias a ON a.eco_id = o.eco_id
            WHERE (o.normalized_title ILIKE params.q || '%')
               OR (a.normalized_alias ILIKE params.q || '%')
               OR (COALESCE(similarity(o.normalized_title, params.q), 0) > 0.2)
            ORDER BY score DESC, o.evidence_count DESC
            LIMIT $4
        """
    else:
        query = """
            SELECT o.eco_id,
                   o.display_name,
                   o.normalized_title,
                   o.description,
                   o.evidence_count,
                   o.locale,
                   o.country,
                   NULL AS alias,
                   NULL AS normalized_alias,
                   NULL AS confidence,
                   CASE WHEN o.normalized_title = $3 THEN 1.0 ELSE 0 END AS score
            FROM eco_occupation o
            WHERE o.locale = $1 AND o.country = $2
              AND (o.normalized_title = $3 OR o.normalized_title ILIKE $3 || '%')
            ORDER BY score DESC, o.evidence_count DESC
            LIMIT $4
        """

    try:
        rows = await conn.fetch(query, locale, country, normalized, limit)
        state.circuit_breaker.record_success()
        return rows
    except asyncpg.PostgresError as exc:
        DB_FAILURES.labels(operation="search").inc()
        state.circuit_breaker.record_failure()
        LOGGER.error("Search query failed: %s", exc)
        raise


@app.get("/occupations/search", response_model=BatchSearchResponse)
async def search_occupations(
    request: Request,
    q: Optional[str] = Query(None, description="Occupation title query"),
    locale: str = Query("pt-BR"),
    country: str = Query("BR"),
    limit: int = Query(10, ge=1, le=settings.max_search_limit),
    titles: Optional[List[str]] = Query(None, description="Batch search queries"),
    user: AuthenticatedUser = Depends(lambda req: authenticate_request(req, settings)),
    redis_client: redis.Redis = Depends(get_redis_client),
):
    await rate_limit(redis_client, user, "occupations_search", settings)
    await state.refresh_dynamic_config()

    queries = []
    if titles:
        queries.extend([title for title in titles if title])
    if q:
        queries.append(q)

    if not queries:
        raise HTTPException(status_code=400, detail="Query parameter q or titles is required")

    async def search_single(raw_query: str) -> SearchResponse:
        normalized_query = normalize_title(raw_query)
        cache_key = f"occ:search:{locale}:{country}:{normalized_query}:{limit}"
        start = time.perf_counter()

        cached = None
        try:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                CACHE_HITS.labels(endpoint="/occupations/search").inc()
                cached = SearchResponse.parse_raw(cached_data)
        except redis.RedisError as exc:
            REDIS_FAILURES.labels(operation="get").inc()
            LOGGER.warning("Cache read failed: %s", exc)

        if cached:
            duration = (time.perf_counter() - start) * 1000
            cached.duration_ms = duration
            cached.cache_hit = True
            return cached

        CACHE_MISSES.labels(endpoint="/occupations/search").inc()

        if not state.circuit_breaker.allow():
            raise HTTPException(status_code=503, detail="Search temporarily unavailable")

        try:
            conn = await get_pg_connection()
            try:
                rows = await run_search_query(conn, normalized_query, locale, country, limit)
            finally:
                await release_pg_connection(conn)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error("Database search failed: %s", exc)
            DB_FAILURES.labels(operation="search").inc()
            cached_only = None
            try:
                cached_fallback = await redis_client.get(cache_key)
                if cached_fallback:
                    cached_only = SearchResponse.parse_raw(cached_fallback)
            except redis.RedisError:
                cached_only = None
            if cached_only:
                cached_only.from_cache_only = True
                cached_only.cache_hit = True
                return cached_only
            raise HTTPException(status_code=503, detail="Search unavailable") from exc

        results: List[OccupationSearchResult] = []
        for row in rows:
            occupation = OccupationSummary(
                eco_id=row["eco_id"],
                display_name=row["display_name"],
                normalized_title=row["normalized_title"],
                description=row["description"],
                locale=row["locale"],
                country=row["country"],
                evidence_count=row["evidence_count"],
            )
            alias = None
            if row.get("alias"):
                alias = AliasInfo(
                    alias=row.get("alias"),
                    normalized_alias=row.get("normalized_alias"),
                    confidence=row.get("confidence"),
                )
            results.append(
                OccupationSearchResult(
                    occupation=occupation,
                    alias=alias,
                    score=float(row.get("score", 0.0)),
                )
            )

        duration = (time.perf_counter() - start) * 1000
        response = SearchResponse(
            query=raw_query,
            normalized_query=normalized_query,
            results=results,
            cache_hit=False,
            duration_ms=duration,
        )

        try:
            await redis_client.setex(cache_key, settings.cache_ttl_occupation, response.json())
        except redis.RedisError as exc:
            REDIS_FAILURES.labels(operation="set").inc()
            LOGGER.warning("Cache write failed: %s", exc)

        return response

    aggregated: Dict[str, SearchResponse] = {}
    batch_errors: Dict[str, str] = {}
    for raw in queries:
        try:
            aggregated[raw] = await search_single(raw)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            batch_errors[raw] = detail
        except Exception as exc:  # pylint: disable=broad-except
            batch_errors[raw] = str(exc)

    return BatchSearchResponse(results=aggregated, errors=batch_errors)


@app.get("/occupations/{eco_id}", response_model=OccupationDetail)
async def get_occupation_detail(
    eco_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(lambda req: authenticate_request(req, settings)),
    redis_client: redis.Redis = Depends(get_redis_client),
):
    await rate_limit(redis_client, user, "occupation_detail", settings)
    await state.refresh_dynamic_config()

    if not state.circuit_breaker.allow():
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    cache_key = f"occ:detail:{eco_id}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            CACHE_HITS.labels(endpoint="/occupations/{eco_id}").inc()
            return json.loads(cached)
        CACHE_MISSES.labels(endpoint="/occupations/{eco_id}").inc()
    except redis.RedisError as exc:
        REDIS_FAILURES.labels(operation="get").inc()
        LOGGER.warning("Cache read failed: %s", exc)

    conn = await get_pg_connection()
    try:
        occupation_row = await conn.fetchrow(
            """
            SELECT eco_id, display_name, normalized_title, description, locale, country, evidence_count
            FROM eco_occupation
            WHERE eco_id = $1
            """,
            eco_id,
        )
        if not occupation_row:
            raise HTTPException(status_code=404, detail="Occupation not found")

        alias_rows = await conn.fetch(
            """SELECT alias, normalized_alias, confidence FROM eco_alias WHERE eco_id = $1 ORDER BY confidence DESC NULLS LAST""",
            eco_id,
        )
        crosswalk_rows = await conn.fetch(
            """SELECT system, code, label FROM occupation_crosswalk WHERE eco_id = $1 ORDER BY system, code""",
            eco_id,
        )
        template_rows = await conn.fetch(
            """
            SELECT required_skills, preferred_skills, min_years_experience, max_years_experience, notes
            FROM eco_template
            WHERE eco_id = $1
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 3
            """,
            eco_id,
        )
    except asyncpg.PostgresError as exc:
        DB_FAILURES.labels(operation="occupation_detail").inc()
        LOGGER.error("Failed to load occupation detail: %s", exc)
        raise HTTPException(status_code=503, detail="Failed to load occupation") from exc
    finally:
        await release_pg_connection(conn)

    detail = OccupationDetail(
        eco_id=occupation_row["eco_id"],
        display_name=occupation_row["display_name"],
        normalized_title=occupation_row["normalized_title"],
        description=occupation_row["description"],
        locale=occupation_row["locale"],
        country=occupation_row["country"],
        evidence_count=occupation_row["evidence_count"],
        aliases=[
            AliasInfo(alias=row["alias"], normalized_alias=row["normalized_alias"], confidence=row["confidence"])
            for row in alias_rows
        ],
        crosswalks=[
            CrosswalkInfo(system=row["system"], code=row["code"], label=row["label"])
            for row in crosswalk_rows
        ],
        templates=[
            TemplateInfo(
                required_skills=row.get("required_skills") or [],
                preferred_skills=row.get("preferred_skills") or [],
                min_years_experience=row.get("min_years_experience"),
                max_years_experience=row.get("max_years_experience"),
                notes=row.get("notes"),
            )
            for row in template_rows
        ],
    )

    payload = detail.dict()
    try:
        await redis_client.setex(cache_key, settings.cache_ttl_occupation, json.dumps(payload))
    except redis.RedisError as exc:
        REDIS_FAILURES.labels(operation="set").inc()
        LOGGER.warning("Cache write failed: %s", exc)

    return payload


@app.post("/occupations/crosswalk/suggest", response_model=SuggestCrosswalkResponse)
async def suggest_crosswalk(
    request: Request,
    payload: SuggestCrosswalkRequest = Body(...),
    user: AuthenticatedUser = Depends(lambda req: authenticate_request(req, settings)),
    redis_client: redis.Redis = Depends(get_redis_client),
):
    await rate_limit(redis_client, user, "crosswalk_suggest", settings)
    await state.refresh_dynamic_config()

    normalized = normalize_title(payload.title)
    cache_key = f"crosswalk:suggest:{normalized}:{','.join(payload.systems or [])}"

    try:
        cached = await redis_client.get(cache_key)
        if cached:
            CACHE_HITS.labels(endpoint="/occupations/crosswalk/suggest").inc()
            return json.loads(cached)
        CACHE_MISSES.labels(endpoint="/occupations/crosswalk/suggest").inc()
    except redis.RedisError as exc:
        REDIS_FAILURES.labels(operation="get").inc()
        LOGGER.warning("Cache read failed: %s", exc)

    search_response = await search_occupations(
        request=request,
        q=payload.title,
        locale=payload.locale,
        country=payload.country,
        limit=1,
        titles=None,
        user=user,
        redis_client=redis_client,
    )
    query_entry = search_response.results.get(payload.title)
    result_items = query_entry.results if query_entry else []
    if not result_items:
        response = SuggestCrosswalkResponse(
            title=payload.title,
            normalized_title=normalized,
            occupation=None,
            crosswalks=[],
            confidence=None,
            cache_hit=query_entry.cache_hit if query_entry else False,
        )
        payload_dict = response.dict()
        try:
            await redis_client.setex(cache_key, settings.cache_ttl_crosswalk, json.dumps(payload_dict))
        except redis.RedisError as exc:
            REDIS_FAILURES.labels(operation="set").inc()
            LOGGER.warning("Cache write failed: %s", exc)
        return payload_dict

    top = result_items[0]
    occupation = top.occupation
    conn = await get_pg_connection()
    try:
        crosswalk_rows = await conn.fetch(
            """
            SELECT system, code, label
            FROM occupation_crosswalk
            WHERE eco_id = $1
            ORDER BY system, code
            """,
            occupation.eco_id,
        )
    except asyncpg.PostgresError as exc:
        DB_FAILURES.labels(operation="crosswalk_suggest").inc()
        LOGGER.error("Failed to load crosswalks: %s", exc)
        raise HTTPException(status_code=503, detail="Failed to compute crosswalks") from exc
    finally:
        await release_pg_connection(conn)

    crosswalks = [
        CrosswalkInfo(system=row["system"], code=row["code"], label=row["label"])
        for row in crosswalk_rows
        if not payload.systems or row["system"] in payload.systems
    ][: payload.limit]

    response = SuggestCrosswalkResponse(
        title=payload.title,
        normalized_title=normalized,
        occupation=occupation,
        crosswalks=crosswalks,
        confidence=top.score,
        cache_hit=bool(query_entry.cache_hit if query_entry else False),
    )

    payload_dict = response.dict()
    try:
        await redis_client.setex(cache_key, settings.cache_ttl_crosswalk, json.dumps(payload_dict))
    except redis.RedisError as exc:
        REDIS_FAILURES.labels(operation="set").inc()
        LOGGER.warning("Cache write failed: %s", exc)

    return payload_dict


@app.get("/health")
async def health_check():
    status_payload = {
        "service": settings.service_name,
        "database": "up" if state.pg_pool else "down",
        "cache": "up" if state.redis else "down",
        "circuit_breaker": {
            "failures": state.circuit_breaker.failures,
            "open": state.circuit_breaker.opened_at is not None,
        },
    }
    return JSONResponse(status_code=200, content=status_payload)


@app.get("/metrics")
async def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        reload=False,
    )
