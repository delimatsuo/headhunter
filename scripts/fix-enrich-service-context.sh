#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

SERVICE_DIR="${ROOT_DIR}/services/hh-enrich-svc"
PAYLOAD_DIR="${SERVICE_DIR}/python_runtime"
SRC_SCRIPTS="${ROOT_DIR}/scripts"
SRC_WORKER="${ROOT_DIR}/cloud_run_worker"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.local.yml"

if [[ ! -d "${SERVICE_DIR}" ]]; then
  echo "hh-enrich-svc directory not found" >&2
  exit 1
fi

copy_directory() {
  local src="$1"
  local dest="$2"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='.pytest_cache' \
      --exclude='.mypy_cache' \
      --exclude='tests' \
      "${src}/" "${dest}/"
  else
    rm -rf "${dest}"
    mkdir -p "${dest}"
    tar -cf - -C "${src}" . \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='.pytest_cache' \
      --exclude='.mypy_cache' \
      --exclude='tests' | tar -xf - -C "${dest}"
  fi
}

sync_python_payload() {
  mkdir -p "${PAYLOAD_DIR}/scripts" "${PAYLOAD_DIR}/cloud_run_worker"
  echo "Syncing scripts/ into python_runtime/scripts"
  copy_directory "${SRC_SCRIPTS}" "${PAYLOAD_DIR}/scripts"
  echo "Syncing cloud_run_worker/ into python_runtime/cloud_run_worker"
  copy_directory "${SRC_WORKER}" "${PAYLOAD_DIR}/cloud_run_worker"
}

check_dockerfile_patch() {
  local dockerfile="${SERVICE_DIR}/Dockerfile"
  local expected=(
    'COPY package.json ./package.json'
    'COPY tsconfig.base.json ./tsconfig.base.json'
    'COPY common/package.json ./common/package.json'
    'COPY hh-enrich-svc/package.json ./hh-enrich-svc/package.json'
    'COPY hh-enrich-svc/python_runtime/scripts ./scripts'
    'COPY hh-enrich-svc/python_runtime/cloud_run_worker ./cloud_run_worker'
  )
  for snippet in "${expected[@]}"; do
    if ! grep -Fq "${snippet}" "${dockerfile}"; then
      echo "Dockerfile missing expected line: ${snippet}" >&2
      exit 1
    fi
  done
  echo "Dockerfile matches optimized context expectations."
}

measure_context_size() {
  echo "Current services/ context footprint:"
  du -sh "${ROOT_DIR}/services" 2>/dev/null | awk '{print "  services: "$1}'
  du -sh "${PAYLOAD_DIR}" 2>/dev/null | awk '{print "  python_runtime: "$1}'
}

compose_cmd=()
if docker compose version >/dev/null 2>&1; then
  compose_cmd=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  compose_cmd=(docker-compose)
else
  echo "Docker Compose is required but not available" >&2
  exit 1
fi

build_service() {
  local label="$1"
  echo "\n[${label}] Building hh-enrich-svc image"
  DOCKER_BUILDKIT="$2" COMPOSE_DOCKER_CLI_BUILD="$3" \
    "${compose_cmd[@]}" -f "${COMPOSE_FILE}" build hh-enrich-svc
}

validate_python_payload() {
  echo "\nValidating python payload inside container"
  DOCKER_BUILDKIT=1 "${compose_cmd[@]}" -f "${COMPOSE_FILE}" run --rm hh-enrich-svc \
    python3 -c "import importlib, json; importlib.import_module('cloud_run_worker'); print(json.dumps({'status': 'ok'}))"
}

main() {
  sync_python_payload
  check_dockerfile_patch
  measure_context_size
  build_service "BuildKit" 1 1
  build_service "Legacy" 0 0
  validate_python_payload
  echo "\nDone. Build artifacts available via docker images."
}

main "$@"
