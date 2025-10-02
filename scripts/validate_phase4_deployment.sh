#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

IFS=$'\n\t'

BLUE="\033[0;34m"; GREEN="\033[0;32m"; YELLOW="\033[0;33m"; RED="\033[0;31m"; NC="\033[0m"
log() { echo -e "${BLUE}[validate]${NC} $*"; }
ok()  { echo -e "${GREEN}[ok]${NC} $*"; }
warn(){ echo -e "${YELLOW}[warn]${NC} $*"; }
err() { echo -e "${RED}[error]${NC} $*" 1>&2; }

REPORT_DIR=${REPORT_DIR:-"scripts"}
MASTER_REPORT=${MASTER_REPORT:-"${REPORT_DIR}/phase4_validation_master_report.json"}

run_step() {
  local name="$1"; shift
  log "Running: $name"
  if "$@"; then ok "$name passed"; else err "$name failed"; return 1; fi
}

ensure_python() { command -v python3 >/dev/null || { err "python3 not found"; exit 1; }; }

main() {
  ensure_python
  mkdir -p "$REPORT_DIR"

  set +e
  python3 scripts/validate_pgvector_deployment.py >"${REPORT_DIR}/validate_pgvector_deployment.out.json"
  v1=$?
  python3 scripts/test_semantic_search_quality.py >"${REPORT_DIR}/semantic_quality.out.json"
  v2=$?
  python3 scripts/monitor_pgvector_performance.py &
  MONITOR_PID=$!
  sleep 2
  kill "$MONITOR_PID" >/dev/null 2>&1 || true
  python3 scripts/pgvector_performance_tuning.py >"${REPORT_DIR}/tuning_report.out.json"
  v3=$?
  set -e

  # Collate
  echo "{" >"$MASTER_REPORT"
  echo "  \"validate_pgvector\": $(cat "${REPORT_DIR}/validate_pgvector_deployment.out.json" 2>/dev/null || echo '{}')," >>"$MASTER_REPORT"
  echo "  \"semantic_quality\": $(cat "${REPORT_DIR}/semantic_quality.out.json" 2>/dev/null || echo '{}')," >>"$MASTER_REPORT"
  echo "  \"tuning\": $(cat "${REPORT_DIR}/tuning_report.out.json" 2>/dev/null || echo '{}')" >>"$MASTER_REPORT"
  echo "}" >>"$MASTER_REPORT"

  if [[ $v1 -eq 0 && $v2 -eq 0 && $v3 -eq 0 ]]; then
    ok "Phase 4 validation passed"
    exit 0
  else
    warn "Phase 4 validation completed with failures"
    exit 1
  fi
}

main "$@"

