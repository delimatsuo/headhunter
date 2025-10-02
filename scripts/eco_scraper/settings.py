import os

BOT_NAME = "eco_scraper"
SPIDER_MODULES = ["scripts.eco_scraper"]
NEWSPIDER_MODULE = "scripts.eco_scraper"

ROBOTSTXT_OBEY = True
DOWNLOAD_DELAY = 3
RANDOMIZE_DOWNLOAD_DELAY = 0.5
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 3
AUTOTHROTTLE_MAX_DELAY = 20
CONCURRENT_REQUESTS = 4
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Basic UA rotation list
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
]

DOWNLOADER_MIDDLEWARES = {
    "scripts.eco_scraper.middlewares.RandomUserAgentMiddleware": 400,
    "scripts.eco_scraper.middlewares.RateLimitMiddleware": 410,
    # Custom backoff middleware removed to avoid blocking sleeps; rely on RetryMiddleware + AutoThrottle
    # "scripts.eco_scraper.middlewares.ExponentialBackoffRetryMiddleware": 420,
    "scripts.eco_scraper.middlewares.CaptchaDetectionMiddleware": 430,
    "scripts.eco_scraper.middlewares.RequestLoggerMiddleware": 900,
}

LOG_LEVEL = "INFO"

ECO_ENABLE_SIMPLE_JSONL = int(os.getenv("ECO_ENABLE_SIMPLE_JSONL", "0"))

ITEM_PIPELINES = {
    "scripts.eco_scraper.pipelines.ValidationPipeline": 80,
    "scripts.eco_scraper.pipelines.DedupPipeline": 100,
    "scripts.eco_scraper.pipelines.TitleNormalizationPipeline": 200,
    "scripts.eco_scraper.pipelines.AliasDedupPipeline": 220,
    # Conditionally enable simple per-spider JSONL writer to avoid double local writes
    **({"scripts.eco_scraper.pipelines.JsonlWriterPipeline": 880} if ECO_ENABLE_SIMPLE_JSONL else {}),
    "scripts.eco_scraper.pipelines.CloudStoragePipeline": 900,
}

# ECO batch and retry settings
ECO_BATCH_SIZE = 1000
ECO_MAX_BATCH_BYTES = 5_000_000
ECO_MAX_RETRIES = 3
ECO_RETRY_BASE_DELAY = 2.0
ECO_CAPTCHA_COOLDOWN = 30.0
ECO_MIN_REQUEST_INTERVAL = 0.0
