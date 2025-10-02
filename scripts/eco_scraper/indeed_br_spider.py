import re
from urllib.parse import urljoin

import scrapy

from .base_spider import BaseEcoSpider


class IndeedBRSpider(BaseEcoSpider):
    name = "indeed_br"
    allowed_domains = ["br.indeed.com", "indeed.com.br", "www.indeed.com.br"]
    start_urls = [
        "https://br.indeed.com/jobs?q=ti&sort=date&fromage=7&lang=pt",
    ]

    custom_settings = BaseEcoSpider.custom_settings | {
        "JOB_SOURCE": "INDEED_BR",
        # Be extra conservative for Indeed
        "DOWNLOAD_DELAY": 5.0,
        "AUTOTHROTTLE_START_DELAY": 5.0,
        "AUTOTHROTTLE_MAX_DELAY": 30.0,
    }

    def parse(self, response, **kwargs):  # type: ignore[override]
        # Handle job cards (sponsored and organic)
        cards = response.css("div.job_seen_beacon, div.tapItem")
        for card in cards:
            title = (card.css("h2.jobTitle span::text").get() or "").strip()
            company = (card.css("span.companyName::text").get() or None)
            location = (card.css("div.companyLocation::text").get() or None)
            posting_date = (card.css("span.date::text").get() or None)
            url = card.css("a.jcs-JobTitle::attr(href), a.tapItem::attr(href)").get()
            if url:
                url = urljoin(response.url, url)

            job_title = self.extract_job_title(title)
            normalized_title = self.normalize_text(job_title)

            yield self.make_item(
                job_title=job_title,
                normalized_title=normalized_title,
                company=company,
                location=location,
                posting_date=posting_date,
                source_url=url,
                source=self.custom_settings.get("JOB_SOURCE"),
            )

        # Pagination: look for start parameter links
        next_href = response.css("a[aria-label='Próximo']::attr(href), a[aria-label='Next']::attr(href)").get()
        if not next_href:
            # Fallback: increment 'start' query param if present
            m = re.search(r"[?&]start=(\d+)", response.url)
            if m:
                start = int(m.group(1)) + 10
                base = re.sub(r"([?&]start=)\d+", rf"\g<1>{start}", response.url)
                next_href = base
        if next_href:
            yield response.follow(next_href, callback=self.parse)

