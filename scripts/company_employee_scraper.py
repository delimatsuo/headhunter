#!/usr/bin/env python3
"""
Company-Focused Employee Scraper for Ella Sourcing

Scrapes engineering talent from curated list of:
- Brazilian unicorns ($1B+ valuation)
- Global big tech (Brazil offices)
- Funded scaleups (Series A-C)
- Emerging startups (recent funding)

Uses Apify's LinkedIn Company Employees actors to extract
engineers from specific company pages.

Usage:
    # Scrape a single company
    python company_employee_scraper.py scrape --company "nubank"

    # Scrape a tier of companies
    python company_employee_scraper.py scrape-tier --tier tier1_unicorns --budget 50

    # Scrape all companies with budget
    python company_employee_scraper.py scrape-all --budget 200

    # List target companies
    python company_employee_scraper.py list-companies

    # Check status
    python company_employee_scraper.py status
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
TARGET_COMPANIES_FILE = DATA_DIR / 'target_companies.json'


# =============================================================================
# CONFIGURATION
# =============================================================================

# Engineering-related keywords for filtering (BILINGUAL: English + Portuguese)
ENGINEERING_TITLES = [
    # === ENGLISH TITLES ===
    # Core engineering
    'software engineer', 'developer', 'programmer', 'coder',
    'engineer', 'engineering',

    # Specializations
    'backend', 'frontend', 'full stack', 'fullstack', 'full-stack',
    'devops', 'sre', 'site reliability', 'platform engineer',
    'data engineer', 'ml engineer', 'machine learning', 'ai engineer',
    'cloud engineer', 'infrastructure engineer', 'systems engineer',
    'security engineer', 'qa engineer', 'test engineer', 'sdet',

    # Mobile
    'ios developer', 'android developer', 'mobile developer', 'mobile engineer',
    'react native', 'flutter developer',

    # Leadership
    'tech lead', 'technical lead', 'team lead',
    'engineering manager', 'em ', 'director of engineering',
    'vp engineering', 'vp of engineering', 'head of engineering',
    'cto', 'chief technology', 'chief technical',
    'architect', 'software architect', 'solutions architect', 'technical architect',

    # Seniority
    'staff engineer', 'principal engineer', 'senior engineer',
    'senior software', 'senior developer', 'sr engineer', 'sr developer',
    'lead engineer', 'lead developer',

    # === PORTUGUESE TITLES ===
    # Core engineering
    'desenvolvedor', 'programador', 'programadora',
    'engenheiro de software', 'engenheira de software',
    'engenheiro', 'engenheira',

    # Specializations
    'desenvolvedor backend', 'desenvolvedor frontend',
    'desenvolvedor full stack', 'desenvolvedor fullstack',
    'desenvolvedor mobile', 'desenvolvedor ios', 'desenvolvedor android',
    'engenheiro de dados', 'engenheira de dados',
    'engenheiro de plataforma', 'engenheiro devops',
    'engenheiro de machine learning', 'engenheiro de ml',
    'engenheiro de infraestrutura', 'engenheiro de cloud',
    'engenheiro de segurança', 'engenheiro de qa',
    'cientista de dados', 'data scientist',

    # Analyst roles (common in Brazil)
    'analista de sistemas', 'analista desenvolvedor', 'analista programador',
    'analista de desenvolvimento', 'analista de software',

    # Leadership
    'líder técnico', 'lider tecnico', 'tech lead',
    'gerente de engenharia', 'gerente de desenvolvimento',
    'diretor de engenharia', 'diretor de tecnologia',
    'head de engenharia', 'head de tecnologia',
    'arquiteto de software', 'arquiteto de soluções', 'arquiteto de sistemas',

    # Seniority
    'desenvolvedor sênior', 'desenvolvedor senior', 'desenvolvedor pleno',
    'engenheiro sênior', 'engenheiro senior',
    'analista sênior', 'analista senior',
]

# Bilingual search queries for Apify
SEARCH_QUERIES_BILINGUAL = [
    "Software Engineer OR Desenvolvedor OR Programador",
    "Backend Developer OR Desenvolvedor Backend OR Engenheiro Backend",
    "Frontend Developer OR Desenvolvedor Frontend OR Engenheiro Frontend",
    "Full Stack OR Desenvolvedor Full Stack OR Fullstack",
    "DevOps OR SRE OR Engenheiro DevOps",
    "Data Engineer OR Engenheiro de Dados OR Cientista de Dados",
    "Tech Lead OR Líder Técnico OR Technical Lead",
    "Engineering Manager OR Gerente de Engenharia",
    "Mobile Developer OR Desenvolvedor Mobile OR iOS OR Android",
    "Analista de Sistemas OR Analista Desenvolvedor",
]

# Keywords to exclude (non-engineering roles)
EXCLUDE_TITLES = [
    'recruiter', 'talent', 'hr', 'human resources',
    'sales', 'marketing', 'finance', 'legal',
    'customer success', 'support', 'design', 'ux', 'ui',
    'product manager', 'project manager', 'scrum master',
    'ceo', 'cfo', 'coo', 'founder',  # unless CTO
]


@dataclass
class ScraperStats:
    """Track scraping statistics"""
    companies_processed: int = 0
    employees_found: int = 0
    engineers_found: int = 0
    duplicates_skipped: int = 0
    stored: int = 0
    failed: int = 0
    estimated_cost: float = 0.0


# =============================================================================
# APIFY CLIENT
# =============================================================================

class CompanyEmployeeScraper:
    """Scrapes employees from LinkedIn company pages using Apify"""

    # Actor for company employee scraping
    # harvestapi/linkedin-company-employees is recommended:
    # - $4/1k for basic data (name, title, profile URL)
    # - $8/1k for full data (experience, skills)
    # - No cookies required
    ACTOR_ID = "harvestapi/linkedin-company-employees"

    # Pricing per 1,000 employees
    COST_SHORT = 4.0   # Basic data
    COST_FULL = 8.0    # Full profile data

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

    def scrape_company(
        self,
        company_url: str,
        mode: str = "Short",
        max_employees: int = 1000,
        title_filter: str = None
    ) -> Tuple[List[Dict], float]:
        """
        Scrape employees from a company's LinkedIn page.

        Args:
            company_url: LinkedIn company URL (e.g., https://www.linkedin.com/company/nubank/)
            mode: "Short" (basic data, cheaper) or "Full" (complete profiles)
            max_employees: Maximum employees to scrape
            title_filter: Optional role/title keyword filter (e.g., "engineer")

        Returns:
            (employees, cost)
        """
        logger.info(f"🏢 Scraping: {company_url}")

        # Map mode to profileScraperMode (as expected by harvestapi actor)
        scraper_mode = f"{mode} ($4 per 1k)" if mode == "Short" else f"{mode} ($8 per 1k)"

        run_input = {
            "companies": [company_url],  # Correct parameter name
            "profileScraperMode": scraper_mode,  # Correct parameter name
            "maxItems": max_employees,  # Correct parameter name
        }

        # Add job titles filter if specified (bilingual engineering titles)
        if title_filter:
            run_input["searchQuery"] = title_filter  # Use searchQuery for fuzzy matching
            logger.info(f"   Filter: {title_filter}")

        try:
            run = self.client.actor(self.ACTOR_ID).call(run_input=run_input)
            employees = self.client.dataset(run["defaultDatasetId"]).list_items().items

            # Calculate cost
            cost_per_1k = self.COST_SHORT if mode == "Short" else self.COST_FULL
            cost = (len(employees) / 1000) * cost_per_1k

            logger.info(f"   Found {len(employees)} employees (${cost:.2f})")

            return employees, cost

        except Exception as e:
            logger.error(f"   ❌ Failed: {e}")
            return [], 0.0

    def filter_engineers(self, employees: List[Dict]) -> List[Dict]:
        """Filter employees to keep only engineering roles"""
        engineers = []

        for emp in employees:
            # Get title from various possible locations in Apify response
            title = ''
            if emp.get('currentPositions') and len(emp['currentPositions']) > 0:
                title = emp['currentPositions'][0].get('title', '')
            title = title or emp.get('title') or emp.get('headline') or ''
            title = title.lower()

            # Check if title contains engineering keywords
            is_engineer = any(keyword in title for keyword in ENGINEERING_TITLES)

            # Check if title contains exclusion keywords
            is_excluded = any(keyword in title for keyword in EXCLUDE_TITLES)

            # Special case: CTOs are engineers
            if 'cto' in title or 'chief technology' in title:
                is_engineer = True
                is_excluded = False

            if is_engineer and not is_excluded:
                engineers.append(emp)

        return engineers


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

class DatabaseManager:
    """Manages database operations for storing scraped profiles"""

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

    def get_existing_urls(self) -> Set[str]:
        """Get all LinkedIn URLs we already have"""
        cur = self.conn.cursor()
        cur.execute("SELECT LOWER(linkedin_url) FROM sourcing.candidates")
        return {row[0] for row in cur.fetchall()}

    def store_employees(
        self,
        employees: List[Dict],
        company_name: str,
        source: str = "company_scrape"
    ) -> int:
        """Store scraped employees in the candidates table"""
        cur = self.conn.cursor()
        stored = 0
        existing_urls = self.get_existing_urls()

        for emp in employees:
            url = self._normalize_url(
                emp.get('linkedinUrl') or
                emp.get('profileUrl') or
                emp.get('url')
            )
            if not url:
                continue

            # Skip duplicates
            if url.lower() in existing_urls:
                continue

            # Extract headline from currentPositions if available
            headline = ''
            if emp.get('currentPositions') and len(emp['currentPositions']) > 0:
                pos = emp['currentPositions'][0]
                headline = f"{pos.get('title', '')} at {pos.get('companyName', '')}"
            headline = headline or emp.get('title') or emp.get('headline') or ''

            # Extract location (may be nested object)
            location = ''
            if isinstance(emp.get('location'), dict):
                location = emp['location'].get('linkedinText', '')
            else:
                location = emp.get('location') or emp.get('geoLocationName') or ''

            try:
                cur.execute("""
                    INSERT INTO sourcing.candidates (
                        linkedin_url, first_name, last_name, headline,
                        location, profile_image_url, scraped_at, source
                    ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
                    ON CONFLICT (linkedin_url) DO NOTHING
                    RETURNING id
                """, (
                    url,
                    emp.get('firstName') or (emp.get('name', '').split()[0] if emp.get('name') else None),
                    emp.get('lastName') or (' '.join(emp.get('name', '').split()[1:]) if emp.get('name') else None),
                    headline,
                    location,
                    emp.get('pictureUrl') or emp.get('profilePicture'),
                    f"{source}:{company_name}"
                ))

                if cur.fetchone():
                    stored += 1
                    existing_urls.add(url.lower())  # Prevent duplicates in same batch

            except Exception as e:
                logger.warning(f"Error storing {url}: {e}")

        self.conn.commit()
        return stored

    def _normalize_url(self, url: str) -> Optional[str]:
        """Normalize LinkedIn URL"""
        if not url:
            return None

        url = url.strip()
        url = re.sub(r'/+$', '', url)

        # Ensure https://www. prefix
        if not url.startswith('http'):
            url = 'https://www.linkedin.com' + url
        url = re.sub(r'^https?://(www\.)?', 'https://www.', url)

        # Accept both /in/ (profiles) format
        if 'linkedin.com/in/' not in url.lower():
            return None

        return url

    def get_stats(self) -> Dict:
        """Get current database statistics"""
        cur = self.conn.cursor()

        stats = {}
        cur.execute("SELECT COUNT(*) FROM sourcing.candidates")
        stats['total_candidates'] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM sourcing.candidates WHERE intelligent_analysis IS NOT NULL")
        stats['enriched'] = cur.fetchone()[0]

        cur.execute("""
            SELECT source, COUNT(*)
            FROM sourcing.candidates
            WHERE source LIKE 'company_scrape:%'
            GROUP BY source
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """)
        stats['by_company'] = dict(cur.fetchall())

        return stats


# =============================================================================
# PIPELINE ORCHESTRATION
# =============================================================================

class CompanyAcquisitionPipeline:
    """Orchestrates company-focused talent acquisition"""

    def __init__(self):
        self.scraper = CompanyEmployeeScraper()
        self.db = DatabaseManager()
        self.stats = ScraperStats()
        self.target_companies = self._load_target_companies()

    def _load_target_companies(self) -> Dict:
        """Load target companies from JSON file"""
        if TARGET_COMPANIES_FILE.exists():
            with open(TARGET_COMPANIES_FILE) as f:
                return json.load(f)
        return {"tiers": {}}

    def list_companies(self):
        """List all target companies by tier"""
        print("\n" + "=" * 70)
        print("TARGET COMPANIES FOR ENGINEERING TALENT ACQUISITION")
        print("=" * 70)

        for tier_name, tier_data in self.target_companies.get('tiers', {}).items():
            print(f"\n📊 {tier_name.upper()}")
            print(f"   {tier_data.get('description', '')}")
            print(f"   Priority: {tier_data.get('priority', 0)}")
            print("-" * 50)

            for company in tier_data.get('companies', []):
                name = company.get('name', 'Unknown')
                funding = company.get('funding') or company.get('valuation', '')
                sector = company.get('sector', '')
                print(f"   • {name:25} | {sector:15} | {funding}")

        summary = self.target_companies.get('summary', {})
        print("\n" + "=" * 70)
        print(f"Total companies: {summary.get('total_companies', 0)}")
        print(f"Estimated engineering talent: {summary.get('estimated_engineering_talent', 0):,}")
        print("=" * 70)

    def scrape_company(self, company_name: str, max_employees: int = 500, mode: str = "Short"):
        """Scrape a single company by name"""
        company = self._find_company(company_name)
        if not company:
            logger.error(f"Company '{company_name}' not found in target list")
            return

        url = company.get('linkedin_url')
        logger.info(f"🎯 Scraping: {company.get('name')}")

        # Scrape employees
        employees, cost = self.scraper.scrape_company(
            url,
            mode=mode,
            max_employees=max_employees,
            title_filter="engineer OR developer OR desenvolvedor OR analista OR software OR data OR tech OR arquiteto OR devops OR sre OR sistemas"
        )
        self.stats.employees_found = len(employees)
        self.stats.estimated_cost += cost

        # Apify already filters by search query, but apply local filter for extra strictness
        # Can be disabled by setting filter_locally=False for better cost efficiency
        engineers = self.scraper.filter_engineers(employees) if True else employees
        self.stats.engineers_found = len(engineers)
        if len(engineers) != len(employees):
            logger.info(f"   Local filter: {len(employees)} → {len(engineers)} engineers")

        # Store in database
        stored = self.db.store_employees(engineers, company.get('name'))
        self.stats.stored = stored
        logger.info(f"   Stored {stored} new profiles")

        # Save raw data as backup
        backup_file = DATA_DIR / f"company_{company.get('name').lower().replace(' ', '_')}_{datetime.now():%Y%m%d}.json"
        with open(backup_file, 'w') as f:
            json.dump(engineers, f, indent=2, default=str)

        self._print_summary()

    def scrape_tier(self, tier_name: str, budget: float = 50.0, max_per_company: int = 500):
        """Scrape all companies in a tier"""
        tier = self.target_companies.get('tiers', {}).get(tier_name)
        if not tier:
            logger.error(f"Tier '{tier_name}' not found")
            return

        companies = tier.get('companies', [])
        logger.info(f"🎯 Scraping tier: {tier_name} ({len(companies)} companies)")
        logger.info(f"   Budget: ${budget:.2f}")

        total_cost = 0.0
        all_engineers = []

        for company in companies:
            if total_cost >= budget:
                logger.warning(f"Budget limit reached (${budget}). Stopping.")
                break

            name = company.get('name')
            url = company.get('linkedin_url')

            if not url:
                logger.warning(f"   Skipping {name} - no LinkedIn URL")
                continue

            logger.info(f"\n🏢 {name}")

            # Scrape
            employees, cost = self.scraper.scrape_company(
                url,
                mode="Short",
                max_employees=max_per_company,
                title_filter="engineer OR developer OR desenvolvedor OR analista OR software OR data OR tech OR arquiteto OR devops OR sre OR sistemas"
            )

            if not employees:
                continue

            total_cost += cost
            self.stats.companies_processed += 1
            self.stats.employees_found += len(employees)

            # Filter to engineers
            engineers = self.scraper.filter_engineers(employees)
            self.stats.engineers_found += len(engineers)
            all_engineers.extend(engineers)

            # Store
            stored = self.db.store_employees(engineers, name)
            self.stats.stored += stored

            logger.info(f"   Found {len(employees)} employees → {len(engineers)} engineers → {stored} new")

        self.stats.estimated_cost = total_cost

        # Save combined backup
        if all_engineers:
            backup_file = DATA_DIR / f"tier_{tier_name}_{datetime.now():%Y%m%d}.json"
            with open(backup_file, 'w') as f:
                json.dump(all_engineers, f, indent=2, default=str)

        self._print_summary()

    def scrape_all(self, budget: float = 200.0, max_per_company: int = 300):
        """Scrape all target companies within budget"""
        logger.info("🚀 FULL ACQUISITION RUN")
        logger.info(f"   Budget: ${budget:.2f}")

        # Sort tiers by priority
        tiers = sorted(
            self.target_companies.get('tiers', {}).items(),
            key=lambda x: x[1].get('priority', 0),
            reverse=True
        )

        total_cost = 0.0
        all_engineers = []

        for tier_name, tier_data in tiers:
            if total_cost >= budget:
                break

            remaining_budget = budget - total_cost
            logger.info(f"\n{'='*60}")
            logger.info(f"TIER: {tier_name} (remaining budget: ${remaining_budget:.2f})")
            logger.info(f"{'='*60}")

            for company in tier_data.get('companies', []):
                if total_cost >= budget:
                    break

                url = company.get('linkedin_url')
                if not url:
                    continue

                name = company.get('name')
                logger.info(f"\n🏢 {name}")

                employees, cost = self.scraper.scrape_company(
                    url,
                    mode="Short",
                    max_employees=max_per_company,
                    title_filter="engineer OR developer OR desenvolvedor OR analista OR software OR data OR tech OR arquiteto OR devops OR sre OR sistemas"
                )

                if not employees:
                    continue

                total_cost += cost
                self.stats.companies_processed += 1
                self.stats.employees_found += len(employees)

                engineers = self.scraper.filter_engineers(employees)
                self.stats.engineers_found += len(engineers)
                all_engineers.extend(engineers)

                stored = self.db.store_employees(engineers, name)
                self.stats.stored += stored

                logger.info(f"   {len(engineers)} engineers → {stored} new (${cost:.2f})")

        self.stats.estimated_cost = total_cost

        # Save backup
        if all_engineers:
            backup_file = DATA_DIR / f"all_companies_{datetime.now():%Y%m%d}.json"
            with open(backup_file, 'w') as f:
                json.dump(all_engineers, f, indent=2, default=str)

        self._print_summary()

    def status(self):
        """Show current acquisition status"""
        stats = self.db.get_stats()

        print("\n" + "=" * 60)
        print("ACQUISITION STATUS")
        print("=" * 60)
        print(f"Total candidates:    {stats['total_candidates']:,}")
        print(f"Enriched:            {stats['enriched']:,}")
        print()
        print("By company source:")
        for source, count in stats.get('by_company', {}).items():
            company = source.replace('company_scrape:', '')
            print(f"   {company:25} {count:,}")
        print("=" * 60)

    def _find_company(self, name: str) -> Optional[Dict]:
        """Find a company by name (case-insensitive)"""
        name_lower = name.lower()
        for tier_data in self.target_companies.get('tiers', {}).values():
            for company in tier_data.get('companies', []):
                if name_lower in company.get('name', '').lower():
                    return company
        return None

    def _print_summary(self):
        """Print acquisition summary"""
        print("\n" + "-" * 50)
        print("ACQUISITION SUMMARY")
        print("-" * 50)
        print(f"Companies processed: {self.stats.companies_processed}")
        print(f"Employees found:     {self.stats.employees_found:,}")
        print(f"Engineers filtered:  {self.stats.engineers_found:,}")
        print(f"New profiles stored: {self.stats.stored:,}")
        print(f"Estimated cost:      ${self.stats.estimated_cost:.2f}")
        print("-" * 50)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Company-focused LinkedIn employee scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List target companies
    python company_employee_scraper.py list-companies

    # Scrape a single company
    python company_employee_scraper.py scrape --company nubank

    # Scrape all unicorns
    python company_employee_scraper.py scrape-tier --tier tier1_unicorns --budget 100

    # Full run with budget
    python company_employee_scraper.py scrape-all --budget 200

    # Check status
    python company_employee_scraper.py status
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # List companies
    subparsers.add_parser('list-companies', help='List target companies')

    # Scrape single company
    scrape_parser = subparsers.add_parser('scrape', help='Scrape a single company')
    scrape_parser.add_argument('--company', required=True, help='Company name')
    scrape_parser.add_argument('--max', type=int, default=500, help='Max employees')
    scrape_parser.add_argument('--mode', choices=['Short', 'Full'], default='Short')

    # Scrape tier
    tier_parser = subparsers.add_parser('scrape-tier', help='Scrape all companies in a tier')
    tier_parser.add_argument('--tier', required=True,
                             choices=['tier1_unicorns', 'tier2_big_tech_brazil',
                                      'tier3_funded_scaleups', 'tier4_series_ab_funded',
                                      'tier5_emerging_startups', 'tier6_software_consultancies',
                                      'tier7_missing_unicorns'])
    tier_parser.add_argument('--budget', type=float, default=50.0, help='Budget in USD')
    tier_parser.add_argument('--max-per-company', type=int, default=500)

    # Scrape all
    all_parser = subparsers.add_parser('scrape-all', help='Scrape all target companies')
    all_parser.add_argument('--budget', type=float, default=200.0, help='Budget in USD')
    all_parser.add_argument('--max-per-company', type=int, default=300)

    # Status
    subparsers.add_parser('status', help='Show acquisition status')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    pipeline = CompanyAcquisitionPipeline()

    if args.command == 'list-companies':
        pipeline.list_companies()

    elif args.command == 'scrape':
        pipeline.scrape_company(args.company, args.max, args.mode)

    elif args.command == 'scrape-tier':
        pipeline.scrape_tier(args.tier, args.budget, args.max_per_company)

    elif args.command == 'scrape-all':
        pipeline.scrape_all(args.budget, args.max_per_company)

    elif args.command == 'status':
        pipeline.status()


if __name__ == '__main__':
    main()
