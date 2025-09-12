Master Parsing Complexity Analyzer

Purpose
- Estimate parsing complexity and risk for resumes/profile texts before enrichment to choose chunking, prompt variant, and retry/repair strategy without network calls.

Scope (MVP)
- Deterministic heuristics over plain text to produce:
  - Stats: length, lines, words, unique words, avg sentence length
  - Signals: non-ASCII ratio, punctuation/digit ratios, bullet ratio, table ratio, code fence count, JSON brace count, URL/LinkedIn/email hits
  - Complexity score (0–1), risk level (low/medium/high)
  - Recommendations: max_chunk_chars, prompt_variant (concise_enriched|guarded_enriched), recommended_retries, repair_likelihood

Usage
- Python module: `scripts/parsing_complexity_analyzer.py`
- CLI: `python3 scripts/parsing_complexity_analyzer.py <textfile>` prints JSON report

Integration Points
- Pre‑processor step in enrichment pipeline to set:
  - chunk size for Together calls
  - guarded prompt when risk is medium/high
  - retry count and whether to enable JSON repair
  - optional quarantine thresholds

Testing
- `tests/test_parsing_complexity_analyzer.py` covers basic low/medium/high patterns

Future (optional)
- Add language detection and character-set profiles
- Learn thresholds from labeled telemetry (no PII)
- Surface analyzer output in Task Master complexity reports

