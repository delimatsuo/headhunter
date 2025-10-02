#!/usr/bin/env python3
"""Orchestrate ECO search integration deployment and validation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import requests

DEFAULT_DEPLOY_SCRIPT = Path(__file__).parent / 'deploy_eco_cloud_run_service.sh'
DEFAULT_VALIDATION_SCRIPT = Path(__file__).parent / 'validate_eco_performance_targets.py'


@dataclass
class OrchestratorConfig:
    project_id: str
    region: str = 'us-central1'
    service_name: str = 'eco-cloud-run'
    deployment_mode: str = 'blue-green'
    database_instance: Optional[str] = None
    database_secret: Optional[str] = None
    dataset_path: Optional[Path] = None
    health_timeout: int = 300
    report_path: Optional[Path] = None
    extra_env: Dict[str, str] = field(default_factory=dict)


class ECODeploymentOrchestrator:
    """High level automation for ECO search integration."""

    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config
        self.report: Dict[str, any] = {
            'project_id': config.project_id,
            'region': config.region,
            'service_name': config.service_name,
            'deployment_mode': config.deployment_mode,
            'steps': [],
        }

    def run(self) -> None:
        self._log_step('validate_database', self.validate_database)
        self._log_step('deploy_cloud_run', self.deploy_cloud_run)
        self._log_step('enable_feature_flags', self.enable_feature_flags)
        self._log_step('initialize_ab_testing', self.initialize_ab_testing)
        if self.config.dataset_path:
            self._log_step('validate_performance_targets', self.validate_performance_targets)
        self._log_step('monitor_deployment', self.monitor_deployment)
        self.generate_report()

    def validate_database(self) -> None:
        if not self.config.database_instance:
            raise ValueError('database_instance is required for validation')
        cmd = [
            'gcloud', 'sql', 'instances', 'describe',
            self.config.database_instance,
            '--project', self.config.project_id,
        ]
        self._run(cmd, check=True)

    def deploy_cloud_run(self) -> None:
        env = os.environ.copy()
        env.update(self.config.extra_env)
        cmd = [
            str(DEFAULT_DEPLOY_SCRIPT),
            f'--db-instance={self.config.database_instance}',
            f'--database-secret={self.config.database_secret}',
            f'--traffic={"1" if self.config.deployment_mode != "canary" else "0.1"}',
        ]
        if self.config.deployment_mode == 'canary':
            cmd.append('--redis-tier=standard')
        self._run(cmd, check=True, env=env)

    def enable_feature_flags(self) -> None:
        payload = {
            'featureFlags': {
                'ECO_TITLE_ALIGNMENT_ENABLED': True,
            },
        }
        self._invoke_function('updateECOConfiguration', payload)

    def initialize_ab_testing(self) -> None:
        payload = {
            'experiment_id': f'eco-title-alignment-{int(time.time())}',
            'name': 'ECO Title Alignment rollout',
            'description': 'Automatic deployment orchestrator rollout',
            'split': {'control': 0.5, 'treatment': 0.5},
        }
        self._invoke_function('startABExperiment', payload)

    def validate_performance_targets(self) -> None:
        if not self.config.dataset_path:
            raise ValueError('dataset_path required for performance validation')
        output_path = self.config.report_path.with_suffix('.performance.json') if self.config.report_path else None
        cmd = [
            str(DEFAULT_VALIDATION_SCRIPT),
            f'--dataset={self.config.dataset_path}',
        ]
        if output_path:
            cmd.append(f'--output={output_path}')
        self._run(cmd, check=True)

    def monitor_deployment(self) -> None:
        url = self._service_url()
        if not url:
            raise RuntimeError('Failed to resolve Cloud Run service URL')
        deadline = time.time() + self.config.health_timeout
        while time.time() < deadline:
            try:
                response = requests.get(f'{url}/health', timeout=5)
                if response.ok:
                    self.report['service_url'] = url
                    self.report['health_response'] = response.json()
                    return
            except requests.RequestException:
                time.sleep(5)
        raise TimeoutError('Service health check did not succeed before timeout')

    def generate_report(self) -> None:
        self.report['completed_at'] = time.time()
        if self.config.report_path:
            self.config.report_path.write_text(json.dumps(self.report, indent=2), encoding='utf-8')
        else:
            print(json.dumps(self.report, indent=2))

    def _invoke_function(self, name: str, payload: Dict[str, any]) -> None:
        describe_cmd = [
            'gcloud', 'functions', 'describe', name,
            '--region', self.config.region,
            '--project', self.config.project_id,
            '--format=value(serviceConfig.uri)',
        ]
        completed = self._run(describe_cmd, check=True, capture_output=True)
        url = completed.stdout.strip()
        if not url:
            raise RuntimeError(f'Failed to resolve URL for function {name}')

        token_cmd = ['gcloud', 'auth', 'print-identity-token']
        token_completed = self._run(token_cmd, check=True, capture_output=True)
        token = token_completed.stdout.strip()
        if not token:
            raise RuntimeError('Failed to obtain identity token for Cloud Functions call')

        try:
            response = requests.post(
                url,
                headers={'Authorization': f'Bearer {token}'},
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f'Function {name} invocation failed: {exc}') from exc

    def _service_url(self) -> Optional[str]:
        cmd = [
            'gcloud', 'run', 'services', 'describe', self.config.service_name,
            '--platform=managed', '--region', self.config.region,
            '--project', self.config.project_id,
            '--format=value(status.url)',
        ]
        completed = self._run(cmd, capture_output=True)
        url = completed.stdout.strip()
        return url or None

    def _log_step(self, name: str, func) -> None:
        started = time.time()
        step_report = {'name': name, 'started_at': started}
        try:
            func()
            step_report['status'] = 'success'
        except Exception as exc:  # pylint: disable=broad-except
            step_report['status'] = 'failed'
            step_report['error'] = str(exc)
            self.report.setdefault('steps', []).append(step_report)
            raise
        else:
            step_report['completed_at'] = time.time()
            self.report.setdefault('steps', []).append(step_report)

    @staticmethod
    def _run(cmd, check=False, capture_output=False, env=None):
        return subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=True,
            env=env,
        )


def parse_args(argv: Optional[Sequence[str]] = None) -> OrchestratorConfig:
    parser = argparse.ArgumentParser(description='Orchestrate ECO search integration deployment')
    parser.add_argument('--project-id', required=True)
    parser.add_argument('--region', default='us-central1')
    parser.add_argument('--service-name', default='eco-cloud-run')
    parser.add_argument('--deployment-mode', choices=['canary', 'blue-green', 'rolling'], default='blue-green')
    parser.add_argument('--db-instance', required=True)
    parser.add_argument('--database-secret', required=True)
    parser.add_argument('--dataset', help='Offline dataset for performance validation')
    parser.add_argument('--report', help='Path to write orchestration report')
    parser.add_argument('--health-timeout', type=int, default=300)
    args = parser.parse_args(argv)

    report_path = Path(args.report) if args.report else None
    dataset_path = Path(args.dataset) if args.dataset else None

    return OrchestratorConfig(
        project_id=args.project_id,
        region=args.region,
        service_name=args.service_name,
        deployment_mode=args.deployment_mode,
        database_instance=args.db_instance,
        database_secret=args.database_secret,
        dataset_path=dataset_path,
        health_timeout=args.health_timeout,
        report_path=report_path,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    config = parse_args(argv)
    orchestrator = ECODeploymentOrchestrator(config)
    try:
        orchestrator.run()
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Deployment orchestration failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
