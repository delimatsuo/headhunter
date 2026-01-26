#!/usr/bin/env python3
"""
Gemini Embedding Generator for Ella Sourcing
Generates vector embeddings for semantic search on enriched candidates
"""

import json
import os
import time
import argparse
import psycopg2
from psycopg2 import pool
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import logging
from urllib.parse import quote_plus
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class EmbeddingStats:
    """Track embedding statistics"""
    total_candidates: int = 0
    embedded: int = 0
    skipped: int = 0
    failed: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[Dict] = field(default_factory=list)


class GeminiEmbeddingPipeline:
    """
    Embedding pipeline using Vertex AI text-embedding-004
    """

    # Model configuration
    MODEL_NAME = 'models/text-embedding-004'
    EMBEDDING_DIM = 768  # text-embedding-004 produces 768-dim vectors

    def __init__(self, api_key: str = None, db_url: str = None):
        """Initialize pipeline with Gemini API and database connection"""

        # Initialize Gemini
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not set")

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.genai = genai
            logger.info(f"✅ Initialized Gemini Embeddings ({self.MODEL_NAME})")
        except ImportError:
            raise ImportError("google-generativeai not installed")

        # Initialize database connection
        self.db_url = db_url or os.getenv('DATABASE_URL')
        if not self.db_url:
            password = self._get_db_password()
            self.db_url = f"postgresql://hh_app:{quote_plus(password)}@136.113.28.239:5432/headhunter"

        self.conn = None
        self.conn_pool = None
        self.stats = EmbeddingStats()
        self._lock = threading.Lock()
        self._api_semaphore = threading.Semaphore(2)  # Limit concurrent API calls

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

    def init_pool(self, min_conn: int = 2, max_conn: int = 10):
        """Initialize connection pool for parallel processing"""
        if self.conn_pool is None:
            self.conn_pool = pool.ThreadedConnectionPool(
                min_conn, max_conn, self.db_url, connect_timeout=30
            )
            logger.info(f"✅ Initialized connection pool (min={min_conn}, max={max_conn})")
        return self.conn_pool

    def close_db(self):
        """Close database connection and pool"""
        if self.conn and not self.conn.closed:
            self.conn.close()
        if self.conn_pool:
            self.conn_pool.closeall()
            logger.info("Connection pool closed")
        else:
            logger.info("Database connection closed")

    def get_candidates_to_embed(self, limit: int = None) -> List[Dict]:
        """Get candidates with enrichment but without embeddings, including company context"""
        conn = self.connect_db()
        cur = conn.cursor()

        # Query with company context from experience records
        query = """
            WITH company_context AS (
                SELECT
                    e.candidate_id,
                    array_agg(DISTINCT e.company_industry) FILTER (WHERE e.company_industry IS NOT NULL) as industries,
                    array_agg(DISTINCT co.company_tier) FILTER (WHERE co.company_tier IS NOT NULL) as company_tiers,
                    array_agg(DISTINCT co.employee_range) FILTER (WHERE co.employee_range IS NOT NULL) as company_sizes,
                    jsonb_agg(DISTINCT e.company_tech_stack) FILTER (WHERE e.company_tech_stack IS NOT NULL) as tech_stacks_exp,
                    jsonb_agg(DISTINCT co.tech_stack) FILTER (WHERE co.tech_stack IS NOT NULL) as tech_stacks_co
                FROM sourcing.experience e
                LEFT JOIN sourcing.companies co ON co.id = e.company_id
                GROUP BY e.candidate_id
            )
            SELECT c.id, c.first_name, c.last_name, c.headline,
                   c.location, c.summary, c.intelligent_analysis,
                   cc.industries, cc.company_tiers, cc.company_sizes,
                   cc.tech_stacks_exp, cc.tech_stacks_co
            FROM sourcing.candidates c
            LEFT JOIN sourcing.embeddings e ON c.id = e.candidate_id
            LEFT JOIN company_context cc ON cc.candidate_id = c.id
            WHERE c.intelligent_analysis IS NOT NULL
              AND e.id IS NULL
            ORDER BY c.id
        """
        if limit:
            query += f" LIMIT {limit}"

        cur.execute(query)
        columns = ['id', 'first_name', 'last_name', 'headline',
                   'location', 'summary', 'intelligent_analysis',
                   'industries', 'company_tiers', 'company_sizes',
                   'tech_stacks_exp', 'tech_stacks_co']
        candidates = [dict(zip(columns, row)) for row in cur.fetchall()]

        return candidates

    def _extract_tech_stack(self, tech_stacks: List) -> Dict[str, set]:
        """Extract and deduplicate tech stack items from JSONB arrays"""
        result = {
            'languages': set(),
            'frameworks': set(),
            'cloud': set(),
            'databases': set()
        }

        if not tech_stacks:
            return result

        for stack in tech_stacks:
            if not stack or not isinstance(stack, dict):
                continue
            for key in result.keys():
                items = stack.get(key, [])
                if items and isinstance(items, list):
                    result[key].update(items)

        return result

    def build_embedding_text(self, candidate: Dict) -> str:
        """Build text for embedding from candidate data, including company context"""
        parts = []

        # Basic info
        name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()
        if name:
            parts.append(f"Name: {name}")

        if candidate.get('headline'):
            parts.append(f"Headline: {candidate['headline']}")

        if candidate.get('location'):
            parts.append(f"Location: {candidate['location']}")

        if candidate.get('summary'):
            # Truncate summary to avoid overly long text
            summary = candidate['summary'][:500]
            parts.append(f"Summary: {summary}")

        # Enriched data
        analysis = candidate.get('intelligent_analysis')
        if analysis and isinstance(analysis, dict):
            if analysis.get('level'):
                parts.append(f"Level: {analysis['level']}")

            if analysis.get('years'):
                parts.append(f"Years of experience: {analysis['years']}")

            if analysis.get('skills'):
                skills = ', '.join(analysis['skills'][:10])
                parts.append(f"Skills: {skills}")

            if analysis.get('companies'):
                companies = ', '.join(analysis['companies'][:5])
                parts.append(f"Companies: {companies}")

            if analysis.get('tier'):
                parts.append(f"Company tier: {analysis['tier']}")

            if analysis.get('strengths'):
                strengths = ', '.join(analysis['strengths'][:5])
                parts.append(f"Strengths: {strengths}")

            if analysis.get('roles'):
                roles = ', '.join(analysis['roles'][:5])
                parts.append(f"Best fit roles: {roles}")

            if analysis.get('summary'):
                parts.append(f"AI Summary: {analysis['summary']}")

        # Company context from experience records
        industries = candidate.get('industries')
        if industries:
            # Filter out None and empty values
            industries = [i for i in industries if i]
            if industries:
                parts.append(f"Industries: {', '.join(industries[:5])}")

        company_tiers = candidate.get('company_tiers')
        if company_tiers:
            # Filter out None and empty values
            company_tiers = [t for t in company_tiers if t]
            if company_tiers:
                parts.append(f"Company tiers worked at: {', '.join(company_tiers)}")

        company_sizes = candidate.get('company_sizes')
        if company_sizes:
            # Filter out None and empty values
            company_sizes = [s for s in company_sizes if s]
            if company_sizes:
                parts.append(f"Company sizes: {', '.join(company_sizes[:3])}")

        # Aggregate tech stack from both experience and company tables
        all_tech_stacks = []
        if candidate.get('tech_stacks_exp'):
            all_tech_stacks.extend(candidate['tech_stacks_exp'])
        if candidate.get('tech_stacks_co'):
            all_tech_stacks.extend(candidate['tech_stacks_co'])

        if all_tech_stacks:
            tech_stack = self._extract_tech_stack(all_tech_stacks)

            if tech_stack['languages']:
                parts.append(f"Programming languages: {', '.join(sorted(tech_stack['languages'])[:8])}")

            if tech_stack['frameworks']:
                parts.append(f"Frameworks: {', '.join(sorted(tech_stack['frameworks'])[:8])}")

            if tech_stack['cloud']:
                parts.append(f"Cloud platforms: {', '.join(sorted(tech_stack['cloud'])[:5])}")

            if tech_stack['databases']:
                parts.append(f"Databases: {', '.join(sorted(tech_stack['databases'])[:5])}")

        return '\n'.join(parts)

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using Gemini"""
        try:
            result = self.genai.embed_content(
                model=self.MODEL_NAME,
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None

    def save_embedding(self, candidate_id: int, embedding: List[float], retries: int = 3):
        """Save embedding to database with retry logic"""
        vector_str = '[' + ','.join(str(x) for x in embedding) + ']'

        for attempt in range(retries):
            try:
                conn = self.connect_db()
                cur = conn.cursor()

                cur.execute("""
                    INSERT INTO sourcing.embeddings (candidate_id, embedding, model_version)
                    VALUES (%s, %s::vector, %s)
                    ON CONFLICT (candidate_id) DO UPDATE
                    SET embedding = EXCLUDED.embedding,
                        model_version = EXCLUDED.model_version,
                        created_at = NOW()
                """, (candidate_id, vector_str, 'text-embedding-004'))  # Must match MODEL_NAME

                conn.commit()
                return  # Success
            except psycopg2.OperationalError as e:
                logger.warning(f"DB connection error (attempt {attempt + 1}/{retries}): {e}")
                # Force reconnect
                if self.conn:
                    try:
                        self.conn.close()
                    except:
                        pass
                self.conn = None
                time.sleep(2 ** attempt)  # Exponential backoff

        raise Exception(f"Failed to save embedding for candidate {candidate_id} after {retries} retries")

    def save_embedding_pooled(self, candidate_id: int, embedding: List[float], retries: int = 3):
        """Save embedding using connection pool (thread-safe)"""
        vector_str = '[' + ','.join(str(x) for x in embedding) + ']'

        for attempt in range(retries):
            conn = None
            try:
                conn = self.conn_pool.getconn()
                cur = conn.cursor()

                cur.execute("""
                    INSERT INTO sourcing.embeddings (candidate_id, embedding, model_version)
                    VALUES (%s, %s::vector, %s)
                    ON CONFLICT (candidate_id) DO UPDATE
                    SET embedding = EXCLUDED.embedding,
                        model_version = EXCLUDED.model_version,
                        created_at = NOW()
                """, (candidate_id, vector_str, 'text-embedding-004'))  # Must match MODEL_NAME

                conn.commit()
                return True
            except Exception as e:
                if conn:
                    conn.rollback()
                logger.warning(f"DB error for candidate {candidate_id} (attempt {attempt + 1}): {e}")
                time.sleep(0.5 * (attempt + 1))
            finally:
                if conn:
                    self.conn_pool.putconn(conn)

        return False

    def process_candidate(self, candidate: Dict, max_retries: int = 3) -> Tuple[int, bool, str]:
        """Process a single candidate - generate and save embedding (thread-safe)"""
        candidate_id = candidate['id']
        name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()

        try:
            # Build text
            text = self.build_embedding_text(candidate)
            if len(text) < 50:
                return (candidate_id, False, "insufficient text")

            # Generate embedding with semaphore and retry for rate limits
            embedding = None
            for attempt in range(max_retries):
                with self._api_semaphore:  # Limit concurrent API calls
                    embedding = self.generate_embedding(text)
                if embedding:
                    break
                # Exponential backoff for rate limit
                time.sleep(1.0 * (2 ** attempt))

            if not embedding:
                return (candidate_id, False, "embedding generation failed")

            # Save to database
            if self.save_embedding_pooled(candidate_id, embedding):
                return (candidate_id, True, name)
            else:
                return (candidate_id, False, "database save failed")

        except Exception as e:
            return (candidate_id, False, str(e))

    def run(self, batch_size: int = 50, delay: float = 0.1, limit: int = None, dry_run: bool = False):
        """
        Run the embedding pipeline

        Args:
            batch_size: Number of candidates per batch
            delay: Seconds to wait between API calls
            limit: Maximum number of candidates to process
            dry_run: If True, don't save to database
        """

        self.stats = EmbeddingStats()
        self.stats.start_time = datetime.now()

        # Get candidates to process
        candidates = self.get_candidates_to_embed(limit)
        self.stats.total_candidates = len(candidates)

        if not candidates:
            logger.info("No candidates to embed. All done!")
            return self.stats

        logger.info(f"🚀 Starting embedding of {len(candidates)} candidates")
        logger.info(f"   Batch size: {batch_size}, Delay: {delay}s")

        try:
            for i, candidate in enumerate(candidates):
                # Build embedding text
                text = self.build_embedding_text(candidate)

                if len(text) < 50:
                    logger.warning(f"Skipping candidate {candidate['id']}: insufficient text")
                    self.stats.skipped += 1
                    continue

                # Generate embedding
                embedding = self.generate_embedding(text)

                if embedding:
                    if not dry_run:
                        self.save_embedding(candidate['id'], embedding)
                    self.stats.embedded += 1

                    # Log sample output at 1, then every 100
                    if self.stats.embedded == 1 or self.stats.embedded % 100 == 0:
                        name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()
                        logger.info(f"[{i+1}/{len(candidates)}] Embedded: {name}")
                else:
                    self.stats.failed += 1
                    self.stats.errors.append({
                        'candidate_id': candidate['id'],
                        'error': 'Failed to generate embedding',
                        'timestamp': datetime.now().isoformat()
                    })

                # Progress update every batch
                if (i + 1) % batch_size == 0:
                    logger.info(f"📊 Progress: {i+1}/{len(candidates)} | "
                               f"Embedded: {self.stats.embedded} | "
                               f"Failed: {self.stats.failed}")

                    # Commit batch
                    if not dry_run:
                        self.conn.commit()

                # Rate limiting (Gemini embeddings are fast, minimal delay needed)
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

            # Print summary
            duration = (self.stats.end_time - self.stats.start_time).total_seconds()
            logger.info("\n" + "=" * 60)
            logger.info("EMBEDDING COMPLETE")
            logger.info("=" * 60)
            logger.info(f"Total candidates: {self.stats.total_candidates}")
            logger.info(f"Embedded: {self.stats.embedded}")
            logger.info(f"Skipped: {self.stats.skipped}")
            logger.info(f"Failed: {self.stats.failed}")
            logger.info(f"Duration: {duration:.1f} seconds")
            logger.info(f"Rate: {self.stats.embedded / max(duration, 1) * 60:.1f} per minute")
            logger.info("=" * 60)

            self.close_db()

        return self.stats

    def run_parallel(self, workers: int = 8, limit: int = None):
        """
        Run the embedding pipeline with parallel processing

        Args:
            workers: Number of parallel workers (threads)
            limit: Maximum number of candidates to process
        """

        self.stats = EmbeddingStats()
        self.stats.start_time = datetime.now()

        # Initialize connection pool
        self.init_pool(min_conn=workers, max_conn=workers + 2)

        # Get candidates to process
        candidates = self.get_candidates_to_embed(limit)
        self.stats.total_candidates = len(candidates)

        if not candidates:
            logger.info("No candidates to embed. All done!")
            return self.stats

        logger.info(f"🚀 Starting PARALLEL embedding of {len(candidates)} candidates")
        logger.info(f"   Workers: {workers}")

        processed = 0
        batch_size = 100  # Process in batches to manage rate limits

        try:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                # Process in batches to respect API rate limits
                for batch_start in range(0, len(candidates), batch_size):
                    batch = candidates[batch_start:batch_start + batch_size]

                    # Submit batch tasks
                    futures = {
                        executor.submit(self.process_candidate, c): c
                        for c in batch
                    }

                    # Process batch results
                    for future in as_completed(futures):
                        candidate_id, success, msg = future.result()
                        processed += 1

                        if success:
                            with self._lock:
                                self.stats.embedded += 1
                        else:
                            if msg == "insufficient text":
                                with self._lock:
                                    self.stats.skipped += 1
                            else:
                                with self._lock:
                                    self.stats.failed += 1
                                    self.stats.errors.append({
                                        'candidate_id': candidate_id,
                                        'error': msg,
                                        'timestamp': datetime.now().isoformat()
                                    })

                        # Progress logging
                        if self.stats.embedded == 1 or self.stats.embedded % 100 == 0:
                            elapsed = (datetime.now() - self.stats.start_time).total_seconds()
                            rate = self.stats.embedded / max(elapsed, 1) * 60
                            logger.info(f"📊 Progress: {processed}/{len(candidates)} | "
                                       f"Embedded: {self.stats.embedded} | "
                                       f"Failed: {self.stats.failed} | "
                                       f"Rate: {rate:.0f}/min")

                    # Small delay between batches to respect rate limits
                    if batch_start + batch_size < len(candidates):
                        time.sleep(0.5)

        except KeyboardInterrupt:
            logger.info("\n⚠️ Interrupted by user.")

        finally:
            self.stats.end_time = datetime.now()

            # Print summary
            duration = (self.stats.end_time - self.stats.start_time).total_seconds()
            logger.info("\n" + "=" * 60)
            logger.info("PARALLEL EMBEDDING COMPLETE")
            logger.info("=" * 60)
            logger.info(f"Total candidates: {self.stats.total_candidates}")
            logger.info(f"Embedded: {self.stats.embedded}")
            logger.info(f"Skipped: {self.stats.skipped}")
            logger.info(f"Failed: {self.stats.failed}")
            logger.info(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
            logger.info(f"Rate: {self.stats.embedded / max(duration, 1) * 60:.1f} per minute")
            logger.info(f"Speedup: ~{workers}x vs sequential")
            logger.info("=" * 60)

            self.close_db()

        return self.stats


def show_status(pipeline: GeminiEmbeddingPipeline):
    """Show current embedding status"""
    conn = pipeline.connect_db()
    cur = conn.cursor()

    # Get counts
    cur.execute("SELECT COUNT(*) FROM sourcing.candidates WHERE intelligent_analysis IS NOT NULL")
    enriched = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM sourcing.embeddings")
    embedded = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(DISTINCT c.id)
        FROM sourcing.candidates c
        LEFT JOIN sourcing.embeddings e ON c.id = e.candidate_id
        WHERE c.intelligent_analysis IS NOT NULL AND e.id IS NULL
    """)
    pending = cur.fetchone()[0]

    # Get company context coverage
    cur.execute("""
        SELECT
            COUNT(DISTINCT e.candidate_id) as candidates_with_exp,
            COUNT(DISTINCT CASE WHEN e.company_industry IS NOT NULL THEN e.candidate_id END) as with_industry,
            COUNT(DISTINCT CASE WHEN co.company_tier IS NOT NULL THEN e.candidate_id END) as with_tier,
            COUNT(DISTINCT CASE WHEN co.tech_stack IS NOT NULL THEN e.candidate_id END) as with_tech
        FROM sourcing.experience e
        LEFT JOIN sourcing.companies co ON co.id = e.company_id
    """)
    exp_stats = cur.fetchone()

    print("\n" + "=" * 60)
    print("EMBEDDING STATUS")
    print("=" * 60)
    print(f"Enriched candidates: {enriched:,}")
    print(f"Already embedded:    {embedded:,}")
    print(f"Pending:             {pending:,}")
    print(f"\nCompany Context Coverage:")
    print(f"  Candidates with experience: {exp_stats[0]:,}")
    print(f"  With industry data:         {exp_stats[1]:,}")
    print(f"  With company tier:          {exp_stats[2]:,}")
    print(f"  With tech stack:            {exp_stats[3]:,}")
    print("=" * 60)


def show_sample(pipeline: GeminiEmbeddingPipeline, num_samples: int = 3):
    """Show sample embedding text to verify company context"""
    candidates = pipeline.get_candidates_to_embed(limit=num_samples)

    if not candidates:
        print("No candidates to embed!")
        return

    for i, candidate in enumerate(candidates):
        name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()
        text = pipeline.build_embedding_text(candidate)

        print("\n" + "=" * 70)
        print(f"SAMPLE {i+1}: {name} (ID: {candidate['id']})")
        print("=" * 70)
        print("\n--- Company Context Data ---")
        print(f"Industries:     {candidate.get('industries')}")
        print(f"Company tiers:  {candidate.get('company_tiers')}")
        print(f"Company sizes:  {candidate.get('company_sizes')}")
        print(f"Tech stacks (exp): {candidate.get('tech_stacks_exp')}")
        print(f"Tech stacks (co):  {candidate.get('tech_stacks_co')}")
        print("\n--- Embedding Text ---")
        print(text)
        print(f"\n[Text length: {len(text)} characters]")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Generate embeddings for sourcing candidates')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Status command
    subparsers.add_parser('status', help='Show embedding status')

    # Sample command
    sample_parser = subparsers.add_parser('sample', help='Show sample embedding text')
    sample_parser.add_argument('--num', type=int, default=3, help='Number of samples to show')

    # Run command (default)
    run_parser = subparsers.add_parser('run', help='Run embedding generation')
    run_parser.add_argument('--batch-size', type=int, default=50, help='Candidates per batch')
    run_parser.add_argument('--delay', type=float, default=0.1, help='Delay between API calls')
    run_parser.add_argument('--limit', type=int, help='Limit number of candidates')
    run_parser.add_argument('--dry-run', action='store_true', help='Run without saving')

    # Add default options for backwards compatibility
    parser.add_argument('--batch-size', type=int, default=50, help='Candidates per batch')
    parser.add_argument('--delay', type=float, default=0.1, help='Delay between API calls')
    parser.add_argument('--limit', type=int, help='Limit number of candidates')
    parser.add_argument('--dry-run', action='store_true', help='Run without saving')
    parser.add_argument('--parallel', action='store_true', help='Run with parallel processing')
    parser.add_argument('--workers', type=int, default=8, help='Number of parallel workers (default: 8)')

    args = parser.parse_args()

    try:
        pipeline = GeminiEmbeddingPipeline()

        if args.command == 'status':
            show_status(pipeline)
        elif args.command == 'sample':
            show_sample(pipeline, args.num)
        elif getattr(args, 'parallel', False):
            # Parallel mode (explicit --parallel flag required)
            stats = pipeline.run_parallel(
                workers=args.workers,
                limit=args.limit
            )

            if stats.failed > stats.embedded:
                exit(1)
        else:
            # Default: run sequential embedding generation
            stats = pipeline.run(
                batch_size=args.batch_size,
                delay=args.delay,
                limit=args.limit,
                dry_run=args.dry_run
            )

            if stats.failed > stats.embedded:
                exit(1)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


if __name__ == '__main__':
    main()
