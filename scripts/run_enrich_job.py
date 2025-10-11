#!/usr/bin/env python3
"""Run a single candidate enrichment job using the Cloud Run worker components."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import logging
from pathlib import Path
from typing import Any, Dict

# Ensure stdout is unbuffered for immediate log visibility
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Ensure repository root is on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cloud_run_worker.candidate_processor import CandidateProcessor  # noqa: E402
from cloud_run_worker.config import Config  # noqa: E402


async def _run(args: argparse.Namespace) -> Dict[str, Any]:
    config = Config(testing=args.testing)
    processor = CandidateProcessor(config)

    await processor.initialize()
    try:
        result = await processor.process_single_candidate(args.candidate_id)

        candidate_doc = await processor.firestore_client.get_candidate(args.candidate_id)

        payload: Dict[str, Any] = {
            "status": result.status,
            "candidate_id": result.candidate_id,
            "processing_time_seconds": result.processing_time_seconds,
            "timestamp": result.timestamp,
        }

        if candidate_doc:
            payload["candidate"] = candidate_doc

        return payload
    finally:
        await processor.shutdown()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a single enrichment job")
    parser.add_argument("--candidate-id", required=True, help="Candidate identifier")
    parser.add_argument("--testing", action="store_true", help="Use Config(testing=True)")
    parser.add_argument("--json", action="store_true", help="Print JSON result to stdout")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = asyncio.run(_run(args))
    except Exception as exc:  # pragma: no cover - surfaced to caller
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1

    if args.json:
        print(json.dumps(result))
    else:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
