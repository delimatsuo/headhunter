#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/run-post-deployment-load-tests.sh --gateway-endpoint <url> [options]

Runs post-deployment load scenarios against the production gateway and validates SLA targets.

Required:
  --gateway-endpoint <url>     Fully qualified HTTPS endpoint for the API gateway

Options:
  --tenant-id <id>             Tenant identifier used for auth headers (default: tenant-alpha)
  --oauth-client-id <id>       OAuth client ID for client credentials flow
  --oauth-client-secret <sec>  OAuth client secret for client credentials flow
  --token-url <url>            Override OAuth token URL (defaults to value from secret or config)
  --api-key <key>              API key to use when OAuth token is unavailable
  --duration <seconds>         Duration per scenario (default: 300)
  --concurrency <count>        Concurrent simulated users (default: 10)
  --ramp-up <seconds>          Ramp-up period before steady load (default: 30)
  --scenarios <list|all>       Comma-separated scenario names or 'all' for full suite
  --output-dir <path>          Directory for load test artifacts (default: .deployment/load-tests/post-deploy-<timestamp>)
  --skip-validation            Skip SLA validation step
  --dry-run                    Print actions without executing load tests
  --help                       Show this help message
USAGE
}

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

warn() {
  printf '[%s] WARN: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
}

fail() {
  printf '[%s] ERROR: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required command '$1' not found in PATH"
  fi
}

SCENARIO_DEFINITIONS='[
  {"name": "embedding", "label": "Embedding generation", "method": "POST", "path": "/v1/embeddings/generate"},
  {"name": "hybrid-search", "label": "Hybrid search", "method": "POST", "path": "/v1/search/hybrid"},
  {"name": "rerank", "label": "Rerank", "method": "POST", "path": "/v1/search/rerank"},
  {"name": "evidence", "label": "Evidence retrieval", "method": "GET", "path": "/v1/evidence/{candidateId}"},
  {"name": "eco-search", "label": "ECO search", "method": "GET", "path": "/v1/occupations/search"},
  {"name": "skill-expansion", "label": "Skill expansion", "method": "POST", "path": "/v1/skills/expand"},
  {"name": "admin-snapshots", "label": "Admin snapshots", "method": "GET", "path": "/v1/admin/snapshots"},
  {"name": "profile-enrichment", "label": "Profile enrichment", "method": "POST", "path": "/v1/enrich/profile"},
  {"name": "end-to-end", "label": "Search pipeline", "method": "FLOW", "path": "embed -> search -> rerank -> evidence"}
]'

GATEWAY_ENDPOINT=""
TENANT_ID="tenant-alpha"
OAUTH_CLIENT_ID=""
OAUTH_CLIENT_SECRET=""
TOKEN_URL=""
API_KEY=""
DURATION=300
CONCURRENCY=10
RAMP_UP=30
SCENARIOS="all"
OUTPUT_DIR=""
SKIP_VALIDATION=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gateway-endpoint)
      GATEWAY_ENDPOINT="$2"; shift 2 ;;
    --tenant-id)
      TENANT_ID="$2"; shift 2 ;;
    --oauth-client-id)
      OAUTH_CLIENT_ID="$2"; shift 2 ;;
    --oauth-client-secret)
      OAUTH_CLIENT_SECRET="$2"; shift 2 ;;
    --token-url)
      TOKEN_URL="$2"; shift 2 ;;
    --api-key)
      API_KEY="$2"; shift 2 ;;
    --duration)
      DURATION="$2"; shift 2 ;;
    --concurrency)
      CONCURRENCY="$2"; shift 2 ;;
    --ramp-up)
      RAMP_UP="$2"; shift 2 ;;
    --scenarios)
      SCENARIOS="$2"; shift 2 ;;
    --output-dir)
      OUTPUT_DIR="$2"; shift 2 ;;
    --skip-validation)
      SKIP_VALIDATION=true; shift ;;
    --dry-run)
      DRY_RUN=true; shift ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      fail "Unknown argument: $1" ;;
  esac
done

if [[ -z "$GATEWAY_ENDPOINT" ]]; then
  fail "--gateway-endpoint is required"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/utils/repo_guard.sh"

require_command python3
require_command curl
require_command jq
require_command gcloud

if [[ "$GATEWAY_ENDPOINT" != https://* ]]; then
  warn "Gateway endpoint does not appear to be HTTPS; continuing"
fi

log "Gateway endpoint: ${GATEWAY_ENDPOINT}"

if [[ "$DRY_RUN" != true ]]; then
  if ! curl -fsS "${GATEWAY_ENDPOINT%/}/health" >/dev/null; then
    warn "Gateway health endpoint returned non-success; continuing but results may fail"
  else
    log "Gateway health check passed"
  fi
else
  log "Dry-run enabled; skipping gateway health probe"
fi

TIMESTAMP="$(date -u +'%Y%m%d-%H%M%S')"
if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="${PROJECT_ROOT}/.deployment/load-tests/post-deploy-${TIMESTAMP}"
else
  OUTPUT_DIR="$OUTPUT_DIR"
fi
RESULTS_DIR="${OUTPUT_DIR}/results"
LOGS_DIR="${OUTPUT_DIR}/logs"
mkdir -p "$RESULTS_DIR" "$LOGS_DIR"

SCENARIO_LIST=()
if [[ "$SCENARIOS" == "all" ]]; then
  mapfile -t SCENARIO_LIST < <(echo "$SCENARIO_DEFINITIONS" | jq -r '.[].name')
else
  IFS=',' read -r -a SCENARIO_LIST <<<"$SCENARIOS"
fi

if (( ${#SCENARIO_LIST[@]} == 0 )); then
  fail "No scenarios selected"
fi

log "Running scenarios: ${SCENARIO_LIST[*]}"

AUTH_TOKEN=""
TOKEN_SOURCE=""

write_payload() {
  local name="$1"
  local payload="$2"
  local path="${RESULTS_DIR}/payload-${name}.json"
  printf '%s\n' "$payload" >"$path"
  echo "$path"
}

acquire_credentials_from_secret() {
  local secret_name="oauth-client-${TENANT_ID}"
  local raw
  if ! raw=$(gcloud secrets versions access latest --secret="$secret_name" 2>/dev/null); then
    warn "Unable to read secret ${secret_name}; skipping"
    return 1
  fi
  local parsed_id parsed_secret parsed_token_url
  parsed_id=$(echo "$raw" | jq -r '.client_id // empty')
  parsed_secret=$(echo "$raw" | jq -r '.client_secret // empty')
  parsed_token_url=$(echo "$raw" | jq -r '.token_url // empty')
  if [[ -n "$parsed_id" && -n "$parsed_secret" ]]; then
    OAUTH_CLIENT_ID="$parsed_id"
    OAUTH_CLIENT_SECRET="$parsed_secret"
    if [[ -z "$TOKEN_URL" && -n "$parsed_token_url" ]]; then
      TOKEN_URL="$parsed_token_url"
    fi
    log "Loaded OAuth credentials from Secret Manager"
    return 0
  fi
  warn "Secret ${secret_name} missing client credentials"
  return 1
}

acquire_oauth_token() {
  if [[ -z "$OAUTH_CLIENT_ID" || -z "$OAUTH_CLIENT_SECRET" ]]; then
    acquire_credentials_from_secret || return 1
  fi
  local token_endpoint
  token_endpoint="${TOKEN_URL:-${GATEWAY_ENDPOINT%/}/oauth/token}"
  if [[ "$DRY_RUN" == true ]]; then
    AUTH_TOKEN="dry-run-token"
    TOKEN_SOURCE="dry-run"
    return 0
  fi
  local response
  response=$(curl -sS -X POST "$token_endpoint" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d "grant_type=client_credentials&client_id=${OAUTH_CLIENT_ID}&client_secret=${OAUTH_CLIENT_SECRET}" 2>/dev/null || true)
  local access_token
  access_token=$(echo "$response" | jq -r '.access_token // empty' 2>/dev/null || true)
  local expires
  expires=$(echo "$response" | jq -r '.expires_in // empty' 2>/dev/null || true)
  if [[ -z "$access_token" ]]; then
    warn "OAuth token acquisition failed via ${token_endpoint}"
    return 1
  fi
  AUTH_TOKEN="$access_token"
  TOKEN_SOURCE="oauth (${token_endpoint})"
  if [[ -n "$expires" ]]; then
    log "Obtained OAuth token (expires in ${expires}s)"
  else
    log "Obtained OAuth token"
  fi
  return 0
}

if ! acquire_oauth_token; then
  if [[ -n "$API_KEY" ]]; then
    warn "Falling back to API key authentication"
    TOKEN_SOURCE="api-key"
  else
    warn "No authentication mechanism available; proceeding without auth"
    TOKEN_SOURCE="none"
  fi
fi

SCENARIO_RESULTS_FILE="${RESULTS_DIR}/scenario-results.jsonl"
: >"$SCENARIO_RESULTS_FILE"

run_scenario() {
  local name="$1"
  local result_path="${RESULTS_DIR}/scenario-${name}.json"
  local log_path="${LOGS_DIR}/scenario-${name}.log"
  if [[ "$DRY_RUN" == true ]]; then
    log "[dry-run] Would execute scenario ${name}"
    jq -n --arg name "$name" --arg status "dry-run" '{scenario:$name, status:$status}' >"$result_path"
    echo "$(jq -n --arg name "$name" --arg status "dry-run" '{scenario:$name, status:$status}')" >>"$SCENARIO_RESULTS_FILE"
    return 0
  fi
  local cmd=(python3 "${SCRIPT_DIR}/load-test-stack.py" --gateway-endpoint "$GATEWAY_ENDPOINT" --tenant-id "$TENANT_ID" --duration "$DURATION" --concurrency "$CONCURRENCY" --ramp-up "$RAMP_UP" --scenario "$name" --output "$result_path")
  if [[ -n "$AUTH_TOKEN" ]]; then
    cmd+=(--auth-token "$AUTH_TOKEN")
  elif [[ -n "$API_KEY" ]]; then
    cmd+=(--api-key "$API_KEY")
  fi
  log "Running scenario ${name}"
  if ! "${cmd[@]}" >"$log_path" 2>&1; then
    warn "Scenario ${name} failed; check ${log_path}"
    jq -n --arg name "$name" --arg status "failed" '{scenario:$name, status:$status}' >>"$SCENARIO_RESULTS_FILE"
    return 1
  fi
  if [[ -s "$result_path" ]]; then
    jq -c '.' "$result_path" >>"$SCENARIO_RESULTS_FILE" 2>/dev/null || {
      warn "Unable to parse scenario result for ${name}"
      jq -n --arg name "$name" --arg status "completed" '{scenario:$name, status:$status}' >>"$SCENARIO_RESULTS_FILE"
    }
  else
    warn "Scenario result file empty for ${name}"
    jq -n --arg name "$name" --arg status "completed" '{scenario:$name, status:$status}' >>"$SCENARIO_RESULTS_FILE"
  fi
  return 0
}

SCENARIO_FAILURES=0
for scenario in "${SCENARIO_LIST[@]}"; do
  if ! run_scenario "$scenario"; then
    SCENARIO_FAILURES=$((SCENARIO_FAILURES + 1))
  fi
done

if (( SCENARIO_FAILURES > 0 )); then
  warn "${SCENARIO_FAILURES} scenario(s) failed"
fi

AGGREGATE_JSON="${RESULTS_DIR}/aggregate.json"
python3 - <<'PY' "$SCENARIO_RESULTS_FILE" "$AGGREGATE_JSON" "$SCENARIO_DEFINITIONS"
import json
import os
import sys
from statistics import mean

results_file, aggregate_path, definitions_json = sys.argv[1:4]
definitions = {item['name']: item for item in json.loads(definitions_json)}
records = []
if os.path.exists(results_file):
    with open(results_file, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            records.append(record)
summary = {
    'scenarios': [],
    'totals': {
        'requests': 0,
        'errors': 0,
        'p95LatencyMs': None,
        'p99LatencyMs': None,
        'throughputPerMin': None,
    }
}
latencies_p95 = []
latencies_p99 = []
throughputs = []
for record in records:
    name = record.get('scenario')
    definition = definitions.get(name, {})
    entry = {
        'scenario': name,
        'label': definition.get('label', name),
        'status': record.get('status', 'completed'),
        'requests': record.get('requests', record.get('totalRequests')),
        'errors': record.get('errors', record.get('errorCount')),
        'p95LatencyMs': record.get('p95LatencyMs') or record.get('latency', {}).get('p95'),
        'p99LatencyMs': record.get('p99LatencyMs') or record.get('latency', {}).get('p99'),
        'throughputPerMin': record.get('throughputPerMin') or record.get('throughput', {}).get('perMinute'),
        'outputPath': record.get('outputPath'),
    }
    summary['scenarios'].append(entry)
    if entry['requests']:
        summary['totals']['requests'] += entry['requests']
    if entry['errors']:
        summary['totals']['errors'] += entry['errors']
    if entry['p95LatencyMs'] is not None:
        latencies_p95.append(entry['p95LatencyMs'])
    if entry['p99LatencyMs'] is not None:
        latencies_p99.append(entry['p99LatencyMs'])
    if entry['throughputPerMin'] is not None:
        throughputs.append(entry['throughputPerMin'])
if latencies_p95:
    summary['totals']['p95LatencyMs'] = max(latencies_p95)
if latencies_p99:
    summary['totals']['p99LatencyMs'] = max(latencies_p99)
if throughputs:
    summary['totals']['throughputPerMin'] = mean(throughputs)
with open(aggregate_path, 'w', encoding='utf-8') as fh:
    json.dump(summary, fh, indent=2)
PY

AGGREGATED_RESULTS=$(cat "$AGGREGATE_JSON" 2>/dev/null || echo '{}')

SLA_REPORT_JSON="${RESULTS_DIR}/sla-validation.json"
if [[ "$SKIP_VALIDATION" == true ]]; then
  jq -n '{skipped: true, reason: "skip-validation flag"}' >"$SLA_REPORT_JSON"
else
  python3 - <<'PY' "$AGGREGATE_JSON" "$SLA_REPORT_JSON"
import json
import sys

def eval_status(value, threshold, operator):
    if value is None:
        return 'unknown'
    if operator == 'lt':
        return 'pass' if value < threshold else 'fail'
    if operator == 'gt':
        return 'pass' if value > threshold else 'fail'
    return 'unknown'

aggregate_path, output_path = sys.argv[1:3]
with open(aggregate_path, 'r', encoding='utf-8') as fh:
    aggregate = json.load(fh)

metrics = aggregate.get('totals', {})
scenarios = aggregate.get('scenarios', [])
scenario_map = {item.get('scenario'): item for item in scenarios}

report = {
    'overall': {
        'p95LatencyMs': {
            'value': metrics.get('p95LatencyMs'),
            'threshold': 1200,
            'status': eval_status(metrics.get('p95LatencyMs'), 1200, 'lt'),
        },
        'p99LatencyMs': {
            'value': metrics.get('p99LatencyMs'),
            'threshold': 1500,
            'status': eval_status(metrics.get('p99LatencyMs'), 1500, 'lt'),
        },
        'errorRate': {
            'value': (metrics.get('errors', 0) / metrics.get('requests', 1)) * 100 if metrics.get('requests') else None,
            'threshold': 1.0,
            'status': eval_status((metrics.get('errors', 0) / metrics.get('requests', 1)) * 100 if metrics.get('requests') else None, 1.0, 'lt'),
        },
        'throughputPerMin': {
            'value': metrics.get('throughputPerMin'),
            'threshold': 100,
            'status': eval_status(metrics.get('throughputPerMin'), 100, 'gt'),
        },
    },
    'scenarios': {
        'rerank': {
            'p95LatencyMs': scenario_map.get('rerank', {}).get('p95LatencyMs'),
            'threshold': 350,
            'status': eval_status(scenario_map.get('rerank', {}).get('p95LatencyMs'), 350, 'lt'),
        },
        'cached-read': {
            'p95LatencyMs': scenario_map.get('hybrid-search', {}).get('p95LatencyMs'),
            'threshold': 250,
            'status': eval_status(scenario_map.get('hybrid-search', {}).get('p95LatencyMs'), 250, 'lt'),
        },
        'cache-hit-rate': {
            'value': scenario_map.get('rerank', {}).get('cacheHitRate'),
            'threshold': 0.98,
            'status': eval_status(scenario_map.get('rerank', {}).get('cacheHitRate'), 0.98, 'gt'),
        },
    }
}
report['overall']['status'] = 'pass'
for check in report['overall'].values():
    if isinstance(check, dict) and check.get('status') == 'fail':
        report['overall']['status'] = 'fail'
        break
if report['overall']['status'] == 'pass':
    for check in report['scenarios'].values():
        if isinstance(check, dict) and check.get('status') == 'fail':
            report['overall']['status'] = 'fail'
            break
with open(output_path, 'w', encoding='utf-8') as fh:
    json.dump(report, fh, indent=2)
PY
fi

REPORT_JSON="${OUTPUT_DIR}/load-test-report.json"
python3 - <<'PY' "$REPORT_JSON" "$GATEWAY_ENDPOINT" "$TENANT_ID" "$DURATION" "$CONCURRENCY" "$RAMP_UP" "$SCENARIO_RESULTS_FILE" "$AGGREGATE_JSON" "$SLA_REPORT_JSON" "$TOKEN_SOURCE"
import json
import os
import sys
from datetime import datetime

(
    report_path,
    gateway_endpoint,
    tenant_id,
    duration,
    concurrency,
    ramp_up,
    scenarios_file,
    aggregate_path,
    sla_path,
    token_source,
) = sys.argv[1:10]

def load_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as fh:
        items = []
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                items.append({'raw': line})
        return items

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError:
            return {'raw': fh.read()}

report = {
    'generatedAt': datetime.utcnow().isoformat() + 'Z',
    'gatewayEndpoint': gateway_endpoint,
    'tenantId': tenant_id,
    'configuration': {
        'durationSeconds': int(duration),
        'concurrency': int(concurrency),
        'rampUpSeconds': int(ramp_up),
        'authentication': token_source,
    },
    'scenarios': load_lines(scenarios_file),
    'aggregate': load_json(aggregate_path),
    'slaValidation': load_json(sla_path),
}
with open(report_path, 'w', encoding='utf-8') as fh:
    json.dump(report, fh, indent=2)
print(report_path)
PY

REPORT_MD="${OUTPUT_DIR}/load-test-report.md"
python3 - <<'PY' "$REPORT_MD" "$REPORT_JSON" "$SCENARIO_DEFINITIONS"
import json
import sys
from datetime import datetime

report_md_path, report_json_path, definitions_json = sys.argv[1:4]
with open(report_json_path, 'r', encoding='utf-8') as fh:
    report = json.load(fh)
scenario_meta = {item['name']: item for item in json.loads(definitions_json)}

lines = []
lines.append(f"# Post-Deployment Load Test Report")
lines.append("")
lines.append(f"- Generated: {report['generatedAt']}")
lines.append(f"- Gateway Endpoint: {report['gatewayEndpoint']}")
lines.append(f"- Tenant: {report['tenantId']}")
lines.append(f"- Duration per scenario: {report['configuration']['durationSeconds']}s")
lines.append(f"- Concurrency: {report['configuration']['concurrency']}")
lines.append(f"- Ramp up: {report['configuration']['rampUpSeconds']}s")
lines.append(f"- Auth mode: {report['configuration']['authentication']}")
lines.append("")
lines.append("## Scenario Results")
lines.append("")
for scenario in report['scenarios']:
    name = scenario.get('scenario', 'unknown')
    meta = scenario_meta.get(name, {})
    lines.append(f"- **{meta.get('label', name)}** (`{name}`): status={scenario.get('status', 'unknown')}, requests={scenario.get('requests', 'n/a')}, errors={scenario.get('errors', 'n/a')}, p95={scenario.get('p95LatencyMs', 'n/a')}ms, throughput/min={scenario.get('throughputPerMin', 'n/a')}")
lines.append("")
lines.append("## Aggregate Metrics")
lines.append("")
agg = report.get('aggregate', {}).get('totals', {})
lines.append(f"- Total requests: {agg.get('requests', 'n/a')}")
lines.append(f"- Total errors: {agg.get('errors', 'n/a')}")
lines.append(f"- Worst-case p95 latency: {agg.get('p95LatencyMs', 'n/a')} ms")
lines.append(f"- Worst-case p99 latency: {agg.get('p99LatencyMs', 'n/a')} ms")
lines.append(f"- Average throughput/min: {agg.get('throughputPerMin', 'n/a')}")
lines.append("")
lines.append("## SLA Validation")
lines.append("")
validation = report.get('slaValidation', {})
if validation.get('skipped'):
    lines.append("- SLA validation skipped: " + validation.get('reason', 'user request'))
else:
    overall = validation.get('overall', {})
    lines.append(f"- Overall status: {overall.get('status', 'unknown')}")
    for key, detail in overall.items():
        if isinstance(detail, dict) and 'status' in detail:
            lines.append(f"  - {key}: value={detail.get('value')}, threshold={detail.get('threshold')}, status={detail.get('status')}")
    lines.append("")
    lines.append("### Scenario-specific checks")
    for key, detail in validation.get('scenarios', {}).items():
        if isinstance(detail, dict):
            lines.append(f"- {key}: value={detail.get('p95LatencyMs', detail.get('value'))}, threshold={detail.get('threshold')}, status={detail.get('status')}")
lines.append("")
lines.append("## Next Steps")
lines.append("- Review Cloud Monitoring dashboards during the load test window for correlated anomalies.")
lines.append("- Investigate any failures using Cloud Logging queries filtered by the load test time range.")
lines.append("- Capture follow-up actions in docs/MONITORING_RUNBOOK.md if remediation is required.")

with open(report_md_path, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(lines) + '\n')
PY

log "Load test artifacts written to ${OUTPUT_DIR}"
log "JSON report: ${REPORT_JSON}"
log "Markdown report: ${REPORT_MD}"
log "Aggregate metrics: ${AGGREGATE_JSON}"
log "SLA validation: ${SLA_REPORT_JSON}"

if (( SCENARIO_FAILURES > 0 )); then
  warn "Load test completed with scenario failures"
  exit 1
fi

log "Load tests completed"
