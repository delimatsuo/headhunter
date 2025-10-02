#!/usr/bin/env bash
set -uo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICES_DIR="$ROOT_DIR/services"
TMP_DIR="$(mktemp -d -t hh-ts-validate-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

EXPECTED_SERVICES=(
  "hh-search-svc"
  "hh-rerank-svc"
  "hh-evidence-svc"
  "hh-eco-svc"
  "hh-enrich-svc"
  "hh-admin-svc"
  "hh-msgs-svc"
)

workspace_ok=false
workspace_build_status=1
workspace_build_log=""
declare -A SERVICE_RESULTS

declare -A SERVICE_LOGS

info() {
  printf '\n[%(%Y-%m-%dT%H:%M:%S%z)T] %s\n' -1 "$1"
}

validate_workspace_config() {
  info "Validating services/workspace configuration"
  local package_json="$SERVICES_DIR/package.json"
  if [[ ! -f "$package_json" ]]; then
    echo "services/package.json not found" >&2
    return 1
  }

  mapfile -t workspace_packages < <(node -e "const data=require(process.argv[1]); const pkgs=data.workspaces?.packages||[]; console.log(pkgs.join('\\n'));" "$package_json")
  local build_script
  build_script=$(node -e "const data=require(process.argv[1]); process.stdout.write(data.scripts?.build||'');" "$package_json")
  local typecheck_script
  typecheck_script=$(node -e "const data=require(process.argv[1]); process.stdout.write(data.scripts?.typecheck||'');" "$package_json")
  local clean_script
  clean_script=$(node -e "const data=require(process.argv[1]); process.stdout.write(data.scripts?.clean||'');" "$package_json")

  local missing_packages=()
  local missing_build=()
  local missing_typecheck=()
  local missing_clean=()

  for service in "${EXPECTED_SERVICES[@]}"; do
    local package_ok=false
    for pkg in "${workspace_packages[@]}"; do
      if [[ "$pkg" == "$service" ]]; then
        package_ok=true
        break
      fi
    done
    if ! $package_ok; then
      missing_packages+=("$service")
    fi

    if [[ "$build_script" != *"$service/tsconfig.json"* ]]; then
      missing_build+=("$service")
    fi
    if [[ "$typecheck_script" != *"$service/tsconfig.json"* ]]; then
      missing_typecheck+=("$service")
    fi
    if [[ "$clean_script" != *"$service/dist"* ]]; then
      missing_clean+=("$service")
    fi
  done

  workspace_ok=true
  if (( ${#missing_packages[@]} > 0 )); then
    workspace_ok=false
    echo " - Missing in workspaces.packages: ${missing_packages[*]}"
  else
    echo " - workspaces.packages includes all services"
  fi
  if (( ${#missing_build[@]} > 0 )); then
    workspace_ok=false
    echo " - build script missing services: ${missing_build[*]}"
  else
    echo " - build script covers all services"
  fi
  if (( ${#missing_typecheck[@]} > 0 )); then
    workspace_ok=false
    echo " - typecheck script missing services: ${missing_typecheck[*]}"
  else
    echo " - typecheck script covers all services"
  fi
  if (( ${#missing_clean[@]} > 0 )); then
    workspace_ok=false
    echo " - clean script missing services: ${missing_clean[*]}"
  else
    echo " - clean script covers all services"
  fi

  if ! $workspace_ok; then
    echo "Workspace configuration requires updates before builds will succeed." >&2
  fi
}

run_workspace_build() {
  info "Running npm -ws run build"
  workspace_build_log="$TMP_DIR/workspace-build.log"
  (cd "$SERVICES_DIR" && npm -ws run build) \
    2>&1 | tee "$workspace_build_log"
  workspace_build_status=${PIPESTATUS[0]}
  if [[ $workspace_build_status -eq 0 ]]; then
    echo "Workspace build succeeded with zero TypeScript errors."
    for service in "${EXPECTED_SERVICES[@]}"; do
      SERVICE_RESULTS["$service"]="pass"
    done
  else
    echo "Workspace build failed; collecting diagnostics."
  fi
}

categorize_ts_errors() {
  local log_file="$1"
  if [[ ! -s "$log_file" ]]; then
    return
  fi

  local type_errors import_errors dependency_errors
  type_errors=$(grep -E "error TS[0-9]{4}" "$log_file" | wc -l | tr -d ' \n')
  import_errors=$(grep -i "cannot find module" "$log_file" | wc -l | tr -d ' \n')
  dependency_errors=$(grep -iE "Cannot (resolve|load)" "$log_file" | wc -l | tr -d ' \n')

  echo "TypeScript error summary:" >&2
  printf ' - Type errors (TS####): %s\n' "$type_errors" >&2
  printf ' - Import resolution issues: %s\n' "$import_errors" >&2
  printf ' - Dependency/runtime load issues: %s\n' "$dependency_errors" >&2

  if [[ "$type_errors" != "0" ]]; then
    echo "Suggested next steps: check recent changes in failing services for strict typing issues." >&2
  fi
  if [[ "$import_errors" != "0" ]]; then
    echo "Review tsconfig paths and ensure index files export expected modules." >&2
  fi
  if [[ "$dependency_errors" != "0" ]]; then
    echo "Verify package.json dependencies and workspace hoisting." >&2
  fi
}

run_individual_builds() {
  info "Attempting individual service builds"
  for service in "${EXPECTED_SERVICES[@]}"; do
    local log_file="$TMP_DIR/${service//\//_}-build.log"
    SERVICE_RESULTS["$service"]="pending"
    echo "\n--- Building $service ---"
    (
      cd "$SERVICES_DIR"
      npm -w "$service" run build
    ) 2>&1 | tee "$log_file"
    local status=${PIPESTATUS[0]}
    SERVICE_LOGS["$service"]="$log_file"
    if [[ $status -eq 0 ]]; then
      SERVICE_RESULTS["$service"]="pass"
      echo "Result: PASS"
    else
      SERVICE_RESULTS["$service"]="fail"
      echo "Result: FAIL"
    fi
  done
}

report_summary() {
  info "TypeScript build validation report"
  printf '%-20s %s\n' "Service" "Status"
  printf '%-20s %s\n' "-------" "------"
  local overall_status="pass"
  for service in "${EXPECTED_SERVICES[@]}"; do
    local status="${SERVICE_RESULTS[$service]:-not-run}"
    if [[ "$status" != "pass" ]]; then
      overall_status="fail"
    fi
    printf '%-20s %s\n' "$service" "$status"
  done
  echo
  if [[ "$overall_status" == "pass" ]]; then
    echo "✅ All TypeScript builds passed."
  else
    echo "❌ TypeScript builds still failing. See logs above for guidance." >&2
    if [[ -n "$workspace_build_log" ]]; then
      categorize_ts_errors "$workspace_build_log"
    fi
  fi
}

validate_workspace_config
run_workspace_build
if [[ $workspace_build_status -ne 0 ]]; then
  categorize_ts_errors "$workspace_build_log"
  run_individual_builds
fi
report_summary

exit "$workspace_build_status"
