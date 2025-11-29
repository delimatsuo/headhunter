#!/usr/bin/env python3
"""
Directly query database dimension using gcloud sql execute-sql
"""

import subprocess
import json

sql_query = """
SELECT
    attname as column_name,
    atttypmod,
    atttypmod - 4 as dimension,
    format_type(atttypid, atttypmod) as full_type
FROM pg_attribute
WHERE attrelid = 'search.candidate_embeddings'::regclass
  AND attname = 'embedding';
"""

print("Checking database dimension configuration...")
print("=" * 80)

result = subprocess.run([
    "gcloud", "sql", "query",
    "sql-hh-core",
    "--project=headhunter-ai-0088",
    "--database=headhunter",
    "--quiet",
    f"--sql={sql_query}"
], capture_output=True, text=True)

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print("\nReturn code:", result.returncode)
