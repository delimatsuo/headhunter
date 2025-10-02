#!/usr/bin/env python3
"""Ad-hoc Together AI connectivity test for CI pipelines."""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict

from scripts.together_ai_processor import TogetherAIProcessor


logger = logging.getLogger(__name__)


async def main() -> int:
    """Exercise TogetherAIProcessor end to end with a minimal candidate."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key:
        logger.error("TOGETHER_API_KEY environment variable is required for the connectivity test.")
        return 1

    candidate: Dict[str, Any] = {
        "id": "ci_test_candidate",
        "name": "CI Test Candidate",
        "experience": "Senior software engineer with 7 years of Python and cloud experience.",
        "education": "B.S. in Computer Science, Sample University",
        "comments": [
            {"text": "Strong engineering fundamentals and leadership experience."}
        ],
    }

    try:
        async with TogetherAIProcessor(api_key, use_firestore=False) as processor:
            result = await processor.process_candidate(candidate)
    except Exception as exc:
        logger.exception("TogetherAIProcessor raised an exception: %s", exc)
        return 1

    if not result:
        logger.error("TogetherAIProcessor returned no result for the test candidate.")
        return 1

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
