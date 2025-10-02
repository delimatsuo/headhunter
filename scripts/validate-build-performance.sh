#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE_FILE="${ROOT_DIR}/docker-compose.local.yml"
REPORT_DIR="${ROOT_DIR}/.docker"
mkdir -p "${REPORT_DIR}"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "docker-compose.local.yml not found" >&2
  exit 1
fi

RUNTIME_REQUIREMENT="services/hh-enrich-svc/python_runtime/cloud_run_worker/requirements.txt"
if [[ ! -f "${RUNTIME_REQUIREMENT}" ]]; then
  echo "${RUNTIME_REQUIREMENT} not found." >&2
  echo "Run scripts/fix-enrich-service-context.sh first" >&2
  exit 1
fi

PYTHON_OUTPUT=""
if ! PYTHON_OUTPUT="$(python3 - <<'PY'
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML is required. Install it with 'pip install PyYAML'.\n")
    sys.exit(2)

compose = yaml.safe_load(Path("docker-compose.local.yml").read_text()) or {}

for name, svc in (compose.get("services") or {}).items():
    build = svc.get("build")
    if not build:
        continue
    if not (name.startswith("hh-") and name.endswith("-svc")):
        continue
    if isinstance(build, str):
        context = build
    else:
        context = build.get("context", ".")
    print(f"{name}|{context}")
PY
)"; then
  status=$?
  exit "${status}"
fi

mapfile -t SERVICES_RAW <<<"${PYTHON_OUTPUT//$'\r'/}"

declare -a SERVICES
declare -A SERVICE_CONTEXTS

for entry in "${SERVICES_RAW[@]}"; do
  [[ -z "${entry}" ]] && continue
  IFS='|' read -r service context <<<"${entry}"
  SERVICES+=("${service}")
  SERVICE_CONTEXTS["${service}"]="${context:-.}"
done

if [[ ${#SERVICES[@]} -eq 0 ]]; then
  echo "No hh-* services detected" >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Docker Compose not available" >&2
  exit 1
fi

resolve_context_path() {
  local ctx="$1"
  if [[ -z "${ctx}" || "${ctx}" == "." ]]; then
    printf '%s\n' "${ROOT_DIR}"
  elif [[ "${ctx}" == /* ]]; then
    printf '%s\n' "${ctx}"
  else
    ctx="${ctx#./}"
    printf '%s\n' "${ROOT_DIR}/${ctx}"
  fi
}

measure_contexts() {
  echo "\n=== Context size overview ==="
  printf '%-20s %-12s %-s\n' "Service" "Context" "Approx Size"
  for service in "${SERVICES[@]}"; do
    ctx="${SERVICE_CONTEXTS[${service}]}"
    path="$(resolve_context_path "${ctx}")"
    size="missing"
    if [[ -d "${path}" ]]; then
      size=$(du -sh "${path}" 2>/dev/null | awk '{print $1}')
    fi
    printf '%-20s %-12s %s\n' "${service}" "${ctx}" "${size}"
  done
}

run_timed_build() {
  local label="$1"
  local buildkit="$2"
  local cli_flag="$3"
  local parallel="$4"
  local logfile="${REPORT_DIR}/build-${label}.log"
  echo "\n>>> ${label}" | tee "${logfile}"
  local start_ts=$(date +%s)
  set -o pipefail
  if [[ "${parallel}" == "yes" ]]; then
    DOCKER_BUILDKIT="${buildkit}" COMPOSE_DOCKER_CLI_BUILD="${cli_flag}" \
      "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" build --parallel | tee -a "${logfile}"
  else
    DOCKER_BUILDKIT="${buildkit}" COMPOSE_DOCKER_CLI_BUILD="${cli_flag}" \
      "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" build | tee -a "${logfile}"
  fi
  local status=$?
  set +o pipefail
  local end_ts=$(date +%s)
  local elapsed=$((end_ts - start_ts))
  echo "<<< ${label} finished in ${elapsed}s (status ${status})" | tee -a "${logfile}"
  printf '%s|%s|%s\n' "${label}" "${elapsed}" "${status}"
}

run_timed_service_builds() {
  local label="$1"
  local buildkit="$2"
  local cli_flag="$3"
  echo "\n>>> ${label}" | tee -a "${REPORT_DIR}/service-builds.log"
  for service in "${SERVICES[@]}"; do
    local start_ts=$(date +%s)
    if DOCKER_BUILDKIT="${buildkit}" COMPOSE_DOCKER_CLI_BUILD="${cli_flag}" \
      "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" build "${service}" >/dev/null; then
      local elapsed=$(( $(date +%s) - start_ts ))
      printf '   %-20s %ss\n' "${service}" "${elapsed}" | tee -a "${REPORT_DIR}/service-builds.log"
    else
      printf '   %-20s failed\n' "${service}" | tee -a "${REPORT_DIR}/service-builds.log"
    fi
  done
}

measure_contexts

declare -a LOG_RESULTS
LOG_RESULTS+=("$(run_timed_build 'buildkit-full' 1 1 no)")
LOG_RESULTS+=("$(run_timed_build 'legacy-full' 0 0 no)")
LOG_RESULTS+=("$(run_timed_build 'buildkit-parallel' 1 1 yes)")

run_timed_service_builds 'Per-service BuildKit cache warm' 1 1
run_timed_service_builds 'Per-service Legacy cache warm' 0 0

cat <<'REPORT'

=== Build timing summary ===
REPORT
printf '%-25s %-10s %-s\n' "Run" "Seconds" "Status"
for entry in "${LOG_RESULTS[@]}"; do
  IFS='|' read -r name seconds status <<<"${entry}"
  printf '%-25s %-10s %s\n' "${name}" "${seconds}" "${status}"

done

cat <<'RECOMMEND'

=== Recommendations ===
- Prefer BuildKit builds; compare buildkit-full vs legacy-full results after context tuning.
- Use --parallel on multi-core hosts to accelerate rebuilds; fall back to sequential when encountering resource contention.
- Warm caches with per-service builds while iterating locally to avoid full rebuilds.
- If timings regress, prune stale layers (`docker builder prune`) and rerun buildkit-full for a clean baseline.
- Pair this script with scripts/test-docker-builds.sh to ensure both performance and functional correctness stay aligned.
RECOMMEND
