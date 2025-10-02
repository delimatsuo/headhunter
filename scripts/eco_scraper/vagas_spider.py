from datetime import datetime
from urllib.parse import urljoin

import scrapy

from .base_spider import BaseEcoSpider


class VagasSpider(BaseEcoSpider):
    name = "vagas"
    allowed_domains = ["www.vagas.com.br", "vagas.com.br"]
    start_urls = [
        "https://www.vagas.com.br/vagas-de-ti?ordenar_por=mais-recentes",
    ]

    custom_settings = BaseEcoSpider.custom_settings | {
        "JOB_SOURCE": "VAGAS",
    }

    def parse(self, response, **kwargs):  # type: ignore[override]
        cards = response.css("li.lista-de-vagas__vaga")
        for card in cards:
            title = card.css("h2 a::text").get() or ""
            company = card.css("span.empr::text").get() or None
            location = card.css("span.vaga-local::text").get() or None
            posting_date = card.css("span.data-publicacao::text").get() or None
            url = card.css("h2 a::attr(href)").get()
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

        # Pagination
        next_page = response.css("a.proximo::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

