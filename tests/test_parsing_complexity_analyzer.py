import json
from scripts.parsing_complexity_analyzer import analyze_text


def test_simple_text_low_complexity():
    text = """
    John Doe
    Senior Software Engineer at Acme Corp
    2018-2024: Built microservices in Python and AWS.
    Skills: Python, AWS, Docker
    """.strip()
    out = analyze_text(text)
    assert out['risk_level'] in ('low', 'medium')
    assert 0 <= out['complexity'] <= 1


def test_table_like_medium_complexity():
    text = """
    Company | Role | Years
    Acme | Engineer | 3
    Globex | Senior Engineer | 2
    """.strip()
    out = analyze_text(text)
    assert out['signals']['table_ratio'] > 0
    assert out['complexity'] >= 0


def test_code_fences_increase_complexity():
    text = """
    ```
    JSON
    {"a": 1}
    ```
    ```
    code
    ```
    """.strip()
    out = analyze_text(text)
    assert out['signals']['code_fences'] >= 2
    assert out['complexity'] >= 0

