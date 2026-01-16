#!/usr/bin/env python3
"""
Alumni Extractor for Ella Sourcing

Identifies engineers who previously worked at target companies (alumni)
by analyzing work history data already stored in the database.

Key insight: LinkedIn doesn't support "past company" search directly,
but we can extract alumni by filtering work history after extraction.

Usage:
    # Tag existing candidates with alumni affiliations
    python alumni_extractor.py tag-existing

    # Show alumni statistics
    python alumni_extractor.py stats

    # List alumni from a specific company
    python alumni_extractor.py list --company "Nubank"

    # Export alumni to CSV
    python alumni_extractor.py export --output alumni.csv
"""

import os
import json
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Optional, Set
from datetime import datetime
from pathlib import Path
import logging
import subprocess
import csv
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / 'data' / 'sourcing'
TARGET_COMPANIES_FILE = DATA_DIR / 'target_companies.json'


# =============================================================================
# TARGET COMPANY NAMES FOR ALUMNI DETECTION
# =============================================================================

def load_target_company_names() -> List[str]:
    """Load all target company names from the JSON file"""
    if not TARGET_COMPANIES_FILE.exists():
        logger.warning(f"Target companies file not found: {TARGET_COMPANIES_FILE}")
        return []

    with open(TARGET_COMPANIES_FILE) as f:
        data = json.load(f)

    company_names = []
    for tier_data in data.get('tiers', {}).values():
        for company in tier_data.get('companies', []):
            name = company.get('name')
            if name:
                company_names.append(name)

    return company_names


# Build SQL ILIKE patterns for company matching
def build_company_patterns(company_names: List[str]) -> List[str]:
    """Build ILIKE patterns for fuzzy company name matching"""
    patterns = []
    for name in company_names:
        # Handle variations: "Nubank" matches "Nubank", "Nu Bank", "nubank", etc.
        base_name = name.lower().strip()

        # Remove common suffixes for broader matching
        for suffix in [' (tech)', ' brasil', ' brazil', ' pagamentos', ' bank', ' (banco)']:
            base_name = base_name.replace(suffix, '')

        patterns.append(f'%{base_name}%')

    return patterns


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

class DatabaseManager:
    """Database operations for alumni extraction"""

    def __init__(self, db_url: str = None):
        self.db_url = db_url or self._build_db_url()
        self._conn = None

    def _build_db_url(self) -> str:
        """Build database URL from environment or Secret Manager"""
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
        return self._conn

    def close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()


# =============================================================================
# ALUMNI EXTRACTION LOGIC
# =============================================================================

class AlumniExtractor:
    """Extract and tag alumni from existing candidate data"""

    def __init__(self):
        self.db = DatabaseManager()
        self.target_companies = load_target_company_names()
        self.company_patterns = build_company_patterns(self.target_companies)

    def find_alumni(self, company_name: str = None) -> List[Dict]:
        """
        Find candidates who previously worked at target companies.

        Args:
            company_name: Specific company to search for (optional)

        Returns:
            List of alumni candidate records
        """
        cur = self.db.conn.cursor(cursor_factory=RealDictCursor)

        if company_name:
            # Search for specific company
            pattern = f'%{company_name.lower()}%'
            cur.execute("""
                SELECT DISTINCT
                    c.id,
                    c.first_name,
                    c.last_name,
                    c.headline,
                    c.location,
                    c.linkedin_url,
                    e.company_name AS alumni_company,
                    e.title AS alumni_title,
                    e.start_date,
                    e.end_date
                FROM sourcing.candidates c
                JOIN sourcing.experience e ON c.id = e.candidate_id
                WHERE e.is_current = FALSE
                  AND LOWER(e.company_name) LIKE %s
                ORDER BY c.id
            """, (pattern,))
        else:
            # Search for all target companies
            cur.execute("""
                SELECT DISTINCT
                    c.id,
                    c.first_name,
                    c.last_name,
                    c.headline,
                    c.location,
                    c.linkedin_url,
                    e.company_name AS alumni_company,
                    e.title AS alumni_title,
                    e.start_date,
                    e.end_date
                FROM sourcing.candidates c
                JOIN sourcing.experience e ON c.id = e.candidate_id
                WHERE e.is_current = FALSE
                  AND LOWER(e.company_name) SIMILAR TO %s
                ORDER BY c.id
            """, ('|'.join(f'%({p.strip("%").lower()})%' for p in self.company_patterns[:50]),))

        return [dict(row) for row in cur.fetchall()]

    def find_current_employees(self, company_name: str = None) -> List[Dict]:
        """Find candidates currently working at target companies"""
        cur = self.db.conn.cursor(cursor_factory=RealDictCursor)

        if company_name:
            pattern = f'%{company_name.lower()}%'
            cur.execute("""
                SELECT DISTINCT
                    c.id,
                    c.first_name,
                    c.last_name,
                    c.headline,
                    c.location,
                    c.linkedin_url,
                    e.company_name AS current_company,
                    e.title AS current_title
                FROM sourcing.candidates c
                JOIN sourcing.experience e ON c.id = e.candidate_id
                WHERE e.is_current = TRUE
                  AND LOWER(e.company_name) LIKE %s
                ORDER BY c.id
            """, (pattern,))
        else:
            cur.execute("""
                SELECT DISTINCT
                    c.id,
                    c.first_name,
                    c.last_name,
                    c.headline,
                    c.location,
                    c.linkedin_url,
                    e.company_name AS current_company,
                    e.title AS current_title
                FROM sourcing.candidates c
                JOIN sourcing.experience e ON c.id = e.candidate_id
                WHERE e.is_current = TRUE
                ORDER BY c.id
            """)

        return [dict(row) for row in cur.fetchall()]

    def get_company_affiliations(self, candidate_id: int) -> Dict:
        """Get all company affiliations for a candidate"""
        cur = self.db.conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT company_name, title, is_current, start_date, end_date
            FROM sourcing.experience
            WHERE candidate_id = %s
            ORDER BY is_current DESC, end_date DESC NULLS FIRST
        """, (candidate_id,))

        affiliations = {
            'current': [],
            'past': []
        }

        for row in cur.fetchall():
            company_info = {
                'company': row['company_name'],
                'title': row['title'],
                'start_date': str(row['start_date']) if row['start_date'] else None,
                'end_date': str(row['end_date']) if row['end_date'] else None,
            }

            # Check if it's a target company
            is_target = any(
                p.strip('%').lower() in (row['company_name'] or '').lower()
                for p in self.company_patterns
            )
            company_info['is_target_company'] = is_target

            if row['is_current']:
                affiliations['current'].append(company_info)
            else:
                affiliations['past'].append(company_info)

        return affiliations

    def tag_alumni_in_database(self) -> int:
        """
        Tag all candidates with their company affiliations.
        Updates the company_affiliations JSONB field.

        Returns:
            Number of candidates tagged
        """
        cur = self.db.conn.cursor(cursor_factory=RealDictCursor)

        # Get all candidates with experience data
        cur.execute("""
            SELECT DISTINCT c.id
            FROM sourcing.candidates c
            JOIN sourcing.experience e ON c.id = e.candidate_id
        """)

        candidate_ids = [row['id'] for row in cur.fetchall()]
        logger.info(f"Found {len(candidate_ids)} candidates with experience data")

        tagged = 0
        target_alumni_count = 0

        for cid in candidate_ids:
            affiliations = self.get_company_affiliations(cid)

            # Check if alumni of any target company
            is_target_alumni = any(
                c.get('is_target_company') for c in affiliations['past']
            )

            # Get list of target companies worked at
            target_companies_worked = list(set(
                c['company'] for c in affiliations['past']
                if c.get('is_target_company')
            ))

            if is_target_alumni:
                target_alumni_count += 1

            # Update candidate record
            try:
                cur.execute("""
                    UPDATE sourcing.candidates
                    SET company_affiliations = %s
                    WHERE id = %s
                """, (
                    psycopg2.extras.Json(affiliations),
                    cid
                ))
                tagged += 1

                if tagged % 100 == 0:
                    logger.info(f"Tagged {tagged}/{len(candidate_ids)} candidates...")
                    self.db.conn.commit()

            except Exception as e:
                logger.warning(f"Error tagging candidate {cid}: {e}")

        self.db.conn.commit()
        logger.info(f"✅ Tagged {tagged} candidates ({target_alumni_count} are target company alumni)")

        return tagged

    def get_statistics(self) -> Dict:
        """Get alumni statistics"""
        cur = self.db.conn.cursor(cursor_factory=RealDictCursor)

        stats = {}

        # Total candidates
        cur.execute("SELECT COUNT(*) as count FROM sourcing.candidates")
        stats['total_candidates'] = cur.fetchone()['count']

        # Candidates with experience data
        cur.execute("""
            SELECT COUNT(DISTINCT candidate_id) as count
            FROM sourcing.experience
        """)
        stats['candidates_with_experience'] = cur.fetchone()['count']

        # Total experience records
        cur.execute("SELECT COUNT(*) as count FROM sourcing.experience")
        stats['total_experience_records'] = cur.fetchone()['count']

        # Alumni by company (top 20)
        cur.execute("""
            SELECT
                e.company_name,
                COUNT(DISTINCT e.candidate_id) as alumni_count
            FROM sourcing.experience e
            WHERE e.is_current = FALSE
              AND e.company_name IS NOT NULL
            GROUP BY e.company_name
            ORDER BY alumni_count DESC
            LIMIT 20
        """)
        stats['top_alumni_sources'] = [
            {'company': row['company_name'], 'count': row['alumni_count']}
            for row in cur.fetchall()
        ]

        # Target company alumni counts
        target_alumni = []
        for company in self.target_companies[:30]:  # Top 30 target companies
            pattern = f'%{company.lower()}%'
            cur.execute("""
                SELECT COUNT(DISTINCT candidate_id) as count
                FROM sourcing.experience
                WHERE is_current = FALSE
                  AND LOWER(company_name) LIKE %s
            """, (pattern,))
            count = cur.fetchone()['count']
            if count > 0:
                target_alumni.append({'company': company, 'alumni_count': count})

        stats['target_company_alumni'] = sorted(
            target_alumni, key=lambda x: x['alumni_count'], reverse=True
        )

        return stats

    def export_alumni_csv(self, output_path: str, company_name: str = None):
        """Export alumni to CSV file"""
        alumni = self.find_alumni(company_name)

        if not alumni:
            logger.warning("No alumni found to export")
            return

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'id', 'first_name', 'last_name', 'headline', 'location',
                'linkedin_url', 'alumni_company', 'alumni_title',
                'start_date', 'end_date'
            ])
            writer.writeheader()
            writer.writerows(alumni)

        logger.info(f"✅ Exported {len(alumni)} alumni to {output_path}")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Extract and tag alumni from existing candidate data",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Tag existing candidates
    subparsers.add_parser('tag-existing', help='Tag all candidates with company affiliations')

    # Show statistics
    subparsers.add_parser('stats', help='Show alumni statistics')

    # List alumni
    list_parser = subparsers.add_parser('list', help='List alumni from a company')
    list_parser.add_argument('--company', help='Company name to search')
    list_parser.add_argument('--limit', type=int, default=50, help='Max results')

    # Export to CSV
    export_parser = subparsers.add_parser('export', help='Export alumni to CSV')
    export_parser.add_argument('--output', default='alumni.csv', help='Output file')
    export_parser.add_argument('--company', help='Filter by company')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    extractor = AlumniExtractor()

    if args.command == 'tag-existing':
        print("\n" + "=" * 60)
        print("TAGGING CANDIDATES WITH COMPANY AFFILIATIONS")
        print("=" * 60)
        tagged = extractor.tag_alumni_in_database()
        print(f"\n✅ Tagged {tagged} candidates")

    elif args.command == 'stats':
        print("\n" + "=" * 60)
        print("ALUMNI STATISTICS")
        print("=" * 60)

        stats = extractor.get_statistics()

        print(f"\nTotal candidates: {stats['total_candidates']:,}")
        print(f"With experience data: {stats['candidates_with_experience']:,}")
        print(f"Total experience records: {stats['total_experience_records']:,}")

        print("\n📊 Top Alumni Sources (all companies):")
        for item in stats['top_alumni_sources'][:10]:
            print(f"   {item['company']:40} {item['count']:>5} alumni")

        print("\n🎯 Target Company Alumni:")
        for item in stats['target_company_alumni'][:15]:
            print(f"   {item['company']:40} {item['alumni_count']:>5} alumni")

    elif args.command == 'list':
        print("\n" + "=" * 60)
        print(f"ALUMNI LIST" + (f" - {args.company}" if args.company else ""))
        print("=" * 60)

        alumni = extractor.find_alumni(args.company)[:args.limit]

        if not alumni:
            print("No alumni found")
            return

        print(f"\nFound {len(alumni)} alumni:\n")
        for a in alumni:
            name = f"{a['first_name'] or ''} {a['last_name'] or ''}".strip()
            print(f"• {name}")
            print(f"  {a['alumni_title']} @ {a['alumni_company']}")
            print(f"  Current: {a['headline']}")
            print(f"  LinkedIn: {a['linkedin_url']}")
            print()

    elif args.command == 'export':
        extractor.export_alumni_csv(args.output, args.company)


if __name__ == '__main__':
    main()
