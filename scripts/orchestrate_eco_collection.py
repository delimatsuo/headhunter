"""
Master orchestration for ECO data collection.

Phases:
 1) Run spiders (vagas, infojobs, catho, indeed_br)
 2) Aggregate aliases and score
 3) Optionally load aliases into DB
 4) Optionally process CBO crosswalk
"""
import importlib
import os
from datetime import datetime

from scrapy.crawler import CrawlerRunner  # type: ignore
from scrapy.settings import Settings  # type: ignore
from twisted.internet import defer, reactor  # type: ignore


def run_spiders():
    # Ensure Scrapy loads our project settings explicitly
    settings = Settings()
    settings.setmodule("scripts.eco_scraper.settings")

    # Log enabled components for verification
    d_mw = dict(settings.getdict("DOWNLOADER_MIDDLEWARES") or {})
    i_pipes = dict(settings.getdict("ITEM_PIPELINES") or {})
    print("Enabled DOWNLOADER_MIDDLEWARES:")
    for k, v in sorted(d_mw.items(), key=lambda x: x[1]):
        print(f"  {k}: {v}")
    print("Enabled ITEM_PIPELINES:")
    for k, v in sorted(i_pipes.items(), key=lambda x: x[1]):
        print(f"  {k}: {v}")

    runner = CrawlerRunner(settings)

    # Import spider classes
    from scripts.eco_scraper.vagas_spider import VagasSpider  # noqa: F401
    from scripts.eco_scraper.infojobs_spider import InfoJobsSpider  # noqa: F401
    from scripts.eco_scraper.catho_spider import CathoSpider  # noqa: F401
    from scripts.eco_scraper.indeed_br_spider import IndeedBRSpider  # noqa: F401

    spiders = [
        "scripts.eco_scraper.vagas_spider.VagasSpider",
        "scripts.eco_scraper.infojobs_spider.InfoJobsSpider",
        "scripts.eco_scraper.catho_spider.CathoSpider",
        "scripts.eco_scraper.indeed_br_spider.IndeedBRSpider",
    ]

    @defer.inlineCallbacks
    def crawl_sequentially():
        for sp in spiders:
            module_name, cls_name = sp.rsplit(".", 1)
            mod = importlib.import_module(module_name)
            cls = getattr(mod, cls_name)
            yield runner.crawl(cls)
        reactor.stop()

    crawl_sequentially()
    reactor.run()


def run_batch_aggregation():
    from scripts.batch_alias_processor import main as agg_main

    date = datetime.utcnow().strftime("%Y%m%d")
    raw_dir = os.environ.get("ECO_OUTPUT_DIR", f"eco_raw/{date}")
    agg_out = os.environ.get("ECO_AGG_OUT", "eco_aggregates")
    agg_main(raw_dir, agg_out)
    return agg_out


def maybe_load_aliases(agg_out: str, do_load: bool):
    if not do_load:
        return
    # Pick latest alias_summary_*.jsonl
    files = sorted([f for f in os.listdir(agg_out) if f.startswith("alias_summary_") and f.endswith(".jsonl")])
    if not files:
        print("No aggregate files to load")
        return
    latest = os.path.join(agg_out, files[-1])
    import asyncio
    from scripts.load_eco_aliases import main as load_main
    asyncio.run(load_main(latest, mode="jsonl"))


def maybe_process_cbo(do_cbo: bool):
    if not do_cbo:
        return
    from scripts.process_cbo_dataset import main as cbo_main
    import asyncio
    cbo_csv = os.environ.get("CBO_CSV_PATH")
    if not cbo_csv:
        print("CBO_CSV_PATH not set; skipping CBO processing")
        return
    out_dir = os.environ.get("CBO_OUT_DIR", "eco_cbo")
    asyncio.run(cbo_main(cbo_csv, out_dir, lookup_db=True))


def main():
    run_spiders()
    agg_out = run_batch_aggregation()
    maybe_load_aliases(agg_out, do_load=bool(os.environ.get("ECO_LOAD_ALIASES", "1") == "1"))
    maybe_process_cbo(do_cbo=bool(os.environ.get("ECO_PROCESS_CBO", "0") == "1"))
    print("Orchestration complete")


if __name__ == "__main__":
    main()
