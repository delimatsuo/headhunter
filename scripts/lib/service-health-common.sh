#!/usr/bin/env bash

# Shared helpers for service health validation scripts. These functions assume
# the caller has already ensured required dependencies (curl, python3) are
# available.

hh_health_get_access_token() {
  local issuer="$1"
  local tenant="$2"
  local subject="$3"
  local scopes="$4"

  local payload
  payload=$(python3 - "$tenant" "$subject" "$scopes" <<'PY'
import json
import sys

tenant_id, subject, scopes = sys.argv[1:]
print(json.dumps({
    "tenant_id": tenant_id,
    "sub": subject,
    "scope": scopes,
}))
PY
  )

  curl -sS -X POST \
    -H "Content-Type: application/json" \
    -d "$payload" \
    "${issuer}/token" | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))"
}

hh_health_dependency_anomalies() {
  local file="$1"
  python3 - "$file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    data = json.loads(path.read_text(encoding='utf-8'))
except Exception:  # noqa: BLE001
    sys.exit(0)

deps = data.get('dependencies') or {}
issues = []
for name, info in deps.items():
    status = ''
    if isinstance(info, dict):
        status = str(info.get('status', '')).lower()
    else:
        status = str(info).lower()
    if status not in {'ok', 'pass', 'healthy', 'ready'}:
        issues.append(f"{name}:{status or 'unknown'}")

if issues:
    print(' '.join(issues))
PY
}
