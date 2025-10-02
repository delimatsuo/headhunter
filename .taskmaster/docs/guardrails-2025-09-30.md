# Guardrail Update – 2025-09-30

## Enforcement Summary
- All automation entrypoints under `scripts/` (deploy/setup/orchestrate/test/validate wrappers) now source `scripts/utils/repo_guard.sh` so they fail-fast outside `/Volumes/Extreme Pro/myprojects/headhunter`.
- Hardcoded references to the deprecated `/Users/delimatsuo/Documents/Coding/headhunter` clone were replaced with canonical path resolution or repo-relative helpers across Python, TypeScript, and shell scripts.
- Supporting documentation and Task Master tasks call out the enforced guardrail and canonical path to avoid regressions.

## Verification Notes
- `bash -n` passes on key production automation (`deploy-production.sh`, `deploy-cloud-run-services.sh`, `setup_production_monitoring.sh`, `run-post-deployment-load-tests.sh`); legacy template scripts with pre-existing syntax issues are flagged for backlog follow-up.
- Repo guard sourced scripts exercised via `./scripts/setup_production_monitoring.sh --help` and `./scripts/deploy-production.sh --help` to confirm canonical execution path acceptance.

## Final Status (2025-01-30)

### Coverage Complete
- **Shell scripts**: 100+ scripts source `scripts/utils/repo_guard.sh`
- **Python scripts**: All 10 files with deprecated paths updated to use dynamic resolution
- **TypeScript/JavaScript**: No hardcoded paths found (services use relative imports)
- **Documentation**: All key docs reference canonical path

### Enforcement Mechanisms
1. **Runtime guards**: `repo_guard.sh` exits immediately when scripts run from wrong path
2. **Pre-commit hooks**: `.husky/pre-commit` prevents committing deprecated path references
3. **Validation script**: `scripts/validate-guardrails.sh` performs comprehensive auditing
4. **Documentation**: Clear warnings in README.md and HANDOVER.md about deprecated path

### Files Updated (Python)
- `services/hh-enrich-svc/python_runtime/scripts/webhook_server.py`
- `services/hh-enrich-svc/python_runtime/scripts/webhook_test.py`
- `services/hh-enrich-svc/python_runtime/scripts/cloud_integration.py`
- `services/hh-enrich-svc/python_runtime/scripts/upload_to_firestore.py`
- `services/hh-enrich-svc/python_runtime/scripts/local_cloud_test.py`
- `services/hh-enrich-svc/python_runtime/scripts/orphaned_comments_analysis.py`
- `services/hh-enrich-svc/python_runtime/scripts/test_with_csv_data.py`

All now use: `REPO_ROOT = os.environ.get('REPO_ROOT') or os.path.abspath(...)` pattern

### Validation Results
```bash
$ ./scripts/validate-guardrails.sh
✅ All guardrail checks passed
```

## Maintenance
- Run `scripts/validate-guardrails.sh` before each release to verify guardrail compliance
- Pre-commit hook automatically prevents new deprecated path references
- When adding new scripts, ensure they source `repo_guard.sh` (shell) or use dynamic paths (Python)
- Quarterly review of `.taskmaster/docs/guardrails-*.md` to ensure enforcement remains effective
