#!/usr/bin/env python3
"""
Acquisition & Enrichment Monitor

Automatically checks status every 15 minutes without manual triggering.
Displays progress for:
- Database candidate counts
- Enrichment status (Gemini 2.5 Flash)
- Company scraping progress
- Alumni tagging status

Usage:
    # Run monitor (checks every 15 minutes)
    python monitor_acquisition.py

    # Single status check
    python monitor_acquisition.py --once

    # Custom interval (minutes)
    python monitor_acquisition.py --interval 5
"""

import os
import sys
import json
import time
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from pathlib import Path
import subprocess
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / 'data' / 'sourcing'


class AcquisitionMonitor:
    """Monitor acquisition and enrichment progress"""

    def __init__(self):
        self.db_url = self._build_db_url()
        self._conn = None

    def _build_db_url(self) -> str:
        """Build database URL"""
        if os.getenv('DATABASE_URL'):
            return os.getenv('DATABASE_URL')

        result = subprocess.run(
            ['gcloud', 'secrets', 'versions', 'access', 'latest',
             '--secret=db-primary-password', '--project=headhunter-ai-0088'],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise ValueError(f"Failed to get DB password: {result.stderr}")

        password = result.stdout.strip()
        return f"postgresql://hh_app:{quote_plus(password)}@136.113.28.239:5432/headhunter"

    @property
    def conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.db_url, connect_timeout=30)
            self._conn.autocommit = True  # For read-only queries
        return self._conn

    def _reset_conn(self):
        """Reset connection on error"""
        if self._conn and not self._conn.closed:
            try:
                self._conn.rollback()
            except:
                pass
            try:
                self._conn.close()
            except:
                pass
        self._conn = None

    def get_status(self) -> dict:
        """Get comprehensive acquisition status"""
        try:
            cur = self.conn.cursor(cursor_factory=RealDictCursor)
        except Exception:
            self._reset_conn()
            cur = self.conn.cursor(cursor_factory=RealDictCursor)

        status = {'timestamp': datetime.now().isoformat()}

        # Total candidates
        cur.execute("SELECT COUNT(*) as count FROM sourcing.candidates")
        status['total_candidates'] = cur.fetchone()['count']

        # Enriched (has intelligent_analysis)
        cur.execute("""
            SELECT COUNT(*) as count
            FROM sourcing.candidates
            WHERE intelligent_analysis IS NOT NULL
        """)
        status['enriched'] = cur.fetchone()['count']

        # Pending enrichment
        status['pending_enrichment'] = status['total_candidates'] - status['enriched']

        # Enrichment rate
        if status['total_candidates'] > 0:
            status['enrichment_rate'] = round(
                status['enriched'] / status['total_candidates'] * 100, 1
            )
        else:
            status['enrichment_rate'] = 0

        # With experience data (work history)
        cur.execute("""
            SELECT COUNT(DISTINCT candidate_id) as count
            FROM sourcing.experience
        """)
        status['with_experience'] = cur.fetchone()['count']

        # Total experience records
        cur.execute("SELECT COUNT(*) as count FROM sourcing.experience")
        status['experience_records'] = cur.fetchone()['count']

        # Alumni tracking columns (if migration applied)
        try:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE is_target_company_alumni = TRUE) as target_alumni,
                    COUNT(*) FILTER (WHERE is_target_company_current = TRUE) as target_current,
                    COUNT(*) FILTER (WHERE company_affiliations IS NOT NULL) as with_affiliations
                FROM sourcing.candidates
            """)
            row = cur.fetchone()
            status['target_company_alumni'] = row['target_alumni']
            status['target_company_current'] = row['target_current']
            status['with_affiliations'] = row['with_affiliations']
        except Exception:
            status['target_company_alumni'] = 'N/A (migration needed)'
            status['target_company_current'] = 'N/A'
            status['with_affiliations'] = 'N/A'

        # By source (company scrapes)
        cur.execute("""
            SELECT source, COUNT(*) as count
            FROM sourcing.candidates
            WHERE source IS NOT NULL
            GROUP BY source
            ORDER BY count DESC
            LIMIT 15
        """)
        status['by_source'] = {row['source']: row['count'] for row in cur.fetchall()}

        # Embeddings count
        try:
            cur.execute("SELECT COUNT(*) as count FROM sourcing.embeddings")
            status['embeddings'] = cur.fetchone()['count']
        except Exception:
            status['embeddings'] = 0

        # Recent additions (last 24 hours)
        cur.execute("""
            SELECT COUNT(*) as count
            FROM sourcing.candidates
            WHERE scraped_at > NOW() - INTERVAL '24 hours'
        """)
        status['added_last_24h'] = cur.fetchone()['count']

        # Recent enrichments (last 24 hours)
        cur.execute("""
            SELECT COUNT(*) as count
            FROM sourcing.candidates
            WHERE enriched_at > NOW() - INTERVAL '24 hours'
        """)
        status['enriched_last_24h'] = cur.fetchone()['count']

        return status

    def print_status(self, status: dict):
        """Print status in a formatted way"""
        print("\n" + "=" * 70)
        print(f"📊 ACQUISITION & ENRICHMENT STATUS")
        print(f"   {status['timestamp']}")
        print("=" * 70)

        print("\n📦 DATABASE OVERVIEW")
        print("-" * 50)
        print(f"   Total candidates:        {status['total_candidates']:,}")
        print(f"   Enriched:                {status['enriched']:,} ({status['enrichment_rate']}%)")
        print(f"   Pending enrichment:      {status['pending_enrichment']:,}")
        print(f"   With experience data:    {status['with_experience']:,}")
        print(f"   Experience records:      {status['experience_records']:,}")

        print("\n🎯 TARGET COMPANY TRACKING")
        print("-" * 50)
        print(f"   Alumni (former):         {status.get('target_company_alumni', 'N/A')}")
        print(f"   Current employees:       {status.get('target_company_current', 'N/A')}")
        print(f"   With affiliations:       {status.get('with_affiliations', 'N/A')}")

        print("\n📈 RECENT ACTIVITY (24h)")
        print("-" * 50)
        print(f"   Candidates added:        {status.get('added_last_24h', 0):,}")
        print(f"   Candidates enriched:     {status.get('enriched_last_24h', 0):,}")

        print("\n🔍 SEARCH READINESS")
        print("-" * 50)
        print(f"   Embeddings generated:    {status.get('embeddings', 0):,}")

        if status.get('by_source'):
            print("\n🏢 BY SOURCE (Top 10)")
            print("-" * 50)
            for source, count in list(status['by_source'].items())[:10]:
                source_display = source[:40] if len(source) > 40 else source
                print(f"   {source_display:40} {count:>6,}")

        print("\n" + "=" * 70)

        # Progress bar for enrichment
        if status['total_candidates'] > 0:
            pct = status['enriched'] / status['total_candidates']
            bar_length = 40
            filled = int(bar_length * pct)
            bar = '█' * filled + '░' * (bar_length - filled)
            print(f"\n   Enrichment: [{bar}] {pct*100:.1f}%")

        print()

    def save_status(self, status: dict, output_dir: Path = None):
        """Save status to JSON file"""
        output_dir = output_dir or DATA_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"status_{datetime.now():%Y%m%d_%H%M%S}.json"
        filepath = output_dir / filename

        with open(filepath, 'w') as f:
            json.dump(status, f, indent=2, default=str)

        return filepath

    def run_monitor(self, interval_minutes: int = 15, once: bool = False):
        """Run monitoring loop"""
        print(f"🔄 Starting acquisition monitor (interval: {interval_minutes} minutes)")
        print("   Press Ctrl+C to stop")

        try:
            while True:
                status = self.get_status()
                self.print_status(status)

                if once:
                    break

                # Wait for next check
                print(f"\n⏰ Next check in {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            print("\n\n👋 Monitor stopped by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Monitor acquisition and enrichment progress",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=15,
        help='Check interval in minutes (default: 15)'
    )

    parser.add_argument(
        '--once', '-1',
        action='store_true',
        help='Run single check and exit'
    )

    parser.add_argument(
        '--save', '-s',
        action='store_true',
        help='Save status to JSON file'
    )

    args = parser.parse_args()

    monitor = AcquisitionMonitor()

    if args.save:
        status = monitor.get_status()
        filepath = monitor.save_status(status)
        print(f"Status saved to: {filepath}")

    monitor.run_monitor(
        interval_minutes=args.interval,
        once=args.once
    )


if __name__ == '__main__':
    main()
