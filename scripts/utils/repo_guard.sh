#!/usr/bin/env bash
# Guard to ensure scripts execute from the canonical repository root.
set -euo pipefail

canonical_root="/Volumes/Extreme Pro/myprojects/headhunter"

resolve_path() {
  local target=$1
  if command -v realpath >/dev/null 2>&1; then
    realpath "$target"
  else
    python3 - <<'PY'
import os, sys
print(os.path.realpath(sys.argv[1]))
PY
  fi
}

current_root=${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd -P)}
resolved_current=$(resolve_path "${current_root}")
resolved_canonical=$(resolve_path "${canonical_root}")

if [[ "${resolved_current}" != "${resolved_canonical}" ]]; then
  cat >&2 <<MSG
[repo-guard] Detected execution from "${resolved_current}".
Scripts must run from the canonical repository at "${resolved_canonical}".
Set REPO_ROOT="${resolved_canonical}" or re-run from the correct path.
MSG
  exit 1
fi
