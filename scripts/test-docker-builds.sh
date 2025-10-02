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
CONTEXT_PROBE_DIR="${REPORT_DIR}/context-probes"
mkdir -p "${REPORT_DIR}" "${CONTEXT_PROBE_DIR}"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "docker-compose.local.yml not found at ${COMPOSE_FILE}" >&2
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
except ImportError as exc:
    sys.stderr.write("PyYAML is required. Install it with 'pip install PyYAML' before running this script.\n")
    sys.exit(2)

compose_path = Path("docker-compose.local.yml")
data = yaml.safe_load(compose_path.read_text()) or {}
services = []

for name, svc in (data.get("services") or {}).items():
    build = svc.get("build")
    if not build:
        continue
    if isinstance(build, str):
        context = build
        dockerfile = "Dockerfile"
    else:
        context = build.get("context", ".")
        dockerfile = build.get("dockerfile") or "Dockerfile"
    if name.startswith("hh-") and name.endswith("-svc"):
        services.append((name, context, dockerfile))

for entry in services:
    name, context, dockerfile = entry
    print(f"{name}|{context}|{dockerfile}")
PY
)"; then
  status=$?
  exit "${status}"
fi

mapfile -t SERVICES_RAW <<<"${PYTHON_OUTPUT//$'\r'/}"

declare -a SERVICES
declare -A SERVICE_CONTEXTS
declare -A SERVICE_DOCKERFILES

for entry in "${SERVICES_RAW[@]}"; do
  [[ -z "${entry}" ]] && continue
  IFS='|' read -r service context dockerfile <<<"${entry}"
  SERVICES+=("${service}")
  SERVICE_CONTEXTS["${service}"]="${context:-.}"
  SERVICE_DOCKERFILES["${service}"]="${dockerfile:-Dockerfile}"
done

if [[ ${#SERVICES[@]} -eq 0 ]]; then
  echo "No hh-* services with build definitions found in docker-compose.local.yml" >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Docker Compose is required but was not found." >&2
  exit 1
fi

project_name="$(basename "${ROOT_DIR}")"
project_name="${project_name//[^a-zA-Z0-9]/}"
project_name="${project_name,,}"

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

resolve_dockerfile_path() {
  local service="$1"
  local ctx="${SERVICE_CONTEXTS[${service}]}"
  local dockerfile="${SERVICE_DOCKERFILES[${service}]}"
  local base
  base="$(resolve_context_path "${ctx}")"
  if [[ -z "${dockerfile}" || "${dockerfile}" == "." ]]; then
    dockerfile="Dockerfile"
  fi
  if [[ "${dockerfile}" == /* ]]; then
    printf '%s\n' "${dockerfile}"
  else
    dockerfile="${dockerfile#./}"
    printf '%s/%s\n' "${base%/}" "${dockerfile}"
  fi
}

probe_context_transfer() {
  local service="$1"
  local context_path="$2"
  local dockerfile_path="$3"
  local log status transfer method
  local -a cmd
  local log_file="${CONTEXT_PROBE_DIR}/${service}.log"

  if ! command -v docker >/dev/null 2>&1; then
    return 1
  fi

  if docker buildx version >/dev/null 2>&1; then
    cmd=(docker buildx build --builder default --progress=plain -f "${dockerfile_path}" "${context_path}" --target __context_probe --load)
    method="buildx"
  else
    cmd=(docker build --progress=plain -f "${dockerfile_path}" "${context_path}" --target __context_probe)
    method="build"
  fi

  set +e
  log=$(DOCKER_BUILDKIT=1 "${cmd[@]}" 2>&1)
  status=$?
  set -e

  transfer=$(printf '%s\n' "${log}" | sed -n 's/.*transferring context: *//p' | tail -n1)
  if [[ -z "${transfer}" ]]; then
    transfer=$(printf '%s\n' "${log}" | sed -n 's/.*Sending build context to Docker daemon *//p' | tail -n1)
  fi
  transfer="${transfer//$'\r'/}"

  if [[ -n "${transfer}" ]]; then
    printf '%s (%s)\n' "${transfer}" "${method}"
    return 0
  fi

  printf '%s\n' "${log}" > "${log_file}"

  return 1
}

measure_context_size() {
  local service="$1"
  local ctx="${SERVICE_CONTEXTS[${service}]}"
  local path="$(resolve_context_path "${ctx}")"
  if [[ ! -d "${path}" ]]; then
    printf '%s|%s|%s\n' "${service}" "${ctx}" "missing"
    return
  fi

  local dockerfile_path="$(resolve_dockerfile_path "${service}")"
  local transfer
  if transfer="$(probe_context_transfer "${service}" "${path}" "${dockerfile_path}")"; then
    printf '%s|%s|%s\n' "${service}" "${ctx}" "${transfer}"
    return
  fi

  local fallback
  fallback=$(du -sh "${path}" 2>/dev/null | awk '{print $1}')
  if [[ -n "${fallback}" ]]; then
    printf '%s|%s|%s (%s)\n' "${service}" "${ctx}" "${fallback}" "du"
  else
    printf '%s|%s|%s\n' "${service}" "${ctx}" "unknown"
  fi
}

find_image_candidate() {
  local service="$1"
  local candidates=(
    "${project_name}_${service}"
    "${project_name}-${service}"
    "${service}"
  )
  for candidate in "${candidates[@]}"; do
    if docker image inspect "${candidate}" >/dev/null 2>&1; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

inspect_image_size() {
  local ref="$1"
  if [[ -z "${ref}" ]]; then
    printf 'n/a'
    return
  fi
  local bytes
  bytes=$(docker image inspect "${ref}" --format '{{ .Size }}' 2>/dev/null || true)
  if [[ -z "${bytes}" ]]; then
    printf 'unknown'
    return
  fi
  awk -v b="${bytes}" 'BEGIN { printf "%.2f MB", b/1048576 }'
}

run_compose_build() {
  local mode="$1"
  local buildkit_var="$2"
  local cli_var="$3"
  local logfile="${REPORT_DIR}/build-${mode}.log"
  echo "\n=== ${mode^^} build (DOCKER_BUILDKIT=${buildkit_var}, COMPOSE_DOCKER_CLI_BUILD=${cli_var}) ==="
  local start_ts end_ts
  start_ts=$(date +%s)
  set -o pipefail
  DOCKER_BUILDKIT="${buildkit_var}" COMPOSE_DOCKER_CLI_BUILD="${cli_var}" \
    "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" build | tee "${logfile}"
  local status=$?
  set +o pipefail
  end_ts=$(date +%s)
  printf 'Completed %s build in %s seconds (status %s). Log: %s\n' "${mode}" "$((end_ts - start_ts))" "${status}" "${logfile}"
}

run_service_builds() {
  local mode="$1"
  local buildkit_var="$2"
  local cli_var="$3"
  echo "\n=== Per-service build validation (${mode}) ==="
  for service in "${SERVICES[@]}"; do
    echo "-- ${service}"
    local start_ts=$(date +%s)
    if DOCKER_BUILDKIT="${buildkit_var}" COMPOSE_DOCKER_CLI_BUILD="${cli_var}" \
      "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" build "${service}"; then
      local end_ts=$(date +%s)
      printf '   build time: %ss\n' "$((end_ts - start_ts))"
    else
      echo "   build failed" >&2
    fi
  done
}

print_context_report() {
  echo "\n=== Docker build context transfer sizes ==="
  printf '%-20s %-15s %s\n' "Service" "Context" "Measured Size"
  for service in "${SERVICES[@]}"; do
    IFS='|' read -r svc ctx size <<<"$(measure_context_size "${service}")"
    printf '%-20s %-15s %s\n' "${svc}" "${ctx}" "${size}"
  done
}

print_image_report() {
  echo "\n=== Built image summary ==="
  printf '%-20s %-30s %s\n' "Service" "Image" "Size"
  for service in "${SERVICES[@]}"; do
    if image_ref=$(find_image_candidate "${service}" 2>/dev/null); then
      size=$(inspect_image_size "${image_ref}")
      printf '%-20s %-30s %s\n' "${service}" "${image_ref}" "${size}"
    else
      printf '%-20s %-30s %s\n' "${service}" "n/a" "missing"
    fi
  done
}

print_troubleshooting_notes() {
  cat <<'EON'

=== Troubleshooting tips ===
- If builds hang on "loading build context", verify the dockerignore patterns exclude large directories (scripts/optimize-build-context.sh can help).
- When BuildKit fails but the legacy builder succeeds, clear caches with `docker builder prune` and retry.
- For repeated failures on a single service, rebuild with `--no-cache` (`docker compose build --no-cache <service>`).
- Ensure Firebase and Together AI emulators are stopped; they can consume resources impacting large builds.
- Check per-service logs in .docker/build-*.log for detailed failure traces.
EON
}

print_context_report
run_compose_build "buildkit" 1 1
run_compose_build "legacy" 0 0
run_service_builds "BuildKit" 1 1
run_service_builds "Legacy" 0 0
print_image_report
print_troubleshooting_notes
