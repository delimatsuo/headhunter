import json
from scripts.json_repair import repair_json


def test_strip_code_fences_and_parse():
    raw = """```json\n{\n  \"ok\": true,\n}\n```"""
    data = repair_json(raw)
    assert isinstance(data, dict)
    assert data.get("ok") is True


def test_normalize_single_quotes():
    raw = "{'test': 123}"
    data = repair_json(raw)
    assert data["test"] == 123


def test_extract_json_from_surrounding_text():
    raw = "Noise before {\"x\": 5,} and after"
    data = repair_json(raw)
    assert data["x"] == 5

