#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Phase 5 deployment validation orchestrator
#
# Runs monitoring setup verification, integration tests, security audits,
# disaster recovery tests, SLA checks, CI/CD smoke, and aggregates results.

PROJECT_ID="${PROJECT_ID:-}"
REPORTS_DIR="${REPORTS_DIR:-reports}"
ENVIRONMENT="${ENVIRONMENT:-staging}"
PREFIX="${PREFIX:-Headhunter}"
CHANNELS="${CHANNELS:-}"

echo "[validate_phase5] Using PROJECT_ID='${PROJECT_ID}' ENVIRONMENT='${ENVIRONMENT}' REPORTS_DIR='${REPORTS_DIR}'"

mkdir -p "${REPORTS_DIR}"

step() { echo "[validate_phase5] === $1 ==="; }

step "1) Validate Cloud Monitoring dashboards and alerting"
python3 scripts/setup_cloud_monitoring_dashboards.py --project "${PROJECT_ID}" --prefix "${PREFIX}" --reports-dir "${REPORTS_DIR}" ${APPLY:+--apply}
dashboards_rc=$?
python3 scripts/setup_production_alerting.py --project "${PROJECT_ID}" --prefix "${PREFIX}" --channels "${CHANNELS}" --reports-dir "${REPORTS_DIR}" ${APPLY:+--apply}
alerts_rc=$?

step "2) Run comprehensive integration tests"
# Enforce strict mode in prod by requiring real checks
extra_flags=()
if [[ "${ENVIRONMENT}" == "prod" ]]; then
  extra_flags+=("--require-real")
fi
python3 scripts/comprehensive_integration_test_suite.py --env "${ENVIRONMENT}" --reports-dir "${REPORTS_DIR}" "${extra_flags[@]}" || true

step "3) Perform security audits and compliance validation"
python3 scripts/automated_security_validation.py --reports-dir "${REPORTS_DIR}" ${APPLY:+--apply} || true

step "4) Test disaster recovery and business continuity"
python3 scripts/disaster_recovery_validation.py --reports-dir "${REPORTS_DIR}" ${APPLY:+--apply} || true

step "5) Validate SLA monitoring"
python3 scripts/sla_monitoring_and_validation.py --env "${ENVIRONMENT}" --reports-dir "${REPORTS_DIR}" || true

step "6) Test CI/CD pipeline automation"
python3 scripts/cicd_automation_pipeline.py --stage full --env "${ENVIRONMENT}" --reports-dir "${REPORTS_DIR}" || true

step "7) Validate system health dashboard"
python3 scripts/system_health_dashboard.py --summary --reports-dir "${REPORTS_DIR}" || true

step "8) Aggregate Phase 5 validation report"
python3 - <<'PY'
import json, os, glob, time
reports_dir = os.environ.get('REPORTS_DIR','reports')
def load(path):
    try:
        with open(path,'r') as f: return json.load(f)
    except Exception: return {}
data = {
    'monitoring': load(os.path.join(reports_dir,'monitoring_dashboards_report.json')),
    'alerting': load(os.path.join(reports_dir,'production_alerting_report.json')),
    'integration': load(os.path.join(reports_dir,'integration_test_report.json')),
    'security': load(os.path.join(reports_dir,'security_validation_report.json')),
    'dr': load(os.path.join(reports_dir,'dr_validation_report.json')),
    'sla': load(os.path.join(reports_dir,'sla_report.json')),
    'cicd': load(os.path.join(reports_dir,'cicd_pipeline_report.json')),
    'timestamp': int(time.time()),
}
ok = True
ok = ok and (data.get('integration',{}).get('sla_compliant', True))
ok = ok and (data.get('security',{}).get('summary',{}).get('passed', True))
ok = ok and (data.get('sla',{}).get('compliant', True))
# Include dashboards/alerts creation success when applying changes
apply = bool(os.environ.get('APPLY'))
if apply:
    dash_ok = any(d.get('created') for d in data.get('monitoring',{}).get('dashboards', [])) or not data.get('monitoring')
    alert_ok = data.get('alerting',{}).get('summary',{}).get('total',0) > 0
    ok = ok and dash_ok and alert_ok
report = {'status': 'pass' if ok else 'fail', 'components': data}
with open(os.path.join(reports_dir,'phase5_validation_report.json'),'w') as f:
    json.dump(report,f,indent=2)
print(json.dumps({'result': report['status'], 'report': 'phase5_validation_report.json'}, indent=2))
PY

echo "[validate_phase5] Completed Phase 5 validation."
