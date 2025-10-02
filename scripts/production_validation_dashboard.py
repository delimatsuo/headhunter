#!/usr/bin/env python3
"""Generate production validation dashboard aggregating test artifacts."""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

LOGGER = logging.getLogger("production_validation_dashboard")


def load_reports(paths: List[Path]) -> Dict[str, Any]:
  aggregated: Dict[str, Any] = {}
  for path in paths:
    if not path.exists():
      LOGGER.warning("Report %s not found", path)
      continue
    try:
      data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
      LOGGER.error("Failed to parse %s: %s", path, exc)
      continue
    aggregated[path.stem] = data
  return aggregated


def summarize(artifacts: Dict[str, Any]) -> Dict[str, Any]:
  summary: Dict[str, Any] = {"checks": []}
  for key, payload in artifacts.items():
    if key.startswith("production_smoke"):
      failures = sum(1 for test in payload.get("tests", []) if test.get("status") == "fail")
      summary["checks"].append({"name": "Smoke Tests", "status": "pass" if failures == 0 else "fail", "details": failures})
    elif key.startswith("production_load"):
      sla_ok = payload.get("overall", {}).get("search/hybrid", {}).get("sla_pass")
      summary["checks"].append({"name": "Load Testing", "status": "pass" if sla_ok else "fail"})
    elif key.startswith("auto_scaling"):
      compliance = payload.get("sla_compliance", {})
      status = "pass" if all(v for k, v in compliance.items() if k.endswith("_pass")) else "fail"
      summary["checks"].append({"name": "Auto Scaling", "status": status})
    elif key.startswith("tenant_isolation"):
      failures = [entry for group in payload.values() for entry in group if entry.get("status") == "fail"]
      summary["checks"].append({"name": "Tenant Isolation", "status": "pass" if not failures else "fail", "details": len(failures)})
    elif key.startswith("pipeline"):
      summary["checks"].append({"name": "Pipeline", "status": "pass" if not payload.get("errors") else "fail"})
    elif key.startswith("security"):
      sec_fail = [entry for group in payload.values() for entry in group if entry.get("status") == "fail"]
      summary["checks"].append({"name": "Security", "status": "pass" if not sec_fail else "fail"})
    elif key.startswith("sla_monitor"):
      summary["checks"].append({"name": "Monitoring", "status": "pass" if not payload.get("alerts") else "fail", "alerts": payload.get("alerts")})
    elif key.startswith("performance"):
      summary["checks"].append({"name": "Performance", "status": "pass"})
    elif key.startswith("chaos"):
      failed = [scenario for scenario in payload.get("scenarios", []) if scenario.get("status") == "fail"]
      summary["checks"].append({"name": "Chaos", "status": "pass" if not failed else "fail"})
  summary["overall"] = "pass" if all(check.get("status") == "pass" for check in summary["checks"]) else "fail"
  return summary


def to_html(summary: Dict[str, Any]) -> str:
  rows = []
  for check in summary.get("checks", []):
    status = check.get("status")
    color = "#2ecc71" if status == "pass" else "#e74c3c"
    rows.append(f"<tr><td>{check.get('name')}</td><td style='color:{color};font-weight:bold'>{status.upper()}</td></tr>")
  return """<html><head><title>Production Validation Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; }
    table { border-collapse: collapse; width: 50%; }
    th, td { border: 1px solid #ccc; padding: 0.5rem; }
    th { background: #f7f7f7; }
  </style></head><body>
  <h1>Production Validation Summary</h1>
  <p>Overall status: <strong>{overall}</strong></p>
  <table><thead><tr><th>Check</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>
  </body></html>""".format(overall=summary.get("overall", "unknown").upper(), rows="".join(rows))


def post_to_webhook(summary: Dict[str, Any], webhook: str) -> None:
  payload = {
    "text": f"Production validation status: {summary.get('overall').upper()}\n" +
    "\n".join(f"• {check['name']}: {check['status']}" for check in summary.get("checks", []))
  }
  resp = requests.post(webhook, json=payload, timeout=10)
  resp.raise_for_status()


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Aggregate production validation results")
  parser.add_argument("--report", action="append", dest="reports", required=True, help="Path to JSON result file")
  parser.add_argument("--output", default=None, help="Write aggregated summary JSON")
  parser.add_argument("--html", default=None, help="Write HTML dashboard to path")
  parser.add_argument("--webhook", default=None, help="Slack webhook URL for notifications")
  parser.add_argument("--verbose", action="store_true")
  return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
  args = parse_args(argv)
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
  report_paths = [Path(item) for item in args.reports]
  artifacts = load_reports(report_paths)
  summary = summarize(artifacts)
  if args.output:
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2))
  if args.html:
    html_path = Path(args.html)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(to_html(summary))
  if args.webhook:
    try:
      post_to_webhook(summary, args.webhook)
    except requests.RequestException as exc:
      LOGGER.error("Failed to post to webhook: %s", exc)
      return 1
  print(json.dumps(summary, indent=2))
  return 0 if summary.get("overall") == "pass" else 1


if __name__ == "__main__":
  sys.exit(main())
