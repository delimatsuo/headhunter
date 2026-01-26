#!/usr/bin/env python3
"""
Bias Metrics Worker for BIAS-03/BIAS-04

Computes selection rates and impact ratios using Fairlearn.
Designed to run periodically (cron/Cloud Scheduler) to update
bias metrics in the admin dashboard.

Usage:
    python bias_metrics_worker.py --days 30 --dimension company_tier
    python bias_metrics_worker.py --days 7 --all-dimensions
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import psycopg2
import numpy as np
import pandas as pd
from scipy import stats

# Fairlearn imports
from fairlearn.metrics import (
    MetricFrame,
    selection_rate,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bias_metrics_worker')

# Minimum sample size for statistical validity
MIN_SAMPLE_SIZE = 20

# Four-fifths rule threshold
ADVERSE_IMPACT_THRESHOLD = 0.8


def get_db_connection():
    """Get PostgreSQL connection from environment."""
    return psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST', 'localhost'),
        port=os.environ.get('POSTGRES_PORT', '5432'),
        database=os.environ.get('POSTGRES_DB', 'headhunter'),
        user=os.environ.get('POSTGRES_USER', 'headhunter'),
        password=os.environ.get('POSTGRES_PASSWORD', 'headhunter'),
        sslmode=os.environ.get('POSTGRES_SSLMODE', 'prefer'),
    )


def fetch_selection_events(
    conn,
    start_date: datetime,
    end_date: datetime,
    tenant_id: Optional[str] = None
) -> pd.DataFrame:
    """
    Fetch selection events from PostgreSQL for the given date range.

    Returns DataFrame with columns:
    - candidate_id, event_type, company_tier, experience_band, specialty
    """
    query = """
        SELECT
            candidate_id,
            event_type,
            company_tier,
            experience_band,
            specialty,
            search_id,
            timestamp
        FROM selection_events
        WHERE timestamp >= %s AND timestamp < %s
    """
    params = [start_date, end_date]

    if tenant_id:
        query += " AND tenant_id = %s"
        params.append(tenant_id)

    query += " ORDER BY timestamp"

    df = pd.read_sql(query, conn, params=params)
    logger.info(f"Fetched {len(df)} selection events")
    return df


def compute_selection_rates(
    events: pd.DataFrame,
    dimension: str,
    baseline_event: str = 'shown',
    selection_event: str = 'shortlisted'
) -> Dict[str, Any]:
    """
    Compute selection rates for a given dimension using Fairlearn.

    Args:
        events: DataFrame of selection events
        dimension: Column to group by (company_tier, experience_band, specialty)
        baseline_event: Event type for denominator (who was shown)
        selection_event: Event type for numerator (who was selected)

    Returns:
        Dict with selection rates, impact ratios, and warnings
    """
    # Get unique candidates by event type
    shown = events[events['event_type'] == baseline_event]['candidate_id'].unique()
    selected = events[events['event_type'] == selection_event]['candidate_id'].unique()

    if len(shown) == 0:
        logger.warning("No 'shown' events in dataset")
        return {'error': 'No baseline events'}

    # Build dataset for Fairlearn
    # y_true = was the candidate selected?
    # y_pred = was the candidate shown? (always 1 for our analysis)
    # sensitive_features = dimension value

    # Get dimension values for shown candidates
    shown_candidates = events[
        (events['event_type'] == baseline_event)
    ].drop_duplicates(subset=['candidate_id'])

    # Mark which were selected
    shown_candidates = shown_candidates.copy()
    shown_candidates['selected'] = shown_candidates['candidate_id'].isin(selected).astype(int)

    # For Fairlearn: y_true = selected, y_pred = 1 (shown)
    y_true = shown_candidates['selected'].values
    y_pred = np.ones(len(shown_candidates))
    sensitive_features = shown_candidates[dimension].values

    # Compute metrics with MetricFrame
    mf = MetricFrame(
        metrics={'selection_rate': selection_rate},
        y_true=y_true,
        y_pred=y_pred,
        sensitive_features=sensitive_features
    )

    # Get per-group metrics
    group_rates = mf.by_group['selection_rate'].to_dict()
    overall_rate = mf.overall['selection_rate']

    # Compute impact ratios (four-fifths rule)
    max_rate = max(group_rates.values()) if group_rates else 0
    impact_ratios = {}
    adverse_impact_groups = []

    for group, rate in group_rates.items():
        ratio = rate / max_rate if max_rate > 0 else 0
        impact_ratios[group] = ratio

        if ratio < ADVERSE_IMPACT_THRESHOLD:
            adverse_impact_groups.append(group)

    # Get sample sizes per group
    sample_sizes = shown_candidates.groupby(dimension).size().to_dict()

    # Flag groups with insufficient samples
    low_sample_groups = [
        group for group, size in sample_sizes.items()
        if size < MIN_SAMPLE_SIZE
    ]

    # Statistical significance testing for small samples
    significance_tests = {}
    for group in group_rates.keys():
        group_data = shown_candidates[shown_candidates[dimension] == group]
        if len(group_data) >= MIN_SAMPLE_SIZE:
            # Chi-square test vs overall rate
            observed = [group_data['selected'].sum(), len(group_data) - group_data['selected'].sum()]
            expected_rate = overall_rate
            expected = [len(group_data) * expected_rate, len(group_data) * (1 - expected_rate)]

            if min(expected) >= 5:  # Chi-square validity
                chi2, p_value = stats.chisquare(observed, expected)
                significance_tests[group] = {
                    'chi2': float(chi2),
                    'p_value': float(p_value),
                    'significant': p_value < 0.05
                }
            else:
                # Use Fisher's exact test for small expected counts
                # Construct 2x2 table: group vs rest
                rest_selected = y_true.sum() - group_data['selected'].sum()
                rest_not_selected = len(y_true) - y_true.sum() - (len(group_data) - group_data['selected'].sum())
                table = [
                    [int(group_data['selected'].sum()), int(len(group_data) - group_data['selected'].sum())],
                    [int(rest_selected), int(rest_not_selected)]
                ]
                _, p_value = stats.fisher_exact(table)
                significance_tests[group] = {
                    'test': 'fisher_exact',
                    'p_value': float(p_value),
                    'significant': p_value < 0.05
                }

    return {
        'dimension': dimension,
        'period': {
            'start': events['timestamp'].min().isoformat() if len(events) > 0 else None,
            'end': events['timestamp'].max().isoformat() if len(events) > 0 else None,
        },
        'overall_rate': float(overall_rate),
        'selection_rates': {k: float(v) for k, v in group_rates.items()},
        'impact_ratios': {k: float(v) for k, v in impact_ratios.items()},
        'sample_sizes': sample_sizes,
        'demographic_parity_ratio': float(mf.ratio()['selection_rate']) if len(group_rates) > 1 else None,
        'demographic_parity_difference': float(mf.difference()['selection_rate']) if len(group_rates) > 1 else None,
        'adverse_impact_detected': len(adverse_impact_groups) > 0,
        'adverse_impact_groups': adverse_impact_groups,
        'low_sample_groups': low_sample_groups,
        'significance_tests': significance_tests,
        'warnings': _generate_warnings(
            adverse_impact_groups,
            low_sample_groups,
            significance_tests
        )
    }


def _generate_warnings(
    adverse_impact_groups: List[str],
    low_sample_groups: List[str],
    significance_tests: Dict[str, Dict]
) -> List[str]:
    """Generate human-readable warnings for the dashboard."""
    warnings = []

    if adverse_impact_groups:
        groups_str = ', '.join(str(g) for g in adverse_impact_groups)
        warnings.append(
            f"Potential adverse impact detected for: {groups_str}. "
            f"These groups have selection rates below 80% of the highest group."
        )

    if low_sample_groups:
        groups_str = ', '.join(str(g) for g in low_sample_groups)
        warnings.append(
            f"Low sample size (<{MIN_SAMPLE_SIZE}) for: {groups_str}. "
            f"Impact ratios may not be statistically meaningful."
        )

    # Check for statistically significant differences
    significant_groups = [
        group for group, test in significance_tests.items()
        if test.get('significant', False)
    ]
    if significant_groups:
        groups_str = ', '.join(str(g) for g in significant_groups)
        warnings.append(
            f"Statistically significant selection rate differences found for: {groups_str}."
        )

    return warnings


def compute_all_dimensions(
    events: pd.DataFrame,
    baseline_event: str = 'shown',
    selection_event: str = 'shortlisted'
) -> Dict[str, Any]:
    """Compute metrics for all three dimensions."""
    results = {}

    for dimension in ['company_tier', 'experience_band', 'specialty']:
        results[dimension] = compute_selection_rates(
            events, dimension, baseline_event, selection_event
        )

    # Compute aggregate warnings
    all_warnings = []
    for dim_result in results.values():
        if 'warnings' in dim_result:
            all_warnings.extend(dim_result['warnings'])

    return {
        'computed_at': datetime.utcnow().isoformat(),
        'dimensions': results,
        'all_warnings': all_warnings,
        'any_adverse_impact': any(
            r.get('adverse_impact_detected', False)
            for r in results.values()
        )
    }


def save_metrics_to_db(conn, metrics: Dict[str, Any], tenant_id: str) -> None:
    """Save computed metrics to PostgreSQL for dashboard consumption."""
    query = """
        INSERT INTO bias_metrics (
            tenant_id, computed_at, metrics_json
        ) VALUES (%s, %s, %s)
    """

    with conn.cursor() as cur:
        cur.execute(query, [
            tenant_id,
            datetime.utcnow(),
            json.dumps(metrics)
        ])
    conn.commit()
    logger.info(f"Saved metrics for tenant {tenant_id}")


def main():
    parser = argparse.ArgumentParser(description='Compute bias metrics')
    parser.add_argument('--days', type=int, default=30, help='Days to look back')
    parser.add_argument('--dimension', type=str, help='Specific dimension to compute')
    parser.add_argument('--all-dimensions', action='store_true', help='Compute all dimensions')
    parser.add_argument('--tenant-id', type=str, help='Filter by tenant')
    parser.add_argument('--output', type=str, help='Output file (JSON)')
    parser.add_argument('--save-to-db', action='store_true', help='Save results to database')

    args = parser.parse_args()

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=args.days)

    logger.info(f"Computing bias metrics for {start_date} to {end_date}")

    conn = get_db_connection()

    try:
        events = fetch_selection_events(conn, start_date, end_date, args.tenant_id)

        if len(events) == 0:
            logger.warning("No selection events found for the period")
            print(json.dumps({'error': 'No data', 'period': {'days': args.days}}))
            return

        if args.all_dimensions:
            results = compute_all_dimensions(events)
        elif args.dimension:
            results = compute_selection_rates(events, args.dimension)
        else:
            results = compute_all_dimensions(events)

        # Output results
        output_json = json.dumps(results, indent=2, default=str)
        print(output_json)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(output_json)
            logger.info(f"Results saved to {args.output}")

        if args.save_to_db:
            tenant_id = args.tenant_id or 'default'
            save_metrics_to_db(conn, results, tenant_id)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
