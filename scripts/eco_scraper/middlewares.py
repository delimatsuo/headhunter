import random
from typing import List, Optional


class RandomUserAgentMiddleware:
    """Rotate User-Agent per request using settings.USER_AGENTS list."""

    def __init__(self, user_agents: List[str]):
        self.user_agents = user_agents or []

    @classmethod
    def from_crawler(cls, crawler):  # noqa: D401
        uas = crawler.settings.getlist("USER_AGENTS") or []
        return cls(uas)

    def process_request(self, request, spider):  # noqa: D401
        if self.user_agents:
            request.headers["User-Agent"] = random.choice(self.user_agents)
        return None


class ExponentialBackoffRetryMiddleware:
    """Retry with exponential backoff for transient errors (429/503/timeouts)."""

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay

    @classmethod
    def from_crawler(cls, crawler):  # noqa: D401
        return cls(
            max_retries=int(crawler.settings.getint("ECO_MAX_RETRIES", 3)),
            base_delay=float(crawler.settings.getfloat("ECO_RETRY_BASE_DELAY", 2.0)),
        )

    def process_response(self, request, response, spider):  # noqa: D401
        if response.status in (429, 503):
            retries = request.meta.get("eco_retry", 0)
            if retries < self.max_retries:
                request.meta["eco_retry"] = retries + 1
                # rely on Scrapy RetryMiddleware + AutoThrottle for pacing
                request.dont_filter = True
                spider.logger.info(
                    "Retrying (status=%s, attempt=%s) without blocking sleep", response.status, retries + 1
                )
                return request
        return response

    def process_exception(self, request, exception, spider):  # noqa: D401
        retries = request.meta.get("eco_retry", 0)
        if retries < self.max_retries:
            request.meta["eco_retry"] = retries + 1
            request.dont_filter = True
            spider.logger.info("Retrying after exception (attempt=%s): %s", retries + 1, exception)
            return request
        return None


class CaptchaDetectionMiddleware:
    """Detect simple CAPTCHA markers and pause scraping for a cooldown period."""

    def __init__(self, cooldown_seconds: float = 30.0):
        self.cooldown_seconds = cooldown_seconds

    @classmethod
    def from_crawler(cls, crawler):  # noqa: D401
        return cls(cooldown_seconds=float(crawler.settings.getfloat("ECO_CAPTCHA_COOLDOWN", 30.0)))

    def process_response(self, request, response, spider):  # noqa: D401
        body = response.text.lower()
        if any(k in body for k in ["captcha", "robot", "solve the challenge"]):
            # Avoid blocking reactor; rely on AutoThrottle and provider pacing
            spider.logger.warning(
                "CAPTCHA detected; skipping blocking sleep (cooldown=%ss suggested)", self.cooldown_seconds
            )
        return response


class RateLimitMiddleware:
    """Simple per-request min delay on top of Scrapy delays."""

    def __init__(self, min_delay: float = 0.0):
        self.min_delay = min_delay
        self._last_time: Optional[float] = None

    @classmethod
    def from_crawler(cls, crawler):  # noqa: D401
        return cls(min_delay=float(crawler.settings.getfloat("ECO_MIN_REQUEST_INTERVAL", 0.0)))

    def process_request(self, request, spider):  # noqa: D401
        # Avoid blocking sleeps; Scrapy's DOWNLOAD_DELAY + AUTOTHROTTLE manage pacing
        return None


class RequestLoggerMiddleware:
    def process_request(self, request, spider):  # noqa: D401
        spider.logger.debug("Request: %s", request.url)
        return None

    def process_response(self, request, response, spider):  # noqa: D401
        spider.logger.debug("Response %s: %s", response.status, response.url)
        return response
