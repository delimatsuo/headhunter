#!/usr/bin/env python3
"""
Gemini 2.5 Flash Enrichment Pipeline for Ella Sourcing
Enriches LinkedIn profiles with AI-powered recruiter intelligence
"""

import json
import os
import time
import argparse
import psycopg2
from psycopg2.extras import Json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import logging
from urllib.parse import quote_plus
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
class EnrichmentStats:
    """Track enrichment statistics"""
    total_candidates: int = 0
    enriched: int = 0
    skipped: int = 0
    failed: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost: float = 0.0
    errors: List[Dict] = field(default_factory=list)


ENRICHMENT_PROMPT = """Analyze this Brazilian software engineer's LinkedIn profile as a recruiter.

Profile: {first_name} {last_name}
Headline: {headline}
Location: {location}
Summary: {summary}

Work History:
{experience_formatted}

Return JSON with these fields:
- level: Junior/Mid/Senior/Lead/Manager/Director (string)
- years: years of experience (number)
- trajectory: technical/management/hybrid (string)
- skills: top 5 skills (array of strings)
- companies: notable company names (array of strings)
- tier: FAANG/unicorn/enterprise/startup/agency (string)
- strengths: 2-3 key strengths (array of strings)
- roles: best fit job titles (array of strings)
- salary_min: min monthly BRL (number)
- salary_max: max monthly BRL (number)
- summary: one sentence pitch (string)

Output only valid JSON."""


class GeminiEnrichmentPipeline:
    """
    Enrichment pipeline using Gemini 2.5 Flash
    """

    # Pricing per 1M tokens (January 2026)
    INPUT_COST_PER_M = 0.30   # $0.30 per 1M input tokens
    OUTPUT_COST_PER_M = 2.50  # $2.50 per 1M output tokens

    def __init__(self, api_key: str = None, db_url: str = None):
        """Initialize pipeline with Gemini API and database connection"""

        # Initialize Gemini
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not set. Get one from https://aistudio.google.com/apikey")

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
            logger.info("✅ Initialized Gemini 2.5 Flash")
        except ImportError:
            raise ImportError("google-generativeai not installed. Run: pip install google-generativeai")

        # Initialize database connection
        self.db_url = db_url or os.getenv('DATABASE_URL')
        if not self.db_url:
            # Build from secrets
            password = self._get_db_password()
            self.db_url = f"postgresql://hh_app:{quote_plus(password)}@136.113.28.239:5432/headhunter"

        self.conn = None
        self.stats = EnrichmentStats()

    def _get_db_password(self) -> str:
        """Retrieve database password from GCP Secret Manager"""
        import subprocess
        result = subprocess.run(
            ['gcloud', 'secrets', 'versions', 'access', 'latest',
             '--secret=db-primary-password', '--project=headhunter-ai-0088'],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise ValueError(f"Failed to get DB password: {result.stderr}")
        return result.stdout.strip()

    def connect_db(self):
        """Establish database connection"""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(self.db_url, connect_timeout=30)
            logger.info("✅ Connected to Cloud SQL database")
        return self.conn

    def close_db(self):
        """Close database connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()
            logger.info("Database connection closed")

    def get_candidates_to_enrich(self, limit: int = None) -> List[Dict]:
        """Get candidates that haven't been enriched yet"""
        conn = self.connect_db()
        cur = conn.cursor()

        query = """
            SELECT c.id, c.linkedin_url, c.first_name, c.last_name,
                   c.headline, c.location, c.summary
            FROM sourcing.candidates c
            WHERE c.intelligent_analysis IS NULL
            ORDER BY c.id
        """
        if limit:
            query += f" LIMIT {limit}"

        cur.execute(query)
        columns = ['id', 'linkedin_url', 'first_name', 'last_name',
                   'headline', 'location', 'summary']
        candidates = [dict(zip(columns, row)) for row in cur.fetchall()]

        return candidates

    def get_candidate_experience(self, candidate_id: int) -> List[Dict]:
        """Get work history for a candidate"""
        conn = self.connect_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT company_name, title, location, description, is_current
            FROM sourcing.experience
            WHERE candidate_id = %s
            ORDER BY is_current DESC, id DESC
        """, (candidate_id,))

        columns = ['company_name', 'title', 'location', 'description', 'is_current']
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    def format_experience(self, experiences: List[Dict]) -> str:
        """Format experience list for prompt"""
        if not experiences:
            return "No work history available"

        formatted = []
        for exp in experiences[:10]:  # Limit to 10 positions
            company = exp.get('company_name') or 'Unknown Company'
            title = exp.get('title') or 'Unknown Role'
            entry = f"- {title} at {company}"

            if exp.get('is_current'):
                entry += " (Current)"

            if exp.get('location'):
                entry += f" | {exp['location']}"

            if exp.get('description'):
                desc = exp['description'][:300].replace('\n', ' ')
                entry += f"\n  {desc}..."

            formatted.append(entry)

        return "\n".join(formatted)

    def enrich_candidate(self, candidate: Dict) -> Optional[Dict]:
        """Enrich a single candidate using Gemini 2.5 Flash"""

        candidate_id = candidate['id']

        try:
            # Get experience
            experiences = self.get_candidate_experience(candidate_id)
            experience_formatted = self.format_experience(experiences)

            # Build prompt
            prompt = ENRICHMENT_PROMPT.format(
                first_name=candidate.get('first_name') or '',
                last_name=candidate.get('last_name') or '',
                headline=candidate.get('headline') or 'No headline',
                location=candidate.get('location') or 'Brazil',
                summary=candidate.get('summary') or 'No summary available',
                experience_formatted=experience_formatted
            )

            # Call Gemini with JSON mode
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.2,
                    'top_p': 0.8,
                    'max_output_tokens': 4000,
                    'response_mime_type': 'application/json',
                }
            )

            # Track tokens
            if hasattr(response, 'usage_metadata'):
                self.stats.total_input_tokens += response.usage_metadata.prompt_token_count
                self.stats.total_output_tokens += response.usage_metadata.candidates_token_count

            # Check for response completion
            if hasattr(response, 'candidates') and response.candidates:
                finish_reason = response.candidates[0].finish_reason
                if finish_reason and finish_reason.name != 'STOP':
                    logger.warning(f"  Response truncated: {finish_reason.name}")

            # Parse JSON response
            response_text = response.text.strip()

            # Clean up markdown if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            response_text = response_text.strip()

            analysis = json.loads(response_text)

            # Validate required fields (simplified schema)
            required_fields = ['level', 'years', 'skills', 'summary']
            for field in required_fields:
                if field not in analysis:
                    raise ValueError(f"Missing required field: {field}")

            return analysis

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error for candidate {candidate_id}: {e}")
            logger.debug(f"Raw response: {response_text[:500]}...")

            # Try to repair common JSON issues
            repaired = self._repair_json(response_text)
            if repaired:
                try:
                    analysis = json.loads(repaired)
                    logger.info(f"  ✓ JSON repaired successfully")
                    return analysis
                except json.JSONDecodeError:
                    pass

            self.stats.errors.append({
                'candidate_id': candidate_id,
                'error': f"JSON parse error: {str(e)}",
                'raw_response': response_text[:500],
                'timestamp': datetime.now().isoformat()
            })
            return None

        except Exception as e:
            logger.warning(f"Error enriching candidate {candidate_id}: {e}")
            self.stats.errors.append({
                'candidate_id': candidate_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return None

    def save_enrichment(self, candidate_id: int, analysis: Dict):
        """Save enrichment result to database"""
        conn = self.connect_db()
        cur = conn.cursor()

        cur.execute("""
            UPDATE sourcing.candidates
            SET intelligent_analysis = %s,
                enriched_at = NOW()
            WHERE id = %s
        """, (Json(analysis), candidate_id))

        conn.commit()

    def calculate_cost(self) -> float:
        """Calculate estimated cost based on token usage"""
        input_cost = (self.stats.total_input_tokens / 1_000_000) * self.INPUT_COST_PER_M
        output_cost = (self.stats.total_output_tokens / 1_000_000) * self.OUTPUT_COST_PER_M
        return input_cost + output_cost

    def _repair_json(self, text: str) -> Optional[str]:
        """Attempt to repair malformed JSON"""
        import re

        # Remove any markdown formatting
        text = re.sub(r'^```json?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

        # Fix trailing commas before closing braces/brackets
        text = re.sub(r',(\s*[}\]])', r'\1', text)

        # Fix missing quotes around property names
        text = re.sub(r'(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)

        # Fix single quotes to double quotes
        # Be careful not to mess up apostrophes in text
        # Only fix quotes that look like they're around property names/values
        text = re.sub(r"'([^']*)'(\s*[,}\]])", r'"\1"\2', text)

        # Truncate if JSON ends abruptly (find last complete structure)
        # Count braces/brackets
        brace_count = 0
        bracket_count = 0
        last_valid_pos = 0

        for i, char in enumerate(text):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and bracket_count == 0:
                    last_valid_pos = i + 1
            elif char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1

        if brace_count != 0 or bracket_count != 0:
            # JSON is incomplete, try to close it
            text = text[:last_valid_pos] if last_valid_pos > 0 else text
            text = text.rstrip(',\n\t ')
            while brace_count > 0:
                text += '}'
                brace_count -= 1
            while bracket_count > 0:
                text += ']'
                bracket_count -= 1

        return text if text else None

    def run(self, batch_size: int = 10, delay: float = 4.0, max_cost: float = 10.0,
            limit: int = None, dry_run: bool = False):
        """
        Run the enrichment pipeline

        Args:
            batch_size: Number of candidates per batch
            delay: Seconds to wait between API calls (for rate limiting)
            max_cost: Stop if estimated cost exceeds this amount
            limit: Maximum number of candidates to process
            dry_run: If True, don't save to database
        """

        self.stats = EnrichmentStats()
        self.stats.start_time = datetime.now()

        # Get candidates to process
        candidates = self.get_candidates_to_enrich(limit)
        self.stats.total_candidates = len(candidates)

        if not candidates:
            logger.info("No candidates to enrich. All done!")
            return self.stats

        logger.info(f"🚀 Starting enrichment of {len(candidates)} candidates")
        logger.info(f"   Batch size: {batch_size}, Delay: {delay}s")
        logger.info(f"   Max cost: ${max_cost:.2f}")

        try:
            for i, candidate in enumerate(candidates):
                # Check cost limit
                current_cost = self.calculate_cost()
                if current_cost >= max_cost:
                    logger.warning(f"⚠️ Cost limit reached: ${current_cost:.2f} >= ${max_cost:.2f}")
                    break

                # Process candidate
                name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()
                logger.info(f"[{i+1}/{len(candidates)}] Enriching: {name}")

                analysis = self.enrich_candidate(candidate)

                if analysis:
                    if not dry_run:
                        self.save_enrichment(candidate['id'], analysis)
                    self.stats.enriched += 1

                    # Log sample output every 50 candidates
                    if self.stats.enriched % 50 == 1:
                        summary = analysis.get('executive_summary', '')[:100]
                        logger.info(f"   Summary: {summary}...")
                else:
                    self.stats.failed += 1

                # Progress update every batch
                if (i + 1) % batch_size == 0:
                    cost = self.calculate_cost()
                    logger.info(f"📊 Progress: {i+1}/{len(candidates)} | "
                               f"Enriched: {self.stats.enriched} | "
                               f"Failed: {self.stats.failed} | "
                               f"Cost: ${cost:.4f}")

                    # Commit batch
                    if not dry_run:
                        self.conn.commit()

                # Rate limiting
                time.sleep(delay)

            # Final commit
            if not dry_run and self.conn:
                self.conn.commit()

        except KeyboardInterrupt:
            logger.info("\n⚠️ Interrupted by user. Saving progress...")
            if not dry_run and self.conn:
                self.conn.commit()

        finally:
            self.stats.end_time = datetime.now()
            self.stats.estimated_cost = self.calculate_cost()

            # Save errors to file
            if self.stats.errors:
                errors_file = DATA_DIR / 'enrichment_errors.json'
                with open(errors_file, 'w') as f:
                    json.dump(self.stats.errors, f, indent=2)
                logger.info(f"Errors saved to {errors_file}")

            # Print summary
            duration = (self.stats.end_time - self.stats.start_time).total_seconds()
            logger.info("\n" + "=" * 60)
            logger.info("ENRICHMENT COMPLETE")
            logger.info("=" * 60)
            logger.info(f"Total candidates: {self.stats.total_candidates}")
            logger.info(f"Enriched: {self.stats.enriched}")
            logger.info(f"Failed: {self.stats.failed}")
            logger.info(f"Duration: {duration:.1f} seconds")
            logger.info(f"Input tokens: {self.stats.total_input_tokens:,}")
            logger.info(f"Output tokens: {self.stats.total_output_tokens:,}")
            logger.info(f"Estimated cost: ${self.stats.estimated_cost:.4f}")
            logger.info("=" * 60)

            self.close_db()

        return self.stats


def main():
    parser = argparse.ArgumentParser(description='Enrich sourcing candidates with Gemini 2.5 Flash')
    parser.add_argument('--batch-size', type=int, default=10, help='Candidates per batch')
    parser.add_argument('--delay', type=float, default=4.0, help='Delay between API calls (seconds)')
    parser.add_argument('--max-cost', type=float, default=10.0, help='Maximum cost in USD')
    parser.add_argument('--limit', type=int, help='Limit number of candidates to process')
    parser.add_argument('--dry-run', action='store_true', help='Run without saving to database')

    args = parser.parse_args()

    try:
        pipeline = GeminiEnrichmentPipeline()
        stats = pipeline.run(
            batch_size=args.batch_size,
            delay=args.delay,
            max_cost=args.max_cost,
            limit=args.limit,
            dry_run=args.dry_run
        )

        # Return appropriate exit code
        if stats.failed > stats.enriched:
            exit(1)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


if __name__ == '__main__':
    main()
