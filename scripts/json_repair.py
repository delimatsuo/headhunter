import json
import re
from typing import Any, Dict


_FENCE_RE = re.compile(r"^```json\s*|```$", re.IGNORECASE | re.MULTILINE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _strip_code_fences(s: str) -> str:
    return _FENCE_RE.sub("", s.strip())


def _clip_to_json_braces(s: str) -> str:
    # Keep content between first "{" and last "}"
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1]
    return s


def _normalize_quotes(s: str) -> str:
    # Replace common smart quotes with standard quotes; drop backticks to avoid breaking strings
    s = s.replace("`", '')
    s = s.replace("“", '"').replace("”", '"')
    return s


def _remove_trailing_commas(s: str) -> str:
    # Remove commas before closing braces/brackets
    while True:
        new_s = _TRAILING_COMMA_RE.sub(r"\1", s)
        if new_s == s:
            return s
        s = new_s


def _balance_brackets(s: str) -> str:
    # Best-effort: append missing closing braces/brackets if counts mismatch
    open_curly = s.count("{")
    close_curly = s.count("}")
    open_brack = s.count("[")
    close_brack = s.count("]")
    if close_curly < open_curly:
        s += "}" * (open_curly - close_curly)
    if close_brack < open_brack:
        s += "]" * (open_brack - close_brack)
    return s


def repair_json(s: str) -> Dict[str, Any]:
    """Attempt to repair common JSON issues from LLM output and parse to dict.

    Fixes:
    - Removes ```json fences
    - Clips to the outermost {...} block
    - Normalizes quotes/backticks
    - Removes trailing commas
    - Balances braces/brackets
    """
    candidates = []
    s1 = _strip_code_fences(s)
    s2 = _clip_to_json_braces(s1)
    s3 = _normalize_quotes(s2)
    s4 = _remove_trailing_commas(s3)
    s5 = _balance_brackets(s4)
    candidates.extend([s5, s4, s3, s2])

    # If quotes are unbalanced, attempt to close the last string before final brace
    if s5.count('"') % 2 == 1 and '}' in s5:
        last_brace = s5.rfind('}')
        if last_brace != -1:
            s5_fixed = s5[:last_brace] + '"' + s5[last_brace:]
            candidates.insert(0, s5_fixed)

    for c in candidates:
        try:
            return json.loads(c)
        except Exception:
            continue

    # Last resort: try to close an unterminated string by appending a quote
    try:
        return json.loads(s5 + '"')
    except Exception as e:
        raise json.JSONDecodeError(f"Failed to repair JSON: {e}", s, 0)
