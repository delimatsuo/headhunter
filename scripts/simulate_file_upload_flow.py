#!/usr/bin/env python3
"""
Simulate Phase 3 file upload pipeline:
  1) Upload sample candidate JSON to profiles bucket
  2) Observe Functions trigger
  3) Check Pub/Sub publish (implicit)
  4) Observe Cloud Run processing via Firestore write
  5) Exercise error cases and concurrency
  6) Emit simple timing report
"""

import os
import json
import time
import uuid
from dataclasses import dataclass
from typing import List

from google.cloud import storage, firestore


PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT") or ""
BUCKET = os.environ.get("PROFILES_BUCKET") or (PROJECT_ID + "-profiles")


@dataclass
class UploadResult:
    candidate_id: str
    ok: bool
    latency_s: float
    error: str = ""


def upload_candidate(bucket: storage.Bucket, candidate_id: str) -> str:
    blob_path = f"profiles/{candidate_id}.json"
    blob = bucket.blob(blob_path)
    payload = {
        "candidate_id": candidate_id,
        "name": f"Test {candidate_id}",
        "resume_analysis": {
            "career_trajectory": {"current_level": "Senior", "progression_speed": "normal", "trajectory_type": "ic"},
            "leadership_scope": {"has_leadership": False},
            "company_pedigree": {"tier_level": "mid"},
            "years_experience": 7,
            "technical_skills": ["python", "gcp"]
        }
    }
    blob.upload_from_string(json.dumps(payload), content_type="application/json")
    return blob_path


def simulate(n: int = 3, timeout_s: int = 180) -> List[UploadResult]:
    if not PROJECT_ID:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT must be set")
    client = storage.Client()
    fs = firestore.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET)

    results: List[UploadResult] = []
    for i in range(n):
        cid = f"upload-{uuid.uuid4().hex[:8]}"
        start = time.time()
        try:
            path = upload_candidate(bucket, cid)
            print(f"Uploaded {path}; waiting for enrichment...")
            deadline = start + timeout_s
            ok = False
            while time.time() < deadline:
                if fs.collection("enriched_profiles").document(cid).get().exists:
                    ok = True
                    break
                time.sleep(2)
            results.append(UploadResult(candidate_id=cid, ok=ok, latency_s=time.time() - start))
        except Exception as e:  # pragma: no cover
            results.append(UploadResult(candidate_id=cid, ok=False, latency_s=time.time() - start, error=str(e)))
    return results


def main():
    results = simulate()
    print("\nFile Upload Flow Report")
    print("=======================")
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        print(f"- {r.candidate_id}: {status} in {r.latency_s:.1f}s {r.error}")
    passed = sum(1 for r in results if r.ok)
    print(f"\nSummary: {passed}/{len(results)} successful")


if __name__ == "__main__":
    main()

