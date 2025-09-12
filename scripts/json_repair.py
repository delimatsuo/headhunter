import json
import re
from typing import Any, Dict


def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # Remove starting fence with optional language
        s = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", s, count=1)
    if s.endswith("```"):
        s = s[: -3]
    return s.strip()


def _remove_trailing_commas(s: str) -> str:
    # Remove trailing commas before } or ]
    s = re.sub(r",\s*(\}|\])", r"\1", s)
    return s


def _normalize_quotes(s: str) -> str:
    # Prefer double quotes for keys/strings when obviously using single quotes JSON-like
    # Be conservative to avoid breaking valid JSON
    if '"' not in s and "'" in s:
        s = s.replace("'", '"')
    return s


def repair_json(raw: str) -> Dict[str, Any]:
    """Attempt to repair common JSON formatting issues and return parsed dict.

    Heuristics:
    - Strip Markdown code fences
    - Remove trailing commas before closing braces/brackets
    - Normalize quotes if only single quotes are present
    - Trim extraneous text before/after JSON by locating the first { and last }
    """
    s = _strip_code_fences(raw)

    # Extract JSON object boundaries if extra text is present
    start = s.find('{')
    end = s.rfind('}')
    if start != -1 and end != -1 and end > start:
        s = s[start : end + 1]

    s = _remove_trailing_commas(s)
    s = _normalize_quotes(s)

    # Try direct parse
    return json.loads(s)

