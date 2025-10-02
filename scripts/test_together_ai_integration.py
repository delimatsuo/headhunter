#!/usr/bin/env python3
"""
Standalone Together AI integration test using the Cloud Run worker client.

Validates:
- API connectivity and auth
- Candidate enrichment prompt + JSON parsing
- Error handling and performance metrics
- Health check endpoint of the client
"""

import argparse
import asyncio
import json
import os
import time
from typing import Any, Dict

# Allow running from repo root
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cloud_run_worker.config import Config
from cloud_run_worker.together_ai_client import TogetherAIClient


async def run_test(sample_candidate: Dict[str, Any]) -> Dict[str, Any]:
    cfg = Config(testing=False)
    client = TogetherAIClient(cfg)
    await client.initialize()
    try:
        t0 = time.perf_counter()
        enriched = await client.enrich_candidate(sample_candidate)
        dt = time.perf_counter() - t0
        ok = (
            isinstance(enriched, dict)
            and "resume_analysis" in enriched
            and "recruiter_insights" in enriched
            and "overall_score" in enriched
        )
        health = await client.health_check()
        return {
            "status": "pass" if ok and health else "fail",
            "latency_s": dt,
            "health": health,
            "model": cfg.together_ai_model,
            "response_keys": list(enriched.keys()) if isinstance(enriched, dict) else [],
        }
    finally:
        await client.shutdown()


def example_candidate() -> Dict[str, Any]:
    return {
        "name": "Jordan Smith",
        "resume_text": (
            "Senior software engineer with 8 years experience in Python, FastAPI, and GCP. "
            "Led migration to Cloud Run and implemented CI/CD."
        ),
        "recruiter_comments": "Strong backend skills, some leadership exposure, good communicator.",
        "metadata": {"years_experience": 8, "technical_skills": ["Python", "GCP", "Docker"]},
    }


def main():
    parser = argparse.ArgumentParser(description="Test Together AI integration")
    parser.add_argument("--print-response", action="store_true", help="Print the raw enriched response")
    args = parser.parse_args()

    # Ensure API key presence early for friendlier error
    if not os.getenv("TOGETHER_API_KEY") and not os.getenv("TOGETHER_AI_MODEL"):
        print("Warning: TOGETHER_API_KEY is not set. This test may fail authentication.")

    result = asyncio.run(run_test(example_candidate()))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

