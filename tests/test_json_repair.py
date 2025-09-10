import json
from scripts.json_repair import repair_json


def assert_parses(s: str):
    fixed = repair_json(s)
    assert isinstance(fixed, dict)
    # Ensure it can be dumped cleanly
    json.dumps(fixed)
    return fixed


def test_repairs_code_fences_and_trailing_commas():
    broken = """
```json
{"a": 1, "b": [1,2,3,],}
```
"""
    out = assert_parses(broken)
    assert out["a"] == 1 and out["b"] == [1, 2, 3]


def test_repairs_unterminated_string_and_backticks():
    broken = '{"text": "hello world, this is unterminated, `backticks`}\n'
    out = assert_parses(broken)
    assert out["text"].startswith("hello world")


def test_repairs_brace_mismatch_simple():
    broken = '{"x": {"y": 1, "z": [1,2,3]}\n'
    out = assert_parses(broken)
    assert out["x"]["z"][-1] == 3

