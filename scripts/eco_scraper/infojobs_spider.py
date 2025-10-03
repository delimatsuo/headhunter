from urllib.parse import urljoin


from .base_spider import BaseEcoSpider


class InfoJobsSpider(BaseEcoSpider):
    name = "infojobs"
    allowed_domains = ["www.infojobs.com.br", "infojobs.com.br"]
    start_urls = [
        "https://www.infojobs.com.br/empregos.aspx?Palabra=ti",
    ]

    custom_settings = BaseEcoSpider.custom_settings | {
        "JOB_SOURCE": "INFOJOBS",
    }

    def parse(self, response, **kwargs):  # type: ignore[override]
        cards = response.css("div.element-vaga, div.card-vaga")
        for card in cards:
            try:
                title = (card.css("h2 a::text, a.js_openVaga::text").get() or "").strip()
                company = (card.css("span.empresas span::text, span.empresas a::text, p.empresa::text").get() or None)
                location = (card.css("span.blocos-localizacao::text, span.local::text").get() or None)
                url = card.css("h2 a::attr(href), a.js_openVaga::attr(href)").get()
                if url:
                    url = urljoin(response.url, url)

                job_title = self.extract_job_title(title)
                normalized_title = self.normalize_text(job_title)

                yield self.make_item(
                    job_title=job_title,
                    normalized_title=normalized_title,
                    company=company,
                    location=location,
                    posting_date=None,
                    source_url=url,
                    source=self.custom_settings.get("JOB_SOURCE"),
                )
            except Exception as e:
                self.logger.warning("Failed to parse card: %s", e)

        next_page = (
            response.css("a.next::attr(href), a[rel='next']::attr(href), li.pagination-next a::attr(href)").get()
        )
        if next_page:
            yield response.follow(next_page, callback=self.parse)
