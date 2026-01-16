#!/usr/bin/env python3
"""
Build Top Brazilian Engineers Database - Master Orchestration Script

Orchestrates the full pipeline to build a comprehensive database of
top Brazilian software engineers from target companies.

Pipeline Steps:
1. Apply database migrations (alumni tracking)
2. Scrape current employees from target companies
3. Extract full profiles with work history
4. Detect and tag alumni
5. Enrich profiles with Gemini 2.5 Flash
6. Generate embeddings for semantic search

Usage:
    # Full pipeline with default budget
    python build_top_engineers_db.py run --budget 300

    # Specific phases
    python build_top_engineers_db.py migrate      # Apply migrations only
    python build_top_engineers_db.py scrape       # Scrape only
    python build_top_engineers_db.py tag-alumni   # Tag alumni only
    python build_top_engineers_db.py enrich       # Enrich only
    python build_top_engineers_db.py embeddings   # Generate embeddings only

    # Status check
    python build_top_engineers_db.py status
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / 'scripts'
DATA_DIR = REPO_ROOT / 'data' / 'sourcing'


class PipelineOrchestrator:
    """Orchestrates the full database building pipeline"""

    def __init__(self, budget: float = 300.0):
        self.budget = budget
        self.spent = 0.0
        self.stats = {
            'started_at': datetime.now().isoformat(),
            'phases_completed': [],
            'candidates_scraped': 0,
            'candidates_enriched': 0,
            'embeddings_generated': 0,
            'alumni_tagged': 0,
            'total_cost': 0.0,
        }

    def run_command(self, cmd: list, description: str) -> bool:
        """Run a command and return success status"""
        logger.info(f"🔄 {description}")
        logger.info(f"   Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            if result.returncode != 0:
                logger.error(f"   ❌ Failed: {result.stderr[:500]}")
                return False

            logger.info(f"   ✅ Success")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"   ❌ Timeout after 1 hour")
            return False
        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
            return False

    def phase_migrate(self) -> bool:
        """Phase 1: Apply database migrations"""
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 1: DATABASE MIGRATIONS")
        logger.info("=" * 60)

        migration_file = SCRIPTS_DIR / 'migrations' / '004_alumni_tracking.sql'

        if not migration_file.exists():
            logger.error(f"Migration file not found: {migration_file}")
            return False

        # Run migration using psql or Python
        cmd = [
            'python3', '-c', f'''
import psycopg2
import subprocess
from urllib.parse import quote_plus

# Get password
result = subprocess.run(
    ["gcloud", "secrets", "versions", "access", "latest",
     "--secret=db-primary-password", "--project=headhunter-ai-0088"],
    capture_output=True, text=True
)
password = result.stdout.strip()
db_url = f"postgresql://hh_app:{{quote_plus(password)}}@136.113.28.239:5432/headhunter"

conn = psycopg2.connect(db_url)
cur = conn.cursor()

# Read and execute migration
with open("{migration_file}") as f:
    sql = f.read()

cur.execute(sql)
conn.commit()
print("Migration applied successfully")
conn.close()
'''
        ]

        success = self.run_command(cmd, "Applying alumni tracking migration")

        if success:
            self.stats['phases_completed'].append('migrate')

        return success

    def phase_scrape(self, tier: str = None, max_budget: float = None) -> bool:
        """Phase 2: Scrape employees from target companies"""
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 2: SCRAPE TARGET COMPANIES")
        logger.info("=" * 60)

        budget = max_budget or (self.budget * 0.4)  # 40% of budget for scraping

        if tier:
            cmd = [
                'python3', str(SCRIPTS_DIR / 'company_employee_scraper.py'),
                'scrape-tier', '--tier', tier,
                '--budget', str(budget)
            ]
        else:
            cmd = [
                'python3', str(SCRIPTS_DIR / 'company_employee_scraper.py'),
                'scrape-all', '--budget', str(budget)
            ]

        success = self.run_command(cmd, f"Scraping companies (budget: ${budget:.2f})")

        if success:
            self.stats['phases_completed'].append('scrape')
            self.spent += budget * 0.8  # Estimate actual spend

        return success

    def phase_tag_alumni(self) -> bool:
        """Phase 3: Tag candidates with alumni affiliations"""
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 3: TAG ALUMNI")
        logger.info("=" * 60)

        cmd = [
            'python3', str(SCRIPTS_DIR / 'alumni_extractor.py'),
            'tag-existing'
        ]

        success = self.run_command(cmd, "Tagging alumni affiliations")

        if success:
            self.stats['phases_completed'].append('tag_alumni')

        return success

    def phase_enrich(self, max_cost: float = None) -> bool:
        """Phase 4: Enrich profiles with Gemini"""
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 4: ENRICH PROFILES")
        logger.info("=" * 60)

        cost_limit = max_cost or (self.budget * 0.5)  # 50% of budget for enrichment

        cmd = [
            'python3', str(SCRIPTS_DIR / 'sourcing_gemini_enrichment.py'),
            '--max-cost', str(cost_limit),
            '--delay', '3.0'
        ]

        success = self.run_command(cmd, f"Enriching profiles (budget: ${cost_limit:.2f})")

        if success:
            self.stats['phases_completed'].append('enrich')
            self.spent += cost_limit * 0.8

        return success

    def phase_embeddings(self) -> bool:
        """Phase 5: Generate embeddings"""
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 5: GENERATE EMBEDDINGS")
        logger.info("=" * 60)

        embeddings_script = SCRIPTS_DIR / 'sourcing_embeddings.py'

        if not embeddings_script.exists():
            logger.warning("Embeddings script not found, skipping")
            return True

        cmd = [
            'python3', str(embeddings_script)
        ]

        success = self.run_command(cmd, "Generating embeddings")

        if success:
            self.stats['phases_completed'].append('embeddings')

        return success

    def get_status(self) -> dict:
        """Get current database status"""
        import psycopg2
        from urllib.parse import quote_plus

        # Get password
        result = subprocess.run(
            ['gcloud', 'secrets', 'versions', 'access', 'latest',
             '--secret=db-primary-password', '--project=headhunter-ai-0088'],
            capture_output=True, text=True
        )
        password = result.stdout.strip()
        db_url = f"postgresql://hh_app:{quote_plus(password)}@136.113.28.239:5432/headhunter"

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        status = {}

        # Total candidates
        cur.execute("SELECT COUNT(*) FROM sourcing.candidates")
        status['total_candidates'] = cur.fetchone()[0]

        # Enriched
        cur.execute("SELECT COUNT(*) FROM sourcing.candidates WHERE intelligent_analysis IS NOT NULL")
        status['enriched'] = cur.fetchone()[0]

        # With experience data
        cur.execute("SELECT COUNT(DISTINCT candidate_id) FROM sourcing.experience")
        status['with_experience'] = cur.fetchone()[0]

        # Alumni (if column exists)
        try:
            cur.execute("SELECT COUNT(*) FROM sourcing.candidates WHERE is_target_company_alumni = TRUE")
            status['target_alumni'] = cur.fetchone()[0]
        except:
            status['target_alumni'] = 'N/A (migration needed)'

        # Embeddings
        try:
            cur.execute("SELECT COUNT(*) FROM sourcing.embeddings")
            status['embeddings'] = cur.fetchone()[0]
        except:
            status['embeddings'] = 0

        conn.close()
        return status

    def run_full_pipeline(self) -> bool:
        """Run the complete pipeline"""
        logger.info("\n" + "=" * 70)
        logger.info("🚀 BUILDING TOP BRAZILIAN ENGINEERS DATABASE")
        logger.info("=" * 70)
        logger.info(f"Budget: ${self.budget:.2f}")
        logger.info(f"Started: {datetime.now().isoformat()}")

        # Phase 1: Migrate
        if not self.phase_migrate():
            logger.warning("Migration failed, continuing anyway...")

        # Phase 2: Scrape (40% of budget)
        scrape_budget = self.budget * 0.4
        self.phase_scrape(max_budget=scrape_budget)

        # Phase 3: Tag alumni (free)
        self.phase_tag_alumni()

        # Phase 4: Enrich (50% of budget)
        enrich_budget = self.budget * 0.5
        self.phase_enrich(max_cost=enrich_budget)

        # Phase 5: Embeddings (free/minimal)
        self.phase_embeddings()

        # Final status
        self.stats['completed_at'] = datetime.now().isoformat()
        self.stats['total_cost'] = self.spent

        self._print_summary()

        # Save stats
        stats_file = DATA_DIR / f"pipeline_stats_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)

        return True

    def _print_summary(self):
        """Print pipeline summary"""
        status = self.get_status()

        print("\n" + "=" * 70)
        print("📊 PIPELINE COMPLETE")
        print("=" * 70)
        print(f"Phases completed: {', '.join(self.stats['phases_completed'])}")
        print(f"Estimated cost: ${self.spent:.2f}")
        print()
        print("Database Status:")
        print(f"  Total candidates:     {status['total_candidates']:,}")
        print(f"  Enriched:             {status['enriched']:,}")
        print(f"  With experience:      {status['with_experience']:,}")
        print(f"  Target company alumni: {status['target_alumni']}")
        print(f"  Embeddings:           {status['embeddings']:,}")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Build Top Brazilian Engineers Database",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Command')

    # Full run
    run_parser = subparsers.add_parser('run', help='Run full pipeline')
    run_parser.add_argument('--budget', type=float, default=300.0, help='Total budget in USD')

    # Individual phases
    subparsers.add_parser('migrate', help='Apply database migrations')
    subparsers.add_parser('tag-alumni', help='Tag alumni affiliations')

    scrape_parser = subparsers.add_parser('scrape', help='Scrape target companies')
    scrape_parser.add_argument('--tier', help='Specific tier to scrape')
    scrape_parser.add_argument('--budget', type=float, default=100.0)

    enrich_parser = subparsers.add_parser('enrich', help='Enrich profiles')
    enrich_parser.add_argument('--max-cost', type=float, default=50.0)

    subparsers.add_parser('embeddings', help='Generate embeddings')
    subparsers.add_parser('status', help='Show current status')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    orchestrator = PipelineOrchestrator(
        budget=getattr(args, 'budget', 300.0)
    )

    if args.command == 'run':
        orchestrator.run_full_pipeline()

    elif args.command == 'migrate':
        orchestrator.phase_migrate()

    elif args.command == 'scrape':
        orchestrator.phase_scrape(
            tier=getattr(args, 'tier', None),
            max_budget=args.budget
        )

    elif args.command == 'tag-alumni':
        orchestrator.phase_tag_alumni()

    elif args.command == 'enrich':
        orchestrator.phase_enrich(max_cost=args.max_cost)

    elif args.command == 'embeddings':
        orchestrator.phase_embeddings()

    elif args.command == 'status':
        status = orchestrator.get_status()
        print("\n" + "=" * 60)
        print("DATABASE STATUS")
        print("=" * 60)
        for key, value in status.items():
            print(f"  {key:25} {value:>10}")
        print("=" * 60)


if __name__ == '__main__':
    main()
