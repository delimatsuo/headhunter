"""
Validate ECO data quality and generate a concise report.
"""
import json
import os
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List


def iter_jsonl(path: str) -> Iterable[Dict]:
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for fn in files:
                if fn.endswith(".jsonl"):
                    with open(os.path.join(root, fn), encoding="utf-8") as f:
                        for line in f:
                            try:
                                yield json.loads(line)
                            except Exception:
                                continue
    else:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    yield json.loads(line)
                except Exception:
                    continue


def validate_scraped(path: str) -> Dict:
    total = 0
    missing_title = 0
    dup_urls = set()
    seen_urls = set()
    sources = Counter()
    for it in iter_jsonl(path):
        total += 1
        if not it.get("job_title") or not it.get("normalized_title"):
            missing_title += 1
        url = it.get("source_url")
        if url:
            if url in seen_urls:
                dup_urls.add(url)
            seen_urls.add(url)
        src = (it.get("source") or "").upper()
        if src:
            sources.update([src])
    return {
        "total_items": total,
        "missing_title_items": missing_title,
        "duplicate_urls": len(dup_urls),
        "source_breakdown": dict(sources.most_common()),
        "missing_rate": round(missing_title / total, 4) if total else 0.0,
        "dup_rate": round(len(dup_urls) / max(1, len(seen_urls)), 4),
    }


def main(path: str, out_path: str) -> None:
    report = {
        "scraped": validate_scraped(path),
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Wrote data quality report: {out_path}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Validate ECO data quality")
    p.add_argument("path", help="Path to scraped JSONL root (dir or file)")
    p.add_argument("--out", default="eco_reports/quality.json", help="Output report path")
    args = p.parse_args()
    main(args.path, args.out)

