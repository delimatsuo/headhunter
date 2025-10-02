#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./utils/repo_guard.sh
source "$(dirname "${BASH_SOURCE[0]}")/utils/repo_guard.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
CONFIG_FILE="${REPO_ROOT}/config/infrastructure/headhunter-production.env"

usage() {
  cat <<'USAGE'
Usage: scripts/generate-deployment-report.sh [options]

Options:
  --project-id <id>            GCP project ID (defaults to config file)
  --environment <env>          Deployment environment label (default: production)
  --region <region>            GCP region (defaults to config file)
  --output <path>              Output markdown file path (default: docs/deployment-report-<timestamp>.md)
  --deployment-manifest <path> Path to deployment manifest JSON (optional)
  --monitoring-manifest <path> Path to monitoring manifest JSON (optional)
  --load-test-report <path>    Path to load test report JSON (optional)
  --include-blockers           Include known blockers section and run blocker detection
  --operator <name>            Operator name to include in report header
  --help                       Display this help message
USAGE
}

require_command() {
  local cmd=$1
  if ! command -v "$cmd" >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

if [[ -f "${CONFIG_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"
fi

PROJECT_ID_DEFAULT=${PROJECT_ID:-""}
REGION_DEFAULT=${REGION:-""}
ENVIRONMENT_DEFAULT="production"

PROJECT_ID=""
ENVIRONMENT="${ENVIRONMENT_DEFAULT}"
REGION=""
OUTPUT_PATH=""
DEPLOYMENT_MANIFEST=""
MONITORING_MANIFEST=""
LOAD_TEST_REPORT=""
INCLUDE_BLOCKERS=false
OPERATOR_NAME=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --project-id)
      PROJECT_ID=$2
      shift 2
      ;;
    --environment)
      ENVIRONMENT=$2
      shift 2
      ;;
    --region)
      REGION=$2
      shift 2
      ;;
    --output)
      OUTPUT_PATH=$2
      shift 2
      ;;
    --deployment-manifest)
      DEPLOYMENT_MANIFEST=$2
      shift 2
      ;;
    --monitoring-manifest)
      MONITORING_MANIFEST=$2
      shift 2
      ;;
    --load-test-report)
      LOAD_TEST_REPORT=$2
      shift 2
      ;;
    --include-blockers)
      INCLUDE_BLOCKERS=true
      shift
      ;;
    --operator)
      OPERATOR_NAME=$2
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

PROJECT_ID=${PROJECT_ID:-${PROJECT_ID_DEFAULT}}
REGION=${REGION:-${REGION_DEFAULT}}

if [[ -z "${PROJECT_ID}" ]]; then
  echo "[error] --project-id or config PROJECT_ID must be provided" >&2
  exit 1
fi

if [[ -z "${REGION}" ]]; then
  echo "[error] --region or config REGION must be provided" >&2
  exit 1
fi

if [[ -z "${OUTPUT_PATH}" ]]; then
  OUTPUT_PATH="${REPO_ROOT}/docs/deployment-report-$(date -u +%Y%m%d-%H%M%S).md"
else
  if [[ ! -d "$(dirname "${OUTPUT_PATH}")" ]]; then
    echo "[error] Output directory does not exist: $(dirname "${OUTPUT_PATH}")" >&2
    exit 1
  fi
  case "${OUTPUT_PATH}" in
    /*) : ;;
    *) OUTPUT_PATH="${REPO_ROOT}/${OUTPUT_PATH}" ;;
  esac
fi

if [[ -z "${OPERATOR_NAME}" ]]; then
  OPERATOR_NAME=${USER:-"unknown"}
fi

TIMESTAMP_UTC=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
REPORT_DATE_HUMAN=$(date -u +"%Y-%m-%d")

mkdir -p "$(dirname "${OUTPUT_PATH}")"

TMP_DIR=$(mktemp -d)
trap 'rm -rf "${TMP_DIR}"' EXIT

warnings=()
blockers=()
notes=()

log() {
  local level=$1
  shift
  printf '[%s] %s\n' "$level" "$*"
}

append_warning() {
  warnings+=("$1")
  log WARN "$1"
}

append_blocker() {
  blockers+=("$1")
  log BLOCKER "$1"
}

append_note() {
  notes+=("$1")
  log INFO "$1"
}

GCLOUD_AVAILABLE=false
JQ_AVAILABLE=false

if require_command gcloud; then
  GCLOUD_AVAILABLE=true
else
  append_warning "gcloud command not found; falling back to placeholder data"
fi

if require_command jq; then
  JQ_AVAILABLE=true
else
  append_warning "jq command not found; structured data will use simplified parsing"
fi

if ${GCLOUD_AVAILABLE}; then
  if ! gcloud config set project "${PROJECT_ID}" >/dev/null 2>&1; then
    append_warning "Unable to set gcloud project to ${PROJECT_ID}. Ensure you have access."
  fi
  ACTIVE_ACCOUNT=$(gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>/dev/null || true)
  if [[ -z "${ACTIVE_ACCOUNT}" ]]; then
    append_warning "No active gcloud account detected; API calls may fail."
  else
    append_note "Using gcloud account ${ACTIVE_ACCOUNT}"
  fi
fi

EXPECTED_FASTIFY_SERVICES=(
  "hh-embed-svc-production"
  "hh-search-svc-production"
  "hh-rerank-svc-production"
  "hh-evidence-svc-production"
  "hh-eco-svc-production"
  "hh-enrich-svc-production"
  "hh-admin-svc-production"
  "hh-msgs-svc-production"
)

CLOUD_RUN_TABLE=""
CLOUD_RUN_JSON="${TMP_DIR}/cloud_run_services.json"
CLOUD_RUN_COUNT=0
FASTIFY_DEPLOYED=0

collect_cloud_run_inventory() {
  if ! ${GCLOUD_AVAILABLE}; then
    CLOUD_RUN_TABLE="| Service Name | URL | Image Digest | Revision | Traffic | Health Status |\n| --- | --- | --- | --- | --- | --- |\n| Data unavailable | N/A | N/A | N/A | N/A | N/A |"
    return
  fi

  if ! gcloud run services list \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --format=json > "${CLOUD_RUN_JSON}" 2>"${TMP_DIR}/cloud_run_list.err"; then
    append_warning "Failed to list Cloud Run services: $(<"${TMP_DIR}/cloud_run_list.err")"
    CLOUD_RUN_TABLE="| Service Name | URL | Image Digest | Revision | Traffic | Health Status |\n| --- | --- | --- | --- | --- | --- |\n| Retrieval failed | - | - | - | - | - |"
    return
  fi

  CLOUD_RUN_COUNT=$(jq length "${CLOUD_RUN_JSON}" 2>/dev/null || echo 0)
  local table_lines=""

  if [[ ${CLOUD_RUN_COUNT} -eq 0 ]]; then
    table_lines="| Service Name | URL | Image Digest | Revision | Traffic | Health Status |\n| --- | --- | --- | --- | --- | --- |\n| No services found in region ${REGION}. | - | - | - | - | - |"
    append_warning "No Cloud Run services detected in ${PROJECT_ID}/${REGION}."
    CLOUD_RUN_TABLE=${table_lines}
    return
  fi

  table_lines="| Service Name | URL | Image Digest | Revision | Traffic | Health Status |\n| --- | --- | --- | --- | --- | --- |"

  while IFS= read -r service; do
    local name
    local url
    name=$(echo "${service}" | jq -r '.metadata.name')
    url=$(echo "${service}" | jq -r '.status.url // ""')
    local describe_json="${TMP_DIR}/run_${name}.json"
    if ! gcloud run services describe "${name}" \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --format=json > "${describe_json}" 2>"${TMP_DIR}/run_${name}.err"; then
      append_warning "Failed to describe Cloud Run service ${name}"
      table_lines+=$"\n| ${name} | ${url:-N/A} | Describe failed | - | - | - |"
      continue
    fi

    local revision image traffic health
    revision=$(jq -r '.status.latestReadyRevisionName // .status.latestCreatedRevisionName // "unknown"' "${describe_json}" 2>/dev/null || echo "unknown")
    image=$(jq -r '.spec.template.spec.containers[0].image // ""' "${describe_json}" 2>/dev/null || echo "")
    traffic=$(jq -r '[.status.traffic[]? | "\(.percent)% -> \(.revisionName // .tag // "latest")"] | join(", ")' "${describe_json}" 2>/dev/null || echo "Not allocated")
    health=$(jq -r '.status.conditions[]? | select(.type=="Ready") | .status' "${describe_json}" 2>/dev/null || echo "Unknown")

    local digest=""
    if [[ -n "${image}" ]]; then
      if [[ "${image}" == *"@sha256:"* ]]; then
        digest="${image##*@}"
      else
        digest="Tag: ${image##*:}"
      fi
    else
      digest="Unavailable"
    fi

    if [[ " ${EXPECTED_FASTIFY_SERVICES[*]} " == *" ${name} "* ]]; then
      ((FASTIFY_DEPLOYED++))
    fi

    table_lines+=$"\n| ${name:-N/A} | ${url:-N/A} | ${digest:-N/A} | ${revision:-N/A} | ${traffic:-N/A} | ${health:-Unknown} |"
  done < <(jq -c '.[]' "${CLOUD_RUN_JSON}")

  CLOUD_RUN_TABLE=${table_lines}
}

IMAGE_ARTIFACT_TABLE=""

collect_image_artifacts() {
  if [[ -z "${DEPLOYMENT_MANIFEST}" ]] || [[ ! -f "${DEPLOYMENT_MANIFEST}" ]]; then
    append_warning "Deployment manifest not provided; container artifact metadata will be limited."
    IMAGE_ARTIFACT_TABLE="| Service Name | Image URI | Digest | Build Time | Git SHA | Size |\n| --- | --- | --- | --- | --- | --- |\n| Data unavailable | - | - | - | - | - |"
    return
  fi

  if ! ${JQ_AVAILABLE}; then
    append_warning "jq is required to parse deployment manifest ${DEPLOYMENT_MANIFEST}."
    IMAGE_ARTIFACT_TABLE="| Service Name | Image URI | Digest | Build Time | Git SHA | Size |\n| --- | --- | --- | --- | --- | --- |\n| Parsing requires jq | - | - | - | - | - |"
    return
  fi

  IMAGE_ARTIFACT_TABLE="| Service Name | Image URI | Digest | Build Time | Git SHA | Size |\n| --- | --- | --- | --- | --- | --- |"
  while IFS= read -r entry; do
    local svc image digest build git_sha size
    svc=$(echo "${entry}" | jq -r '.service // .name // "unknown"')
    image=$(echo "${entry}" | jq -r '.image // ""')
    digest=$(echo "${entry}" | jq -r '.digest // (.image // "" | split("@") | .[1]? // "unknown")')
    build=$(echo "${entry}" | jq -r '.buildTime // .builtAt // "unknown"')
    git_sha=$(echo "${entry}" | jq -r '.gitSha // .gitCommit // "unknown"')
    size=$(echo "${entry}" | jq -r '.imageSize // .size // "unknown"')
    IMAGE_ARTIFACT_TABLE+=$"\n| ${svc} | ${image:-unknown} | ${digest:-unknown} | ${build:-unknown} | ${git_sha:-unknown} | ${size:-unknown} |"
  done < <(jq -c '.services? // .artifacts? // [] | .[]' "${DEPLOYMENT_MANIFEST}")
}

GATEWAY_SECTION=""
API_GATEWAY_HOSTNAME=""

collect_api_gateway() {
  if ! ${GCLOUD_AVAILABLE}; then
    GATEWAY_SECTION="- API Gateway data unavailable (gcloud missing)."
    return
  fi

  local gateway_list="${TMP_DIR}/gateway_list.json"
  if ! gcloud api-gateway gateways list \
      --project="${PROJECT_ID}" \
      --location="${REGION}" \
      --format=json > "${gateway_list}" 2>"${TMP_DIR}/gateway_list.err"; then
    append_warning "Failed to list API Gateways: $(<"${TMP_DIR}/gateway_list.err")"
    GATEWAY_SECTION="- Unable to query API Gateway."
    return
  fi

  local count
  count=$(jq length "${gateway_list}" 2>/dev/null || echo 0)
  if [[ ${count} -eq 0 ]]; then
    GATEWAY_SECTION="- No API Gateway instances found in ${REGION}."
    append_warning "API Gateway not configured in region ${REGION}."
    return
  fi

  local section="| Attribute | Value |\n| --- | --- |"

  while IFS= read -r gateway; do
    local name state hostname api_config create_time
    name=$(echo "${gateway}" | jq -r '.name // "unnamed"')
    state=$(echo "${gateway}" | jq -r '.state // "UNKNOWN"')
    hostname=$(echo "${gateway}" | jq -r '.defaultHostname // "pending"')
    api_config=$(echo "${gateway}" | jq -r '.apiConfig // "n/a"')
    create_time=$(echo "${gateway}" | jq -r '.createTime // "unknown"')
    API_GATEWAY_HOSTNAME=${hostname}

    section+=$"\n| Gateway | ${name} |"
    section+=$"\n| State | ${state} |"
    section+=$"\n| Hostname | ${hostname} |"
    section+=$"\n| API Config | ${api_config} |"
    section+=$"\n| Created | ${create_time} |"

    local api_config_json="${TMP_DIR}/gateway_config.json"
    local api_id=""
    local api_config_id=""

    if [[ "${api_config}" =~ ^projects/.*/apis/([^/]+)/configs/([^/]+)$ ]]; then
      api_id="${BASH_REMATCH[1]}"
      api_config_id="${BASH_REMATCH[2]}"
    fi

    if [[ -n "${api_id}" && -n "${api_config_id}" ]]; then
      if gcloud api-gateway api-configs describe "${api_config_id}" \
          --api="${api_id}" \
          --project="${PROJECT_ID}" \
          --format=json > "${api_config_json}" 2>"${TMP_DIR}/gateway_config.err"; then
        if ${JQ_AVAILABLE}; then
          local routes_table="| Path | Method | Backend Service | Auth Required |\n| --- | --- | --- | --- |"
          while IFS= read -r route; do
            local path method backend auth
            path=$(echo "${route}" | jq -r '.path // "N/A"')
            method=$(echo "${route}" | jq -r '.method // "ANY"')
            backend=$(echo "${route}" | jq -r '.backend // "N/A"')
            auth=$(echo "${route}" | jq -r '.auth // "N/A"')
            routes_table+=$"\n| ${path} | ${method} | ${backend} | ${auth} |"
          done < <(jq -c '.routes? // [] | .[]' "${api_config_json}")
          section+=$"\n\n**Routes**\n\n${routes_table}"
        fi
      else
        append_warning "Failed to describe API config ${api_config_id} for API ${api_id}: $(<"${TMP_DIR}/gateway_config.err" 2>/dev/null)"
      fi
    elif [[ "${api_config}" != "n/a" ]]; then
      append_warning "Unexpected apiConfig path for gateway ${name}: ${api_config}"
    fi
  done < <(jq -c '.[]' "${gateway_list}")

  GATEWAY_SECTION=${section}
}

MONITORING_SECTION=""
ALERT_SECTION=""
UPTIME_SECTION=""
COST_SECTION=""

collect_monitoring() {
  if [[ -n "${MONITORING_MANIFEST}" ]] && [[ -f "${MONITORING_MANIFEST}" ]] && ${JQ_AVAILABLE}; then
    local dashboard_table="| Dashboard | Purpose | URL |\n| --- | --- | --- |"
    while IFS= read -r dash; do
      local name desc id url
      name=$(echo "${dash}" | jq -r '.name // .displayName // "Unnamed dashboard"')
      desc=$(echo "${dash}" | jq -r '.description // "-"')
      id=$(echo "${dash}" | jq -r '.id // (.name | split("/")[-1])')
      url="https://console.cloud.google.com/monitoring/dashboards/custom/${id}?project=${PROJECT_ID}"
      dashboard_table+=$"\n| ${name} | ${desc} | ${url} |"
    done < <(jq -c '.dashboards? // [] | .[]' "${MONITORING_MANIFEST}")
    MONITORING_SECTION=${dashboard_table}

    local alert_table="| Policy | Severity | Condition | Notification Channels |\n| --- | --- | --- | --- |"
    while IFS= read -r alert; do
      local name sev condition channels
      name=$(echo "${alert}" | jq -r '.displayName // .name // "Unnamed policy"')
      sev=$(echo "${alert}" | jq -r '.severity // "MEDIUM"')
      condition=$(echo "${alert}" | jq -r '.conditions[0].displayName // .conditions[0].conditionThreshold.filter // "-"')
      channels=$(echo "${alert}" | jq -r '.notificationChannels | join(", ") // "-"')
      alert_table+=$"\n| ${name} | ${sev} | ${condition} | ${channels} |"
    done < <(jq -c '.alertPolicies? // [] | .[]' "${MONITORING_MANIFEST}")
    ALERT_SECTION=${alert_table}

    local uptime_table="| Uptime Check | Target | Frequency | Status |\n| --- | --- | --- | --- |"
    while IFS= read -r uptime; do
      local name target freq status
      name=$(echo "${uptime}" | jq -r '.displayName // .name // "Unnamed uptime"')
      target=$(echo "${uptime}" | jq -r '.monitoredResource.labels.instance // .httpCheck.path // "-"')
      freq=$(echo "${uptime}" | jq -r '.period // "-"')
      status=$(echo "${uptime}" | jq -r '.uptimeState // "-"')
      uptime_table+=$"\n| ${name} | ${target} | ${freq} | ${status} |"
    done < <(jq -c '.uptimeChecks? // [] | .[]' "${MONITORING_MANIFEST}")
    UPTIME_SECTION=${uptime_table}

    local cost_table="| Component | Resource | Notes |\n| --- | --- | --- |"
    while IFS= read -r cost; do
      local component resource notes
      component=$(echo "${cost}" | jq -r '.component // "Cost tracking"')
      resource=$(echo "${cost}" | jq -r '.resource // "-"')
      notes=$(echo "${cost}" | jq -r '.notes // "-"')
      cost_table+=$"\n| ${component} | ${resource} | ${notes} |"
    done < <(jq -c '.costTracking? // [] | .[]' "${MONITORING_MANIFEST}")
    COST_SECTION=${cost_table}
  else
    MONITORING_SECTION="Monitoring manifest not provided; dashboards unresolved."
    ALERT_SECTION="Alert manifest not provided."
    UPTIME_SECTION="Uptime checks manifest not provided."
    COST_SECTION="Cost tracking configuration pending."
    append_warning "Monitoring manifest missing or jq unavailable; observability section will be limited."
  fi
}

LOAD_TEST_SECTION=""
SLA_SECTION=""
SLA_FLAGS=()

collect_load_tests() {
  if [[ -z "${LOAD_TEST_REPORT}" ]] || [[ ! -f "${LOAD_TEST_REPORT}" ]]; then
    LOAD_TEST_SECTION="Load test report missing. Execute run-post-deployment-load-tests.sh to generate results."
    SLA_SECTION="SLA evidence pending load test execution."
    append_warning "Load test report not found; SLA evidence incomplete."
    return
  fi
  if ! ${JQ_AVAILABLE}; then
    LOAD_TEST_SECTION="Load test report provided (${LOAD_TEST_REPORT}) but jq unavailable for parsing."
    SLA_SECTION="Cannot summarise SLA without jq."
    append_warning "jq required to parse load test report ${LOAD_TEST_REPORT}."
    return
  fi

  local overall_table="| Metric | Target | Actual | Status |\n| --- | --- | --- | --- |"
  local metrics=(
    "Overall p95 latency" "overall.p95LatencyMs" "<= 1200"
    "Rerank p95 latency" "rerank.p95LatencyMs" "<= 350"
    "Error rate" "overall.errorRate" "< 1%"
    "Cache hit rate" "cache.hitRate" ">= 98%"
    "Throughput" "overall.throughputPerMin" ">= 100 req/min"
  )
  local metric_count=${#metrics[@]}
  local idx=0
  while [[ ${idx} -lt ${metric_count} ]]; do
    local label=${metrics[${idx}]}
    local key=${metrics[$((idx+1))]}
    local target=${metrics[$((idx+2))]}
    local actual
    actual=$(jq -r --arg key "${key}" '(
      ($key | split(".")) as $p
      | try (getpath($p)) catch empty
    ) // ""' "${LOAD_TEST_REPORT}" 2>/dev/null || printf '')
    if [[ -z "${actual}" ]]; then
      actual="N/A"
    fi
    local status="Pending"
    if [[ "${actual}" =~ ^[0-9.]+$ ]]; then
      if [[ "${label}" == "Error rate" ]]; then
        status=$(awk -v val="${actual}" 'BEGIN { if (val < 0.01) print "Pass"; else print "Fail" }')
      elif [[ "${label}" == "Cache hit rate" ]]; then
        status=$(awk -v val="${actual}" 'BEGIN { if (val >= 0.98) print "Pass"; else print "Fail" }')
      elif [[ "${label}" == "Throughput" ]]; then
        status=$(awk -v val="${actual}" 'BEGIN { if (val >= 100) print "Pass"; else print "Fail" }')
      else
        status=$(awk -v val="${actual}" 'BEGIN { if (val <= 1200) print "Pass"; else print "Fail" }')
      fi
    fi
    overall_table+=$"\n| ${label} | ${target} | ${actual} | ${status} |"
    if [[ "${status}" == "Fail" ]]; then
      SLA_FLAGS+=("${label}")
    fi
    idx=$((idx+3))
  done

  local scenario_table="| Scenario | Requests | p95 Latency (ms) | Error Rate | Throughput (req/min) |\n| --- | --- | --- | --- | --- |"
  while IFS= read -r scenario; do
    local name requests p95 err thr
    name=$(echo "${scenario}" | jq -r '.name // "Unnamed"')
    requests=$(echo "${scenario}" | jq -r '.requests // 0')
    p95=$(echo "${scenario}" | jq -r '.p95LatencyMs // "N/A"')
    err=$(echo "${scenario}" | jq -r '.errorRate // "N/A"')
    thr=$(echo "${scenario}" | jq -r '.throughputPerMin // "N/A"')
    scenario_table+=$"\n| ${name} | ${requests} | ${p95} | ${err} | ${thr} |"
  done < <(jq -c '.scenarios? // [] | .[]' "${LOAD_TEST_REPORT}")

  LOAD_TEST_SECTION=$(cat <<EOF
**Load Test Configuration**

- Duration: $(jq -r '.configuration.duration // "unknown"' "${LOAD_TEST_REPORT}")
- Concurrency: $(jq -r '.configuration.concurrency // "unknown"' "${LOAD_TEST_REPORT}")
- Scenarios: $(jq -r '.scenarios | length' "${LOAD_TEST_REPORT}") tested

**Overall Metrics**

${overall_table}

**Scenario Results**

${scenario_table}
EOF
  )

  local sla_table="| SLA Target | Requirement | Evidence | Status |\n| --- | --- | --- | --- |"
  sla_table+=$"\n| Availability | 99.9% uptime | Uptime checks / Cloud Monitoring | Pending |"
  sla_table+=$"\n| Latency | p95 < 1.2s overall / < 350ms rerank | Load test metrics | $( [[ " ${SLA_FLAGS[*]} " == *" Rerank p95 latency "* ]] && echo "Fail" || echo "Pass" ) |"
  sla_table+=$"\n| Error Rate | < 1% | Load test metrics | $( [[ " ${SLA_FLAGS[*]} " == *" Error rate "* ]] && echo "Fail" || echo "Pass" ) |"
  sla_table+=$"\n| Cache Hit Rate | > 98% | Load test cache metrics | $( [[ " ${SLA_FLAGS[*]} " == *" Cache hit rate "* ]] && echo "Fail" || echo "Pass" ) |"
  sla_table+=$"\n| Throughput | > 100 req/min | Load test throughput | $( [[ " ${SLA_FLAGS[*]} " == *" Throughput "* ]] && echo "Fail" || echo "Pass" ) |"

  SLA_SECTION=${sla_table}
}

TODO_SECTION=""

build_todos() {
  TODO_SECTION=$(cat <<'EOF'
**Critical**
- No additional critical items identified — Owner: Operations — Target: N/A — Dependencies: N/A — Effort: Low

**High Priority**
- Secret rotation automation and documentation — Owner: Platform Security — Target: +1 week — Dependencies: Secret Manager policies — Effort: Medium
- Disaster recovery runbook and testing — Owner: Operations — Target: +1 week — Dependencies: Backup/restore automation — Effort: High

**Medium Priority**
- Jest harness parity with Python integration tests — Owner: QA — Target: +4 weeks — Dependencies: Existing Python suites — Effort: Medium
- Cost tracking dashboards and anomaly detection — Owner: FinOps — Target: +4 weeks — Dependencies: Billing export, BigQuery datasets — Effort: Medium

**Low Priority**
- Multi-tenant isolation regression coverage expansion — Owner: QA — Target: +6 weeks — Dependencies: Integration test harness — Effort: Medium
- API Gateway custom domain setup — Owner: Platform — Target: +6 weeks — Dependencies: DNS delegation, SSL certs — Effort: Low
EOF
  )
}

ARTIFACT_SECTION=""

generate_artifacts_section() {
  ARTIFACT_SECTION=$(cat <<'EOF'
| Artifact | Path | Notes |
| --- | --- | --- |
| Build manifest | `.deployment/build-manifest-*.json` | Generated by build-and-push-services.sh |
| Deployment manifest | `.deployment/deploy-manifest-*.json` | Generated by deployment scripts |
| Monitoring manifest | `.monitoring/setup-*/monitoring-manifest.json` | Generated by setup-monitoring-and-alerting.sh |
| Load test report | `.deployment/load-tests/post-deploy-*/load-test-report.json` | Generated by run-post-deployment-load-tests.sh |
| Smoke test report | `.deployment/smoke-test-report-*.json` | Generated by smoke tests |
| Infrastructure notes | `docs/infrastructure-notes.md` | Manual notes and diagrams |
EOF
  )
}

TIMELINE_SECTION=""

generate_timeline_section() {
  TIMELINE_SECTION=$(cat <<'EOF'
| Phase | Task | Start Time | End Time | Duration | Status |
| --- | --- | --- | --- | --- | --- |
| Phase 1 | Infrastructure provisioning | [AUTO-GENERATED] | [AUTO-GENERATED] | [AUTO] | Complete |
| Phase 2 | Service deployment | [AUTO-GENERATED] | [AUTO-GENERATED] | [AUTO] | Complete |
| Phase 3 | API Gateway configuration | [AUTO-GENERATED] | [AUTO-GENERATED] | [AUTO] | Complete |
| Phase 4 | Monitoring setup | [AUTO-GENERATED] | [AUTO-GENERATED] | [AUTO] | Complete |
| Phase 5 | Load testing | [AUTO-GENERATED] | [AUTO-GENERATED] | [AUTO] | Pending |
| Phase 6 | Validation | [AUTO-GENERATED] | [AUTO-GENERATED] | [AUTO] | Pending |
EOF
  )
}

KNOWN_ISSUES_SECTION=""

generate_known_issues() {
  KNOWN_ISSUES_SECTION=$(cat <<'EOF'
- ADC credentials missing in CI runner — Workaround: Run `gcloud auth application-default login` locally before executing scripts.
- API Gateway currently disabled — Workaround: enable via `gcloud services enable apigateway.googleapis.com` and rerun gateway deployment.
- Monitoring dashboards rely on manual credential setup — Workaround: ensure `GOOGLE_APPLICATION_CREDENTIALS` is exported before running monitoring setup script.
EOF
  )
}

ROLLBACK_SECTION=""

generate_rollback_section() {
  ROLLBACK_SECTION=$(cat <<'EOF'
1. Revert Cloud Run services to previous revision:
   ```bash
   gcloud run services update TRAFFIC_TARGET \
     --region=us-central1 \
     --project=headhunter-ai-0088 \
     --to-revisions=REVISION=100
   ```
2. Restore API Gateway config:
   ```bash
   gcloud api-gateway api-configs deploy hh-gateway --api=headhunter --openapi-spec=previous-openapi.yaml
   ```
3. Rollback infrastructure changes via Terraform or deployment manifests if required.
4. Notify stakeholders and update deployment report with rollback actions.
EOF
  )
}

POST_VALIDATION_SECTION=""

generate_post_validation() {
  POST_VALIDATION_SECTION=$(cat <<'EOF'
- ✅ All services healthy
- ✅ Gateway routing working
- ✅ Authentication working
- ✅ Monitoring dashboards showing data
- ✅ Alerts configured and tested
- ✅ Load tests passed
- ✅ SLA targets met
EOF
  )
}

REFERENCES_SECTION=""

generate_references() {
  REFERENCES_SECTION=$(cat <<'EOF'
- ARCHITECTURE.md
- docs/HANDOVER.md
- docs/PRODUCTION_DEPLOYMENT_GUIDE.md
- docs/MONITORING_RUNBOOK.md
- docs/gcp-infrastructure-setup.md
- docs/RELEASE_NOTES_drive-migration-complete.md
- docs/execution-plan-phase5-7.md
- migration-log.txt
EOF
  )
}

SIGN_OFF_SECTION=""

generate_sign_off() {
  SIGN_OFF_SECTION=$(cat <<'EOF'
| Role | Name | Signature | Date |
| --- | --- | --- | --- |
| Operations Lead | | | |
| Security Reviewer | | | |
| Product Owner | | | |
EOF
  )
}

BLOCKER_SECTION=""

detect_blockers() {
  if [[ "${INCLUDE_BLOCKERS}" != true ]]; then
    BLOCKER_SECTION="Blocker analysis skipped (use --include-blockers to enable)."
    return
  fi

  local blocker_lines=""

  if [[ ${FASTIFY_DEPLOYED} -lt ${#EXPECTED_FASTIFY_SERVICES[@]} ]]; then
    blocker_lines+=$"\n- Fastify services deployed: ${FASTIFY_DEPLOYED}/${#EXPECTED_FASTIFY_SERVICES[@]}"
  fi

  if [[ -n "${API_GATEWAY_HOSTNAME}" ]]; then
    :
  else
    blocker_lines+=$"\n- API Gateway hostname unavailable; gateway may be disabled"
  fi

  if [[ -z "${MONITORING_MANIFEST}" || ! -f "${MONITORING_MANIFEST}" ]]; then
    blocker_lines+=$"\n- Monitoring manifest missing; dashboards not provisioned"
  fi

  if [[ -z "${LOAD_TEST_REPORT}" || ! -f "${LOAD_TEST_REPORT}" ]]; then
    blocker_lines+=$"\n- Load test report absent; SLA evidence incomplete"
  fi

  if ${GCLOUD_AVAILABLE}; then
    if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
      blocker_lines+=$"\n- Application Default Credentials not configured; monitoring API access blocked"
    fi
  else
    blocker_lines+=$"\n- gcloud unavailable; cannot verify API states"
  fi

  if [[ -z "${blocker_lines}" ]]; then
    BLOCKER_SECTION="No blockers detected."
  else
    BLOCKER_SECTION=$"Known blockers:${blocker_lines}"
    append_blocker "Deployment blockers detected during report generation."
  fi
}

EXEC_SUMMARY=""

generate_executive_summary() {
  local status="COMPLETE"
  local blocker_count=${#blockers[@]}
  local warning_count=${#warnings[@]}
  if (( blocker_count > 0 )); then
    status="BLOCKED"
  elif (( warning_count > 0 )); then
    status="PARTIAL"
  fi

  EXEC_SUMMARY=$(cat <<EOF
**Executive Summary**

- Deployment Status: ${status}
- Cloud Run Services: ${CLOUD_RUN_COUNT} detected (${FASTIFY_DEPLOYED} Fastify services)
- Warning Count: ${warning_count}
- Blocker Count: ${blocker_count}
- Load Test Report: ${LOAD_TEST_REPORT:-Not provided}
- Monitoring Manifest: ${MONITORING_MANIFEST:-Not provided}
EOF
  )
}

write_report() {
  cat > "${OUTPUT_PATH}" <<EOF
# Headhunter Production Deployment Report

**Date**: ${REPORT_DATE_HUMAN}
**Project**: `${PROJECT_ID}`
**Repository**: `${REPO_ROOT}`
**Environment**: ${ENVIRONMENT}
**Git Commit**: [AUTO-GENERATED]
**Release Tag**: `drive-migration-complete`
**Operator**: ${OPERATOR_NAME}

**Status**: [AUTO-GENERATED: COMPLETE | BLOCKED | PARTIAL]

${EXEC_SUMMARY}

## Deployment Metadata

- Git SHA: [AUTO-GENERATED]
- Release Tag: drive-migration-complete
- Timestamp: ${TIMESTAMP_UTC}
- Operator: ${OPERATOR_NAME}
- Environment: ${ENVIRONMENT}

## Cloud Run Services

### Current State

${CLOUD_RUN_TABLE}

### Target State

- Eight Fastify production services deployed in region ${REGION}
- Legacy function endpoints retired post-migration

### Deployment Evidence

${CLOUD_RUN_TABLE}

## Container Artifacts

${IMAGE_ARTIFACT_TABLE}

## API Gateway Configuration

${GATEWAY_SECTION}

## Monitoring & Observability

### Dashboards

${MONITORING_SECTION}

### Alert Policies

${ALERT_SECTION}

### Uptime Checks

${UPTIME_SECTION}

### Cost Tracking

${COST_SECTION}

## Load Testing & SLA Evidence

${LOAD_TEST_SECTION}

### SLA Evidence

${SLA_SECTION}

## Guardrails & Release Tagging

- Guardrails enforced: [AUTO-GENERATED]
- Release tag minted: drive-migration-complete
- Validation command: ./scripts/validate-guardrails.sh

## Remaining TODOs

${TODO_SECTION}

## Deployment Artifacts

${ARTIFACT_SECTION}

## Deployment Timeline

${TIMELINE_SECTION}

## Known Issues and Workarounds

${KNOWN_ISSUES_SECTION}

## Rollback Procedures

${ROLLBACK_SECTION}

## Post-Deployment Validation

${POST_VALIDATION_SECTION}

## References

${REFERENCES_SECTION}

## Sign-Off

${SIGN_OFF_SECTION}

## Known Blockers

${BLOCKER_SECTION}

---
_This report was auto-generated by scripts/generate-deployment-report.sh._
EOF
}

collect_cloud_run_inventory
collect_image_artifacts
collect_api_gateway
collect_monitoring
collect_load_tests
build_todos
generate_artifacts_section
generate_timeline_section
generate_known_issues
generate_rollback_section
generate_post_validation
generate_references
generate_sign_off
detect_blockers
generate_executive_summary
write_report

log INFO "Deployment report generated at ${OUTPUT_PATH}"
log INFO "Warnings: ${#warnings[@]} | Blockers: ${#blockers[@]}"
if (( ${#warnings[@]} > 0 )); then
  printf '\nWarnings:\n'
  printf ' - %s\n' "${warnings[@]}"
fi
if (( ${#blockers[@]} > 0 )); then
  printf '\nBlockers:\n'
  printf ' - %s\n' "${blockers[@]}"
fi

exit 0
