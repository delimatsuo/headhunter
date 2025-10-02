#!/usr/bin/env python3
"""Manage production-safe validation data for Headhunter deployments."""
import argparse
import json
import logging
import random
import string
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
  from google.cloud import firestore  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
  firestore = None

LOGGER = logging.getLogger("production_test_data_manager")


@dataclass
class TenantDataset:
  tenant_id: str
  profiles: int
  jobs: int
  skills: List[str]


def load_config(path: Path) -> Dict[str, Any]:
  with path.open("r", encoding="utf-8") as fh:
    return yaml.safe_load(fh)


def random_id(prefix: str) -> str:
  return f"{prefix}-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


class TestDataManager:
  def __init__(self, project_id: str, datasets: List[TenantDataset], dry_run: bool = False) -> None:
    self.project_id = project_id
    self.datasets = datasets
    self.dry_run = dry_run
    self.client = firestore.Client(project=project_id) if firestore else None

  def seed(self) -> Dict[str, Any]:
    results = []
    for dataset in self.datasets:
      LOGGER.info("Seeding tenant %s", dataset.tenant_id)
      profiles = [self._profile_payload(dataset.tenant_id) for _ in range(dataset.profiles)]
      jobs = [self._job_payload(dataset.tenant_id) for _ in range(dataset.jobs)]
      if self.client and not self.dry_run:
        self._write_batch(dataset.tenant_id, "profiles", profiles)
        self._write_batch(dataset.tenant_id, "jobs", jobs)
      results.append({"tenant": dataset.tenant_id, "profiles": len(profiles), "jobs": len(jobs)})
    return {"mode": "seed", "results": results}

  def cleanup(self) -> Dict[str, Any]:
    if not self.client and not self.dry_run:
      raise RuntimeError("Firestore client unavailable")
    summary: List[Dict[str, Any]] = []
    for dataset in self.datasets:
      if self.client and not self.dry_run:
        batch = self.client.batch()
        collection = self.client.collection(f"tenants/{dataset.tenant_id}/profiles")
        for doc in collection.stream():
          batch.delete(doc.reference)
        collection_jobs = self.client.collection(f"tenants/{dataset.tenant_id}/jobs")
        for doc in collection_jobs.stream():
          batch.delete(doc.reference)
        batch.commit()
      summary.append({"tenant": dataset.tenant_id, "removed": True})
    return {"mode": "cleanup", "results": summary}

  def list(self) -> Dict[str, Any]:
    summary: List[Dict[str, Any]] = []
    if self.client:
      for dataset in self.datasets:
        profile_collection = self.client.collection(f"tenants/{dataset.tenant_id}/profiles")
        job_collection = self.client.collection(f"tenants/{dataset.tenant_id}/jobs")
        summary.append({
          "tenant": dataset.tenant_id,
          "profiles": len(list(profile_collection.limit(5).stream())),
          "jobs": len(list(job_collection.limit(5).stream())),
        })
    return {"mode": "list", "results": summary}

  def refresh(self) -> Dict[str, Any]:
    cleanup = self.cleanup()
    seed = self.seed()
    return {"mode": "refresh", "cleanup": cleanup, "seed": seed}

  def _write_batch(self, tenant_id: str, collection: str, rows: List[Dict[str, Any]]) -> None:
    assert self.client is not None
    batch = self.client.batch()
    for row in rows:
      ref = self.client.document(f"tenants/{tenant_id}/{collection}/{row['id']}")
      batch.set(ref, row)
    batch.commit()

  def _profile_payload(self, tenant_id: str) -> Dict[str, Any]:
    return {
      "id": random_id("profile"),
      "tenant_id": tenant_id,
      "name": random.choice(["Alex", "Jordan", "Taylor", "Morgan"]),
      "title": random.choice(["Senior Engineer", "Product Manager", "Data Scientist"]),
      "skills": random.sample(["python", "go", "gcp", "terraform", "ml"], k=3),
      "years_experience": random.randint(2, 15),
    }

  def _job_payload(self, tenant_id: str) -> Dict[str, Any]:
    return {
      "id": random_id("job"),
      "tenant_id": tenant_id,
      "title": random.choice(["Backend Engineer", "Site Reliability Engineer", "ML Engineer"]),
      "description": "Production validation benchmark job.",
      "location": random.choice(["Remote", "New York", "San Francisco"]),
      "requirements": random.sample(["python", "distributed systems", "microservices", "sql"], k=3),
    }


def parse_tenant_config(path: Path) -> List[TenantDataset]:
  config = load_config(path)
  datasets = []
  for entry in config.get("tenantIsolation", {}).get("tenants", []):
    datasets.append(
      TenantDataset(
        tenant_id=entry["tenantId"],
        profiles=entry.get("profileCount", 10),
        jobs=entry.get("jobCount", 5),
        skills=entry.get("skills", ["python", "gcp", "ml"]),
      )
    )
  if not datasets:
    datasets.append(TenantDataset("tenant-alpha", profiles=10, jobs=5, skills=["python", "gcp", "ml"]))
  return datasets


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Manage production validation data")
  parser.add_argument("mode", choices=["seed", "cleanup", "refresh", "list"])
  parser.add_argument("--config", default="config/testing/production-test-config.yaml")
  parser.add_argument("--project-id", required=True)
  parser.add_argument("--dry-run", action="store_true")
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
  args = parse_args(argv)
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
  datasets = parse_tenant_config(Path(args.config))
  manager = TestDataManager(project_id=args.project_id, datasets=datasets, dry_run=args.dry_run)
  if args.mode == "seed":
    result = manager.seed()
  elif args.mode == "cleanup":
    result = manager.cleanup()
  elif args.mode == "refresh":
    result = manager.refresh()
  else:
    result = manager.list()
  print(json.dumps(result, indent=2))
  return 0


if __name__ == "__main__":
  sys.exit(main())
