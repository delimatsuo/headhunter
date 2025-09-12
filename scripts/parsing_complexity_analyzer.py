import re
import json
from typing import Dict, Any


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator > 0 else 0.0


def analyze_text(text: str) -> Dict[str, Any]:
    """Lightweight, deterministic parsing complexity analyzer.

    Produces metrics that help choose prompt/repair strategies and batching.
    No external libs or network required.
    """
    raw_len = len(text)
    lines = text.splitlines()
    line_count = len(lines)
    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)
    unique_words = len(set(w.lower() for w in words))

    # Heuristics
    non_ascii = sum(1 for ch in text if ord(ch) > 126)
    digits = sum(1 for ch in text if ch.isdigit())
    punctuation = sum(1 for ch in text if re.match(r"[.,;:!?'\-]", ch))
    bullet_lines = sum(1 for ln in lines if re.match(r"\s*([-*•]|\d+\.)\s", ln))
    table_like_lines = sum(1 for ln in lines if ln.count('|') >= 2)
    code_fences = text.count("```")
    json_braces = text.count('{') + text.count('}')
    url_hits = len(re.findall(r"https?://\S+", text))
    linkedin_hits = len(re.findall(r"https?://(www\.)?linkedin\.com/in/[\w\-_/]+", text))
    email_hits = len(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text))

    # Sentence stats
    sentences = re.split(r"[.!?]+\s+", text)
    sentences = [s for s in sentences if s.strip()]
    avg_sentence_words = round(sum(len(s.split()) for s in sentences) / len(sentences), 2) if sentences else 0

    # Noise proxies
    non_ascii_ratio = _ratio(non_ascii, raw_len)
    punctuation_ratio = _ratio(punctuation, raw_len)
    digit_ratio = _ratio(digits, raw_len)
    bullet_ratio = _ratio(bullet_lines, max(1, line_count))
    table_ratio = _ratio(table_like_lines, max(1, line_count))

    # Complexity scoring (0–1)
    # Higher is more complex/risky to parse deterministically
    complexity = 0.0
    complexity += min(0.3, non_ascii_ratio * 1.5)
    complexity += min(0.2, table_ratio * 2.0)
    complexity += min(0.15, bullet_ratio * 0.8)
    complexity += min(0.15, _ratio(code_fences, max(1, line_count)) * 3.0)
    complexity += 0.1 if json_braces > 50 else 0.0
    complexity = round(min(1.0, complexity), 3)

    # Strategy suggestions
    risk_level = (
        'high' if complexity >= 0.7 else 'medium' if complexity >= 0.4 else 'low'
    )

    max_chunk_chars = 20000 if risk_level == 'low' else 12000 if risk_level == 'medium' else 8000
    recommended_retries = 0 if risk_level == 'low' else 1 if risk_level == 'medium' else 2

    prompt_variant = 'concise_enriched' if risk_level == 'low' else 'guarded_enriched'
    repair_likelihood = 0.05 if risk_level == 'low' else 0.12 if risk_level == 'medium' else 0.22

    out: Dict[str, Any] = {
        'stats': {
            'raw_len': raw_len,
            'line_count': line_count,
            'word_count': word_count,
            'unique_words': unique_words,
            'avg_sentence_words': avg_sentence_words,
        },
        'signals': {
            'non_ascii_ratio': non_ascii_ratio,
            'punctuation_ratio': punctuation_ratio,
            'digit_ratio': digit_ratio,
            'bullet_ratio': bullet_ratio,
            'table_ratio': table_ratio,
            'code_fences': code_fences,
            'json_braces': json_braces,
            'url_hits': url_hits,
            'linkedin_hits': linkedin_hits,
            'email_hits': email_hits,
        },
        'complexity': complexity,
        'risk_level': risk_level,
        'recommendations': {
            'max_chunk_chars': max_chunk_chars,
            'prompt_variant': prompt_variant,
            'recommended_retries': recommended_retries,
            'repair_likelihood': repair_likelihood,
        }
    }
    return out


def analyze_file(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        return analyze_text(f.read())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Parsing Complexity Analyzer')
    parser.add_argument('input', help='Path to a text file to analyze')
    args = parser.parse_args()
    result = analyze_file(args.input)
    print(json.dumps(result, indent=2))

