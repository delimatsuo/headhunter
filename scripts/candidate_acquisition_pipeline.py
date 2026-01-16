#!/usr/bin/env python3
"""
Robust Candidate Acquisition Pipeline for Ella Sourcing

This pipeline implements a cost-optimized, deduplication-aware system for
acquiring LinkedIn profiles at scale.

Architecture:
    Discovery (cheap) → Dedup → Prioritize → Extract (expensive) → Store → Enrich

Key Features:
- Two-phase approach: cheap discovery, selective extraction
- Persistent URL tracking prevents re-discovery costs
- Priority scoring for high-value profile extraction
- Campaign tracking for cost control
- Geographic and query diversity for coverage

Usage:
    # Discover profiles (cheap, broad)
    python candidate_acquisition_pipeline.py discover --location "Rio de Janeiro, Brazil" --max 1000

    # Extract high-priority profiles (expensive, selective)
    python candidate_acquisition_pipeline.py extract --limit 500 --min-priority 60

    # Full campaign (discover + extract)
    python candidate_acquisition_pipeline.py campaign --name "rio-jan-2026" --budget 50

    # Check status
    python candidate_acquisition_pipeline.py status
"""

import os
import json
import argparse
import psycopg2
from psycopg2.extras import execute_values, Json
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import logging
import subprocess
import re
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
DATA_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Search configurations for comprehensive coverage
SEARCH_CONFIGS = {
    # Geographic expansion - major tech hubs
    'geo_tier1': {
        'locations': [
            'São Paulo, Brazil',
            'Rio de Janeiro, Brazil',
            'Belo Horizonte, Brazil',
            'Curitiba, Brazil',
            'Porto Alegre, Brazil',
        ],
        'query': 'Software Engineer OR Desenvolvedor OR Programador',
        'priority_boost': 10,
    },
    'geo_tier2': {
        'locations': [
            'Florianópolis, Brazil',
            'Brasília, Brazil',
            'Campinas, Brazil',
            'Recife, Brazil',
            'Salvador, Brazil',
        ],
        'query': 'Software Engineer OR Desenvolvedor',
        'priority_boost': 5,
    },
    'geo_tier3': {
        'locations': [
            'Fortaleza, Brazil',
            'Goiânia, Brazil',
            'Joinville, Brazil',
            'Ribeirão Preto, Brazil',
            'São José dos Campos, Brazil',
        ],
        'query': 'Software Engineer OR Desenvolvedor',
        'priority_boost': 0,
    },

    # Role-based searches (run across all locations)
    'senior_roles': {
        'locations': ['Brazil'],
        'query': 'Tech Lead OR Staff Engineer OR Principal Engineer',
        'priority_boost': 20,
    },
    'leadership': {
        'locations': ['Brazil'],
        'query': 'Engineering Manager OR VP Engineering OR CTO',
        'priority_boost': 25,
    },
    'specialists': {
        'locations': ['Brazil'],
        'query': 'ML Engineer OR Data Engineer OR Platform Engineer OR SRE',
        'priority_boost': 15,
    },

    # Technology-specific (high demand skills)
    'backend': {
        'locations': ['Brazil'],
        'query': 'Python Developer OR Java Developer OR Go Developer OR Node.js Developer',
        'priority_boost': 10,
    },
    'frontend': {
        'locations': ['Brazil'],
        'query': 'React Developer OR Frontend Engineer OR TypeScript Developer',
        'priority_boost': 10,
    },
    'cloud': {
        'locations': ['Brazil'],
        'query': 'AWS Engineer OR GCP Engineer OR Azure Engineer OR DevOps Engineer',
        'priority_boost': 15,
    },
}

# Keywords that indicate tech profiles (for priority scoring)
TECH_KEYWORDS = {
    'high_value': [
        'staff engineer', 'principal engineer', 'tech lead', 'architect',
        'engineering manager', 'vp engineering', 'cto', 'director of engineering',
        'machine learning', 'ml engineer', 'data scientist', 'ai engineer',
    ],
    'mid_value': [
        'senior', 'software engineer', 'desenvolvedor', 'backend', 'frontend',
        'full stack', 'fullstack', 'devops', 'sre', 'platform',
        'python', 'java', 'golang', 'react', 'node.js', 'typescript',
    ],
    'low_value': [
        'junior', 'intern', 'estagiário', 'trainee', 'student',
    ],
}


@dataclass
class AcquisitionStats:
    """Track acquisition pipeline statistics"""
    discovered: int = 0
    duplicates: int = 0
    new_urls: int = 0
    extracted: int = 0
    failed: int = 0
    estimated_cost: float = 0.0
    actual_cost: float = 0.0


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

class DatabaseManager:
    """Manages database connections and operations"""

    def __init__(self, db_url: str = None):
        self.db_url = db_url or self._build_db_url()
        self._conn = None

    def _build_db_url(self) -> str:
        """Build database URL from environment or Secret Manager"""
        if os.getenv('DATABASE_URL'):
            return os.getenv('DATABASE_URL')

        # Get password from Secret Manager
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

    def get_existing_urls(self) -> Set[str]:
        """Get all URLs we already have (candidates + discovered)"""
        cur = self.conn.cursor()

        # Get from candidates table
        cur.execute("SELECT LOWER(linkedin_url) FROM sourcing.candidates")
        urls = {row[0] for row in cur.fetchall()}

        # Get from discovered_urls table (if exists)
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'sourcing' AND table_name = 'discovered_urls'
            )
        """)
        if cur.fetchone()[0]:
            cur.execute("SELECT LOWER(linkedin_url) FROM sourcing.discovered_urls")
            urls.update(row[0] for row in cur.fetchall())

        return urls

    def ensure_discovery_tables(self):
        """Create discovery tracking tables if they don't exist"""
        migration_file = REPO_ROOT / 'scripts' / 'migrations' / '003_discovery_tracking.sql'
        if migration_file.exists():
            cur = self.conn.cursor()
            cur.execute(migration_file.read_text())
            self.conn.commit()
            logger.info("Discovery tracking tables ready")

    def save_discovered_urls(self, profiles: List[Dict], campaign_id: int = None,
                             query: str = None, location: str = None) -> Tuple[int, int]:
        """
        Save discovered URLs, returning (new_count, duplicate_count)
        """
        cur = self.conn.cursor()
        new_count = 0
        dup_count = 0

        for profile in profiles:
            url = self._normalize_url(
                profile.get('linkedinUrl') or
                profile.get('profileUrl') or
                profile.get('url')
            )
            if not url:
                continue

            # Calculate priority score
            name = profile.get('firstName', '') + ' ' + profile.get('lastName', '')
            headline = profile.get('headline') or profile.get('title') or ''
            priority = self._calculate_priority(headline)

            try:
                cur.execute("""
                    INSERT INTO sourcing.discovered_urls
                        (linkedin_url, name, headline, location, discovery_query,
                         discovery_location, priority_score, has_tech_keywords, campaign_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (linkedin_url) DO NOTHING
                    RETURNING id
                """, (
                    url,
                    name.strip()[:200],
                    headline[:500] if headline else None,
                    profile.get('location') or profile.get('geoLocationName'),
                    query,
                    location,
                    priority,
                    priority >= 50,
                    campaign_id,
                ))

                if cur.fetchone():
                    new_count += 1
                else:
                    dup_count += 1

            except Exception as e:
                logger.warning(f"Error saving URL {url}: {e}")
                dup_count += 1

        self.conn.commit()
        return new_count, dup_count

    def get_urls_to_extract(self, limit: int = 500, min_priority: int = 0) -> List[Dict]:
        """Get high-priority discovered URLs that haven't been extracted"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, linkedin_url, name, headline, priority_score
            FROM sourcing.discovered_urls
            WHERE status = 'discovered'
              AND priority_score >= %s
            ORDER BY priority_score DESC, discovered_at ASC
            LIMIT %s
        """, (min_priority, limit))

        columns = ['id', 'linkedin_url', 'name', 'headline', 'priority_score']
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    def mark_extracted(self, url_ids: List[int], success: bool = True, error: str = None):
        """Mark URLs as extracted or failed"""
        cur = self.conn.cursor()
        if success:
            cur.execute("""
                UPDATE sourcing.discovered_urls
                SET status = 'extracted', extracted_at = NOW()
                WHERE id = ANY(%s)
            """, (url_ids,))
        else:
            cur.execute("""
                UPDATE sourcing.discovered_urls
                SET status = 'failed', extraction_error = %s
                WHERE id = ANY(%s)
            """, (error, url_ids))
        self.conn.commit()

    def _normalize_url(self, url: str) -> Optional[str]:
        """Normalize LinkedIn URL for consistent deduplication"""
        if not url:
            return None

        url = url.lower().strip()
        url = re.sub(r'/+$', '', url)  # Remove trailing slashes
        url = re.sub(r'^https?://(www\.)?', 'https://www.', url)

        # Validate it's a LinkedIn profile URL
        if 'linkedin.com/in/' not in url:
            return None

        return url

    def _calculate_priority(self, headline: str) -> int:
        """Calculate priority score based on headline keywords"""
        if not headline:
            return 50

        headline_lower = headline.lower()
        score = 50

        # Check high-value keywords
        for keyword in TECH_KEYWORDS['high_value']:
            if keyword in headline_lower:
                score += 20
                break

        # Check mid-value keywords
        for keyword in TECH_KEYWORDS['mid_value']:
            if keyword in headline_lower:
                score += 10
                break

        # Check low-value keywords (reduce priority)
        for keyword in TECH_KEYWORDS['low_value']:
            if keyword in headline_lower:
                score -= 20
                break

        return max(0, min(100, score))

    def get_status(self) -> Dict:
        """Get current pipeline status"""
        cur = self.conn.cursor()

        status = {}

        # Candidates table
        cur.execute("SELECT COUNT(*) FROM sourcing.candidates")
        status['total_candidates'] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM sourcing.candidates WHERE intelligent_analysis IS NOT NULL")
        status['enriched_candidates'] = cur.fetchone()[0]

        # Discovery table (if exists)
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'sourcing' AND table_name = 'discovered_urls'
            )
        """)
        if cur.fetchone()[0]:
            cur.execute("""
                SELECT status, COUNT(*) FROM sourcing.discovered_urls GROUP BY status
            """)
            status['discovered_urls'] = dict(cur.fetchall())
        else:
            status['discovered_urls'] = {}

        return status


# =============================================================================
# APIFY OPERATIONS
# =============================================================================

class ApifyDiscovery:
    """Handles Apify API operations for profile discovery"""

    DISCOVERY_ACTOR = "harvestapi/linkedin-profile-search"
    EXTRACTION_ACTOR = "supreme_coder/linkedin-profile-scraper"

    # Cost estimates
    DISCOVERY_COST_PER_PAGE = 0.10
    DISCOVERY_COST_PER_PROFILE = 0.004  # Full mode only
    EXTRACTION_COST_PER_1K = 3.00

    def __init__(self, token: str = None):
        self.token = token or os.getenv('APIFY_TOKEN')
        if not self.token:
            raise ValueError("APIFY_TOKEN not set")

        self._client = None

    @property
    def client(self):
        if self._client is None:
            from apify_client import ApifyClient
            self._client = ApifyClient(self.token)
        return self._client

    def discover(self, query: str, locations: List[str], max_items: int = 1000,
                 mode: str = "Short") -> Tuple[List[Dict], float]:
        """
        Discover LinkedIn profiles via search.

        Args:
            query: Search query
            locations: List of locations
            max_items: Maximum profiles to discover
            mode: "Short" (URLs only, cheap) or "Full" (with basic data)

        Returns:
            (profiles, estimated_cost)
        """
        logger.info(f"🔍 Discovering: {query} in {locations}")

        run_input = {
            "profileScraperMode": mode,
            "searchQuery": query,
            "locations": locations,
            "maxItems": max_items,
        }

        run = self.client.actor(self.DISCOVERY_ACTOR).call(run_input=run_input)
        profiles = self.client.dataset(run["defaultDatasetId"]).list_items().items

        # Estimate cost
        pages = len(profiles) / 25
        cost = pages * self.DISCOVERY_COST_PER_PAGE
        if mode == "Full":
            cost += len(profiles) * self.DISCOVERY_COST_PER_PROFILE

        logger.info(f"   Found {len(profiles)} profiles (est. ${cost:.2f})")

        return profiles, cost

    def extract(self, urls: List[str], batch_size: int = 500) -> Tuple[List[Dict], float]:
        """
        Extract full profile data from URLs.

        Args:
            urls: List of LinkedIn profile URLs
            batch_size: Profiles per batch

        Returns:
            (profiles, actual_cost)
        """
        logger.info(f"📥 Extracting {len(urls)} profiles")

        all_profiles = []
        total_cost = 0.0

        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            batch_num = (i // batch_size) + 1

            logger.info(f"   Batch {batch_num}: {len(batch)} profiles")

            try:
                run_input = {"urls": [{"url": u} for u in batch]}
                run = self.client.actor(self.EXTRACTION_ACTOR).call(run_input=run_input)
                profiles = self.client.dataset(run["defaultDatasetId"]).list_items().items

                all_profiles.extend(profiles)
                batch_cost = (len(batch) / 1000) * self.EXTRACTION_COST_PER_1K
                total_cost += batch_cost

                logger.info(f"   ✅ Extracted {len(profiles)} (${batch_cost:.2f})")

            except Exception as e:
                logger.error(f"   ❌ Batch failed: {e}")

        return all_profiles, total_cost


# =============================================================================
# PIPELINE ORCHESTRATION
# =============================================================================

class AcquisitionPipeline:
    """Main pipeline orchestrator"""

    def __init__(self):
        self.db = DatabaseManager()
        self.apify = ApifyDiscovery()
        self.stats = AcquisitionStats()

    def discover_command(self, query: str, locations: List[str], max_items: int = 1000):
        """Run discovery phase only"""
        self.db.ensure_discovery_tables()

        logger.info("=" * 60)
        logger.info("DISCOVERY PHASE")
        logger.info("=" * 60)

        # Run discovery
        profiles, cost = self.apify.discover(query, locations, max_items)
        self.stats.discovered = len(profiles)
        self.stats.estimated_cost += cost

        # Save to database (with deduplication)
        new_count, dup_count = self.db.save_discovered_urls(
            profiles, query=query, location=','.join(locations)
        )
        self.stats.new_urls = new_count
        self.stats.duplicates = dup_count

        # Save raw data as backup
        backup_file = DATA_DIR / f"discovery_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(backup_file, 'w') as f:
            json.dump(profiles, f, indent=2, default=str)

        self._print_discovery_summary()
        return self.stats

    def extract_command(self, limit: int = 500, min_priority: int = 0):
        """Extract high-priority discovered URLs"""
        logger.info("=" * 60)
        logger.info("EXTRACTION PHASE")
        logger.info("=" * 60)

        # Get URLs to extract
        to_extract = self.db.get_urls_to_extract(limit, min_priority)
        if not to_extract:
            logger.info("No URLs to extract. Run discovery first.")
            return self.stats

        logger.info(f"Found {len(to_extract)} URLs to extract (priority >= {min_priority})")

        # Extract profiles
        urls = [p['linkedin_url'] for p in to_extract]
        url_ids = [p['id'] for p in to_extract]

        profiles, cost = self.apify.extract(urls)
        self.stats.extracted = len(profiles)
        self.stats.actual_cost += cost

        # Store in candidates table
        if profiles:
            from scripts.apify_linkedin_pipeline import ApifyLinkedInPipeline
            pipeline = ApifyLinkedInPipeline()
            stored = pipeline.store_profiles(profiles)
            logger.info(f"Stored {stored} candidates")

            # Mark as extracted
            self.db.mark_extracted(url_ids, success=True)

        self._print_extraction_summary()
        return self.stats

    def campaign_command(self, name: str, config_name: str = None, budget: float = 50.0,
                         max_per_location: int = 1000):
        """Run a full discovery + extraction campaign"""
        self.db.ensure_discovery_tables()

        logger.info("=" * 60)
        logger.info(f"CAMPAIGN: {name}")
        logger.info("=" * 60)

        # Get search config
        if config_name and config_name in SEARCH_CONFIGS:
            configs = {config_name: SEARCH_CONFIGS[config_name]}
        else:
            configs = SEARCH_CONFIGS

        total_cost = 0.0
        all_new = 0

        for config_key, config in configs.items():
            if total_cost >= budget:
                logger.warning(f"Budget limit reached (${budget}). Stopping.")
                break

            logger.info(f"\n--- Config: {config_key} ---")

            for location in config['locations']:
                if total_cost >= budget:
                    break

                # Discovery
                profiles, cost = self.apify.discover(
                    config['query'], [location], max_per_location, mode="Short"
                )
                total_cost += cost

                # Save with priority boost
                new_count, dup_count = self.db.save_discovered_urls(
                    profiles, query=config['query'], location=location
                )
                all_new += new_count

                logger.info(f"   {location}: {new_count} new, {dup_count} duplicates")

        self.stats.discovered = all_new
        self.stats.estimated_cost = total_cost

        logger.info(f"\n✅ Campaign complete: {all_new} new URLs discovered, ${total_cost:.2f}")
        return self.stats

    def status_command(self):
        """Show current pipeline status"""
        status = self.db.get_status()

        print("\n" + "=" * 60)
        print("PIPELINE STATUS")
        print("=" * 60)
        print(f"Total candidates:    {status['total_candidates']:,}")
        print(f"Enriched candidates: {status['enriched_candidates']:,}")
        print()
        print("Discovered URLs:")
        for state, count in status.get('discovered_urls', {}).items():
            print(f"  {state}: {count:,}")
        print("=" * 60)

    def _print_discovery_summary(self):
        """Print discovery phase summary"""
        print("\n" + "-" * 40)
        print("DISCOVERY SUMMARY")
        print("-" * 40)
        print(f"Discovered:     {self.stats.discovered:,}")
        print(f"New URLs:       {self.stats.new_urls:,}")
        print(f"Duplicates:     {self.stats.duplicates:,}")
        print(f"Est. cost:      ${self.stats.estimated_cost:.2f}")
        print("-" * 40)

    def _print_extraction_summary(self):
        """Print extraction phase summary"""
        print("\n" + "-" * 40)
        print("EXTRACTION SUMMARY")
        print("-" * 40)
        print(f"Extracted:      {self.stats.extracted:,}")
        print(f"Actual cost:    ${self.stats.actual_cost:.2f}")
        print("-" * 40)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Robust LinkedIn Profile Acquisition Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Discover from a new location
    python candidate_acquisition_pipeline.py discover -l "Rio de Janeiro, Brazil" -m 1000

    # Discover using a predefined config
    python candidate_acquisition_pipeline.py discover --config geo_tier1

    # Extract high-priority profiles
    python candidate_acquisition_pipeline.py extract --limit 500 --min-priority 60

    # Run a full campaign with budget
    python candidate_acquisition_pipeline.py campaign --name "jan-2026-expansion" --budget 100

    # Check status
    python candidate_acquisition_pipeline.py status
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Discover command
    discover_parser = subparsers.add_parser('discover', help='Discover LinkedIn profiles')
    discover_parser.add_argument('-q', '--query', default='Software Engineer OR Desenvolvedor',
                                  help='Search query')
    discover_parser.add_argument('-l', '--location', action='append',
                                  help='Location(s) to search')
    discover_parser.add_argument('-m', '--max', type=int, default=1000,
                                  help='Max profiles to discover')
    discover_parser.add_argument('--config', choices=list(SEARCH_CONFIGS.keys()),
                                  help='Use predefined search config')

    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract discovered profiles')
    extract_parser.add_argument('--limit', type=int, default=500,
                                 help='Max profiles to extract')
    extract_parser.add_argument('--min-priority', type=int, default=0,
                                 help='Minimum priority score (0-100)')

    # Campaign command
    campaign_parser = subparsers.add_parser('campaign', help='Run full acquisition campaign')
    campaign_parser.add_argument('--name', required=True, help='Campaign name')
    campaign_parser.add_argument('--config', choices=list(SEARCH_CONFIGS.keys()),
                                  help='Specific config to use (default: all)')
    campaign_parser.add_argument('--budget', type=float, default=50.0,
                                  help='Budget in USD')
    campaign_parser.add_argument('--max-per-location', type=int, default=1000,
                                  help='Max profiles per location')

    # Status command
    subparsers.add_parser('status', help='Show pipeline status')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    pipeline = AcquisitionPipeline()

    if args.command == 'discover':
        if args.config:
            config = SEARCH_CONFIGS[args.config]
            pipeline.discover_command(config['query'], config['locations'], args.max)
        else:
            locations = args.location or ['São Paulo, Brazil']
            pipeline.discover_command(args.query, locations, args.max)

    elif args.command == 'extract':
        pipeline.extract_command(args.limit, args.min_priority)

    elif args.command == 'campaign':
        pipeline.campaign_command(args.name, args.config, args.budget, args.max_per_location)

    elif args.command == 'status':
        pipeline.status_command()


if __name__ == '__main__':
    main()
