from datetime import datetime
from typing import Dict, Any

import scrapy


class BaseEcoSpider(scrapy.Spider):
    name = "eco_base"
    custom_settings = {
        "DOWNLOAD_DELAY": 3.0,
        "RANDOMIZE_DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 3.0,
        "AUTOTHROTTLE_MAX_DELAY": 20.0,
        "ROBOTSTXT_OBEY": True,
        "USER_AGENT": "Mozilla/5.0 (compatible; ECO-Scraper/1.0; +https://example.com/bot)",
        "LOG_LEVEL": "INFO",
    }

    def parse(self, response, **kwargs):  # type: ignore[override]
        raise NotImplementedError

    def extract_job_title(self, text: str) -> str:
        return (text or "").strip()

    def normalize_text(self, text: str) -> str:
        try:
            import unidecode  # type: ignore
            t = unidecode.unidecode(text or "").lower()
        except Exception:
            t = (text or "").lower()
        return " ".join("".join(ch if ch.isalnum() or ch.isspace() else " " for ch in t).split())

    def make_item(self, **kwargs) -> Dict[str, Any]:
        return {
            "job_title": kwargs.get("job_title"),
            "normalized_title": kwargs.get("normalized_title"),
            "company": kwargs.get("company"),
            "location": kwargs.get("location"),
            "posting_date": kwargs.get("posting_date"),
            "source_url": kwargs.get("source_url"),
            "source": kwargs.get("source"),
            "fetched_at": datetime.utcnow().isoformat(),
        }

    def errback(self, failure):  # noqa: D401
        self.logger.error("Request failed: %s", failure)

