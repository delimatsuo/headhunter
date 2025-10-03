"""
Aggregate scraped job postings into ECO aliases and occupations.

Reads JSONL files from a directory or GCS prefix and produces aggregated alias
stats with confidence scores, plus optional SQL upserts.
"""
import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List

try:
    from scripts.eco_title_normalizer import normalize_title_ptbr  # type: ignore
except Exception:  # pragma: no cover
    def normalize_title_ptbr(s: str) -> str:  # type: ignore
        return (s or "").lower()

from scripts.alias_confidence_scorer import AliasConfidenceScorer


def _iter_local_jsonl(path: str) -> Iterable[Dict]:
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for fn in files:
                if fn.endswith(".jsonl"):
                    with open(os.path.join(root, fn), encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                yield json.loads(line)
                            except Exception:
                                continue
    else:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue


def _iter_gcs_jsonl(uri: str) -> Iterable[Dict]:  # gs://bucket/prefix
    try:
        from google.cloud import storage  # type: ignore
    except Exception:  # pragma: no cover
        raise RuntimeError("google-cloud-storage not installed; cannot read GCS")

    assert uri.startswith("gs://")
    _, rest = uri.split("gs://", 1)
    bucket_name, prefix = rest.split("/", 1)
    client = storage.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    bucket = client.bucket(bucket_name)
    for blob in client.list_blobs(bucket, prefix=prefix):
        if not blob.name.endswith(".jsonl"):
            continue
        for line in blob.download_as_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


@dataclass
class AliasAggregate:
    normalized_title: str
    alias_examples: Counter
    companies: Counter
    sources: Counter
    total: int


def aggregate_items(items: Iterable[Dict]) -> Dict[str, AliasAggregate]:
    agg: Dict[str, AliasAggregate] = {}
    for it in items:
        title = it.get("job_title") or ""
        norm = it.get("normalized_title") or normalize_title_ptbr(title)
        comp = it.get("company") or ""
        src = (it.get("source") or "").upper()
        if norm not in agg:
            agg[norm] = AliasAggregate(norm, Counter(), Counter(), Counter(), 0)
        a = agg[norm]
        a.alias_examples.update([title])
        a.companies.update([comp])
        a.sources.update([src])
        a.total += 1
    return agg


def score_aliases(agg: Dict[str, AliasAggregate]) -> List[Dict]:
    scorer = AliasConfidenceScorer()
    out: List[Dict] = []
    for norm, a in agg.items():
        total = a.total
        for alias, freq in a.alias_examples.items():
            # Choose the most frequent source for trust
            top_src = a.sources.most_common(1)[0][0] if a.sources else None
            score = scorer.score(alias, None, norm, freq, total, source=top_src)
            out.append({
                "alias": alias,
                "normalized_alias": normalize_title_ptbr(alias),
                "canonical_normalized": norm,
                "frequency": freq,
                "total_for_norm": total,
                "top_source": top_src,
                "confidence": round(score, 4),
            })
    return out


def write_summary(output_path: str, rows: List[Dict]) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(input_uri: str, out_dir: str) -> None:
    if input_uri.startswith("gs://"):
        it = _iter_gcs_jsonl(input_uri)
    else:
        it = _iter_local_jsonl(input_uri)
    agg = aggregate_items(it)
    scored = score_aliases(agg)
    date = datetime.utcnow().strftime("%Y%m%d")
    out_path = os.path.join(out_dir, f"alias_summary_{date}.jsonl")
    write_summary(out_path, scored)
    print(f"Aggregated {len(scored)} aliases -> {out_path}")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Batch process ECO aliases from scraped JSONL")
    p.add_argument("input", help="Directory/file path or gs://bucket/prefix of JSONL postings")
    p.add_argument("--out", default="eco_aggregates", help="Output directory")
    args = p.parse_args()

    main(args.input, args.out)
