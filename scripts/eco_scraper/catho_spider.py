from urllib.parse import urljoin

import scrapy

from .base_spider import BaseEcoSpider


class CathoSpider(BaseEcoSpider):
    name = "catho"
    allowed_domains = ["www.catho.com.br", "catho.com.br"]
    start_urls = [
        "https://www.catho.com.br/vagas/ti/?ordem=maior-data",
    ]

    custom_settings = BaseEcoSpider.custom_settings | {
        "JOB_SOURCE": "CATHO",
    }

    def parse(self, response, **kwargs):  # type: ignore[override]
        # Listing cards
        cards = response.css("div.job-card, li.result-item, div.card-vaga")
        for card in cards:
            title = (card.css("a::text").get() or "").strip()
            if not title:
                title = (card.css("h2 a::text").get() or "").strip()

            company = card.css("span.company::text, span.employer::text, p.company::text").get()
            location = card.css("span.location::text, p.location::text, span.job-city::text").get()
            posting_date = card.css("time::attr(datetime), span.date::text").get()
            url = card.css("a::attr(href)").get()
            if url:
                url = urljoin(response.url, url)

            job_title = self.extract_job_title(title)
            normalized_title = self.normalize_text(job_title)

            yield self.make_item(
                job_title=job_title,
                normalized_title=normalized_title,
                company=(company or None),
                location=(location or None),
                posting_date=(posting_date or None),
                source_url=url,
                source=self.custom_settings.get("JOB_SOURCE"),
            )

        # Pagination
        next_page = response.css("a[rel='next']::attr(href), a.next::attr(href), li.pagination-next a::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

