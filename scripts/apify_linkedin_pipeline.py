#!/usr/bin/env python3
"""
Apify LinkedIn Pipeline for Ella Sourcing
Discovers and extracts Brazilian software engineer profiles from LinkedIn
Uses optimized actors for best cost-benefit:
- harvestapi/linkedin-profile-search ($0.10/page + $0.004/profile) - Discovery
- supreme_coder/linkedin-profile-scraper ($3/1k profiles) - Extraction
"""

import os
import json
import asyncio
import psycopg2
from psycopg2.extras import execute_values, Json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Project paths
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / 'data' / 'sourcing'
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PipelineStats:
    """Track pipeline execution statistics"""
    discovery_profiles: int = 0
    extracted_profiles: int = 0
    stored_profiles: int = 0
    failed_extractions: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    estimated_cost: float = 0.0
    errors: List[str] = field(default_factory=list)


class ApifyLinkedInPipeline:
    """
    Main pipeline for LinkedIn profile discovery and extraction.

    Cost estimates:
    - Discovery: ~$0.10/page + $0.004/profile (harvestapi)
    - Extraction: ~$3/1k profiles (supreme_coder)
    - Total for 5k pilot: ~$40-50
    """

    # Actor IDs (optimized for cost-benefit)
    DISCOVERY_ACTOR = "harvestapi/linkedin-profile-search"  # 5.0 rating, auto-segmentation
    EXTRACTION_ACTOR = "supreme_coder/linkedin-profile-scraper"  # $3/1k, 4.3 rating

    def __init__(self, apify_token: str = None, db_url: str = None):
        """
        Initialize pipeline with Apify token and database connection.

        Args:
            apify_token: Apify API token (or set APIFY_TOKEN env var)
            db_url: PostgreSQL connection URL (or set DATABASE_URL env var)
        """
        self.apify_token = apify_token or os.getenv('APIFY_TOKEN')
        if not self.apify_token:
            raise ValueError("Apify token required. Set APIFY_TOKEN env var or pass apify_token parameter.")

        self.db_url = db_url or os.getenv('DATABASE_URL')
        if not self.db_url:
            logger.warning("No DATABASE_URL set. Will save to JSON files only.")

        self.stats = PipelineStats()
        self._client = None

    @property
    def client(self):
        """Lazy-load Apify client"""
        if self._client is None:
            try:
                from apify_client import ApifyClient
                self._client = ApifyClient(self.apify_token)
            except ImportError:
                raise ImportError("apify-client not installed. Run: pip install apify-client")
        return self._client

    def discover_profiles(
        self,
        search_query: str = "Software Engineer OR Desenvolvedor",
        locations: List[str] = None,
        max_items: int = 5000,
        scraper_mode: str = "Short"
    ) -> List[Dict]:
        """
        Step 1: Discover LinkedIn profiles via search.

        Args:
            search_query: Boolean search query (e.g., "Software Engineer OR Desenvolvedor")
            locations: List of locations to search (default: ["São Paulo, Brazil"])
            max_items: Maximum profiles to discover
            scraper_mode: "Short" (URLs only, cheaper) or "Full" (with basic data)

        Returns:
            List of profile dictionaries with linkedinUrl

        Cost: ~$0.10/page + $0.004/profile
        """
        locations = locations or ["São Paulo, Brazil"]

        logger.info(f"🔍 Starting profile discovery...")
        logger.info(f"   Query: {search_query}")
        logger.info(f"   Locations: {locations}")
        logger.info(f"   Max items: {max_items}")
        logger.info(f"   Mode: {scraper_mode}")

        run_input = {
            "profileScraperMode": scraper_mode,
            "searchQuery": search_query,
            "locations": locations,
            "maxItems": max_items,
        }

        try:
            # Run discovery actor
            logger.info(f"   Running actor: {self.DISCOVERY_ACTOR}")
            run = self.client.actor(self.DISCOVERY_ACTOR).call(run_input=run_input)

            # Get results
            dataset_items = self.client.dataset(run["defaultDatasetId"]).list_items().items

            self.stats.discovery_profiles = len(dataset_items)
            logger.info(f"✅ Discovered {len(dataset_items)} profiles")

            # Estimate cost (rough)
            pages_estimated = len(dataset_items) / 25  # ~25 results per page
            self.stats.estimated_cost += pages_estimated * 0.10
            if scraper_mode == "Full":
                self.stats.estimated_cost += len(dataset_items) * 0.004

            # Save to file for backup
            discovery_file = DATA_DIR / f"discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(discovery_file, 'w') as f:
                json.dump(dataset_items, f, indent=2, default=str)
            logger.info(f"   Saved to: {discovery_file}")

            return dataset_items

        except Exception as e:
            logger.error(f"❌ Discovery failed: {e}")
            self.stats.errors.append(f"Discovery: {str(e)}")
            raise

    def extract_profiles(
        self,
        profile_urls: List[str],
        batch_size: int = 500
    ) -> List[Dict]:
        """
        Step 2: Extract full profile data from LinkedIn URLs.

        Args:
            profile_urls: List of LinkedIn profile URLs
            batch_size: Number of profiles per batch (to avoid timeouts)

        Returns:
            List of enriched profile dictionaries

        Cost: ~$3 per 1,000 profiles
        """
        logger.info(f"📥 Starting profile extraction...")
        logger.info(f"   Total URLs: {len(profile_urls)}")
        logger.info(f"   Batch size: {batch_size}")

        all_profiles = []

        # Process in batches
        for i in range(0, len(profile_urls), batch_size):
            batch = profile_urls[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(profile_urls) + batch_size - 1) // batch_size

            logger.info(f"   Processing batch {batch_num}/{total_batches} ({len(batch)} profiles)")

            try:
                # supreme_coder expects urls as objects with 'url' key
                urls_formatted = [{"url": url} for url in batch]
                run_input = {
                    "urls": urls_formatted
                }

                run = self.client.actor(self.EXTRACTION_ACTOR).call(run_input=run_input)
                batch_profiles = self.client.dataset(run["defaultDatasetId"]).list_items().items

                all_profiles.extend(batch_profiles)
                self.stats.extracted_profiles += len(batch_profiles)

                logger.info(f"   ✅ Batch {batch_num}: Extracted {len(batch_profiles)} profiles")

            except Exception as e:
                logger.error(f"   ❌ Batch {batch_num} failed: {e}")
                self.stats.failed_extractions += len(batch)
                self.stats.errors.append(f"Extraction batch {batch_num}: {str(e)}")

        # Estimate cost
        self.stats.estimated_cost += (len(profile_urls) / 1000) * 3.0

        # Save to file for backup
        extraction_file = DATA_DIR / f"extracted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(extraction_file, 'w') as f:
            json.dump(all_profiles, f, indent=2, default=str)
        logger.info(f"   Saved to: {extraction_file}")

        return all_profiles

    def store_profiles(self, profiles: List[Dict]) -> int:
        """
        Step 3: Store extracted profiles in Cloud SQL.

        Args:
            profiles: List of profile dictionaries from extraction

        Returns:
            Number of profiles stored
        """
        if not self.db_url:
            logger.warning("⚠️ No database URL configured. Skipping database storage.")
            return 0

        logger.info(f"💾 Storing {len(profiles)} profiles to database...")

        conn = None
        stored_count = 0

        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()

            # Prepare data for insertion
            candidate_data = []
            for profile in profiles:
                # Build LinkedIn URL from publicIdentifier if not directly available
                linkedin_url = (
                    profile.get('linkedinUrl') or
                    profile.get('profileUrl') or
                    (f"https://www.linkedin.com/in/{profile.get('publicIdentifier')}"
                     if profile.get('publicIdentifier') else None)
                )

                if not linkedin_url:
                    logger.warning(f"Skipping profile without URL: {profile.get('firstName')} {profile.get('lastName')}")
                    continue

                # Extract location from various possible fields
                location = (
                    profile.get('location') or
                    profile.get('geoLocationName') or
                    profile.get('locationName')
                )

                # Get country from geoCountryName or default to Brazil
                country = profile.get('geoCountryName') or 'Brazil'

                candidate_data.append((
                    linkedin_url,
                    profile.get('firstName'),
                    profile.get('lastName'),
                    profile.get('headline') or profile.get('jobTitle'),
                    location,
                    country,
                    profile.get('summary') or profile.get('about'),
                    profile.get('pictureUrl') or profile.get('profilePicture'),
                    profile.get('connections'),
                    profile.get('followers'),
                    datetime.now(),
                    'apify_linkedin'
                ))

            # Upsert candidates
            insert_query = """
                INSERT INTO sourcing.candidates (
                    linkedin_url, first_name, last_name, headline, location,
                    country, summary, profile_image_url, connections, followers,
                    scraped_at, source
                ) VALUES %s
                ON CONFLICT (linkedin_url) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    headline = EXCLUDED.headline,
                    location = EXCLUDED.location,
                    summary = EXCLUDED.summary,
                    profile_image_url = EXCLUDED.profile_image_url,
                    connections = EXCLUDED.connections,
                    followers = EXCLUDED.followers,
                    last_updated = NOW()
                RETURNING id
            """

            result = execute_values(cur, insert_query, candidate_data, fetch=True)
            stored_count = len(result)

            # Store experience data
            for profile in profiles:
                linkedin_url = profile.get('linkedinUrl') or profile.get('profileUrl')
                experiences = profile.get('experience') or profile.get('positions') or []

                if experiences and linkedin_url:
                    self._store_experience(cur, linkedin_url, experiences)

            # Store skills
            for profile in profiles:
                linkedin_url = profile.get('linkedinUrl') or profile.get('profileUrl')
                skills = profile.get('skills') or []

                if skills and linkedin_url:
                    self._store_skills(cur, linkedin_url, skills)

            conn.commit()
            self.stats.stored_profiles = stored_count
            logger.info(f"✅ Stored {stored_count} profiles to database")

        except Exception as e:
            logger.error(f"❌ Database storage failed: {e}")
            self.stats.errors.append(f"Database: {str(e)}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

        return stored_count

    def _store_experience(self, cur, linkedin_url: str, experiences: List[Dict]):
        """Store work experience for a candidate"""
        # Get candidate ID
        cur.execute(
            "SELECT id FROM sourcing.candidates WHERE linkedin_url = %s",
            (linkedin_url,)
        )
        result = cur.fetchone()
        if not result:
            return

        candidate_id = result[0]

        # Delete existing experience
        cur.execute(
            "DELETE FROM sourcing.experience WHERE candidate_id = %s",
            (candidate_id,)
        )

        # Insert new experience
        for exp in experiences:
            cur.execute("""
                INSERT INTO sourcing.experience (
                    candidate_id, company_name, company_linkedin_url, title,
                    location, start_date, end_date, is_current, description
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                candidate_id,
                exp.get('companyName') or exp.get('company'),
                exp.get('companyLinkedinUrl') or exp.get('companyUrl'),
                exp.get('title') or exp.get('position'),
                exp.get('location'),
                self._parse_date(exp.get('startDate')),
                self._parse_date(exp.get('endDate')),
                exp.get('isCurrent', False),
                exp.get('description')
            ))

    def _store_skills(self, cur, linkedin_url: str, skills: List):
        """Store skills for a candidate"""
        # Get candidate ID
        cur.execute(
            "SELECT id FROM sourcing.candidates WHERE linkedin_url = %s",
            (linkedin_url,)
        )
        result = cur.fetchone()
        if not result:
            return

        candidate_id = result[0]

        # Delete existing skills
        cur.execute(
            "DELETE FROM sourcing.candidate_skills WHERE candidate_id = %s",
            (candidate_id,)
        )

        for skill_data in skills:
            # Handle both string and dict formats
            if isinstance(skill_data, str):
                skill_name = skill_data
                endorsements = 0
            else:
                skill_name = skill_data.get('name') or skill_data.get('skill')
                endorsements = skill_data.get('endorsements') or skill_data.get('endorsementCount', 0)

            if not skill_name:
                continue

            # Upsert skill
            cur.execute("""
                INSERT INTO sourcing.skills (name, normalized_name)
                VALUES (%s, %s)
                ON CONFLICT (name) DO NOTHING
                RETURNING id
            """, (skill_name, skill_name.lower()))

            result = cur.fetchone()
            if result:
                skill_id = result[0]
            else:
                cur.execute("SELECT id FROM sourcing.skills WHERE name = %s", (skill_name,))
                skill_id = cur.fetchone()[0]

            # Link skill to candidate
            cur.execute("""
                INSERT INTO sourcing.candidate_skills (candidate_id, skill_id, endorsement_count)
                VALUES (%s, %s, %s)
                ON CONFLICT (candidate_id, skill_id) DO UPDATE SET
                    endorsement_count = EXCLUDED.endorsement_count
            """, (candidate_id, skill_id, endorsements))

    def _parse_date(self, date_str) -> Optional[str]:
        """Parse date string to SQL-compatible format"""
        if not date_str:
            return None

        if isinstance(date_str, dict):
            year = date_str.get('year')
            month = date_str.get('month', 1)
            if year:
                return f"{year}-{month:02d}-01"
            return None

        # Try common formats
        for fmt in ['%Y-%m-%d', '%Y-%m', '%Y']:
            try:
                from datetime import datetime as dt
                parsed = dt.strptime(str(date_str)[:10], fmt)
                return parsed.strftime('%Y-%m-%d')
            except ValueError:
                continue

        return None

    def run_pilot(
        self,
        search_query: str = "Software Engineer OR Desenvolvedor",
        location: str = "São Paulo, Brazil",
        max_profiles: int = 100
    ) -> PipelineStats:
        """
        Run a small pilot to test the pipeline.

        Args:
            search_query: Search query
            location: Target location
            max_profiles: Maximum profiles to process (keep small for testing)

        Returns:
            Pipeline statistics
        """
        logger.info("=" * 60)
        logger.info("🚀 STARTING ELLA SOURCING PILOT")
        logger.info("=" * 60)

        self.stats.start_time = datetime.now()

        try:
            # Step 1: Discover
            discovered = self.discover_profiles(
                search_query=search_query,
                locations=[location],
                max_items=max_profiles,
                scraper_mode="Short"
            )

            # Extract URLs
            profile_urls = [
                p.get('linkedinUrl') or p.get('profileUrl')
                for p in discovered
                if p.get('linkedinUrl') or p.get('profileUrl')
            ]

            if not profile_urls:
                logger.warning("⚠️ No profile URLs found in discovery results")
                return self.stats

            # Step 2: Extract
            profiles = self.extract_profiles(profile_urls)

            # Step 3: Store
            if self.db_url:
                self.store_profiles(profiles)

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}")
            self.stats.errors.append(str(e))

        self.stats.end_time = datetime.now()

        # Print summary
        duration = (self.stats.end_time - self.stats.start_time).total_seconds()

        logger.info("")
        logger.info("=" * 60)
        logger.info("📊 PILOT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"   Duration: {duration:.1f} seconds")
        logger.info(f"   Discovered: {self.stats.discovery_profiles}")
        logger.info(f"   Extracted: {self.stats.extracted_profiles}")
        logger.info(f"   Stored: {self.stats.stored_profiles}")
        logger.info(f"   Failed: {self.stats.failed_extractions}")
        logger.info(f"   Estimated cost: ${self.stats.estimated_cost:.2f}")
        if self.stats.errors:
            logger.info(f"   Errors: {len(self.stats.errors)}")
            for error in self.stats.errors[:5]:
                logger.info(f"      - {error}")
        logger.info("=" * 60)

        return self.stats


def main():
    """Run pilot with command line interface"""
    import argparse

    parser = argparse.ArgumentParser(description="Apify LinkedIn Pipeline for Ella Sourcing")
    parser.add_argument('--query', default="Software Engineer OR Desenvolvedor",
                        help="Search query (default: Software Engineer OR Desenvolvedor)")
    parser.add_argument('--location', default="São Paulo, Brazil",
                        help="Location filter (default: São Paulo, Brazil)")
    parser.add_argument('--max', type=int, default=100,
                        help="Maximum profiles to process (default: 100)")
    parser.add_argument('--discover-only', action='store_true',
                        help="Only run discovery step (cheaper)")

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🔗 ELLA SOURCING - LINKEDIN PIPELINE")
    print("=" * 60)
    print(f"Query: {args.query}")
    print(f"Location: {args.location}")
    print(f"Max profiles: {args.max}")
    print("=" * 60 + "\n")

    pipeline = ApifyLinkedInPipeline()

    if args.discover_only:
        results = pipeline.discover_profiles(
            search_query=args.query,
            locations=[args.location],
            max_items=args.max
        )
        print(f"\n✅ Discovered {len(results)} profiles")
    else:
        stats = pipeline.run_pilot(
            search_query=args.query,
            location=args.location,
            max_profiles=args.max
        )
        print(f"\n✅ Pipeline complete. Estimated cost: ${stats.estimated_cost:.2f}")


if __name__ == "__main__":
    main()
