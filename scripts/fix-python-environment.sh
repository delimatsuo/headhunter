#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Diagnoses and remediates common Python environment issues for running the
# local pytest suite. Ensures work happens inside a dedicated virtualenv.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIRS=("pm_check_venv")
VENV_PATH="${ROOT_DIR}/.hh_venv"
REQUIREMENTS_FILE="${ROOT_DIR}/cloud_run_worker/requirements.txt"
PYTHON_BIN="${PYTHON_BIN:-python3}"

log() {
  printf '[python-fix] %s\n' "$*"
}

warn() {
  printf '[python-fix][warn] %s\n' "$*" >&2
}

error() {
  printf '[python-fix][error] %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    error "Missing required command: $1"
  fi
}

require_cmd "$PYTHON_BIN"

log "Using Python interpreter: $(command -v "$PYTHON_BIN")"
"$PYTHON_BIN" --version

if [[ "${SKIP_VENV_REMOVAL:-false}" != "true" ]]; then
  for dir in "${VENV_DIRS[@]}"; do
    path="${ROOT_DIR}/${dir}"
    if [[ -d "${path}" ]]; then
      log "Removing stale virtual environment '${dir}'"
      rm -rf "${path}"
    fi
  done
fi

if [[ ! -d "${VENV_PATH}" ]]; then
  log "Creating virtual environment at ${VENV_PATH}"
  "$PYTHON_BIN" -m venv "${VENV_PATH}"
fi

# shellcheck disable=SC1090
source "${VENV_PATH}/bin/activate"

VENV_PYTHON="${VENV_PATH}/bin/python"
log "Activated virtual environment using ${VENV_PYTHON}"
"${VENV_PYTHON}" --version

log "Upgrading pip tooling inside virtual environment"
"${VENV_PYTHON}" -m pip install --upgrade pip setuptools wheel >/dev/null

if [[ -f "${REQUIREMENTS_FILE}" ]]; then
  log "Ensuring dependencies from ${REQUIREMENTS_FILE}"
  "${VENV_PYTHON}" -m pip install -r "${REQUIREMENTS_FILE}" >/dev/null
else
  warn "Requirements file not found at ${REQUIREMENTS_FILE}"
fi

if ! "${VENV_PYTHON}" -m pytest --version >/dev/null 2>&1; then
  log "Installing pytest"
  "${VENV_PYTHON}" -m pip install pytest >/dev/null
fi

log "Validating pytest import"
"${VENV_PYTHON}" - <<'PY'
import importlib
import sys

for module in ("pytest", "scripts.run_integration"):
    try:
        importlib.import_module(module)
    except Exception as exc:  # noqa: BLE001
        print(f"import-error:{module}:{exc}")
        sys.exit(1)
print("imports-ok")
PY

log "Collecting tests to verify PYTHONPATH"
PYTHONPATH="${ROOT_DIR}" "${VENV_PYTHON}" -m pytest --collect-only >/dev/null

cat <<'NEXT'
Python environment checks complete. Virtual environment notes:
  • Environment location: .hh_venv
  • To deactivate in the current shell: deactivate
  • To reactivate later: source .hh_venv/bin/activate
  • Run full test suite: PYTHONPATH=. python -m pytest tests -q
NEXT
