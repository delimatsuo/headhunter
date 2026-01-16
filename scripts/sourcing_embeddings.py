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
from typing import Dict, List, Optional
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
    Embedding pipeline using Gemini gemini-embedding-001
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
        self.stats = EmbeddingStats()

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

    def get_candidates_to_embed(self, limit: int = None) -> List[Dict]:
        """Get candidates with enrichment but without embeddings"""
        conn = self.connect_db()
        cur = conn.cursor()

        query = """
            SELECT c.id, c.first_name, c.last_name, c.headline,
                   c.location, c.summary, c.intelligent_analysis
            FROM sourcing.candidates c
            LEFT JOIN sourcing.embeddings e ON c.id = e.candidate_id
            WHERE c.intelligent_analysis IS NOT NULL
              AND e.id IS NULL
            ORDER BY c.id
        """
        if limit:
            query += f" LIMIT {limit}"

        cur.execute(query)
        columns = ['id', 'first_name', 'last_name', 'headline',
                   'location', 'summary', 'intelligent_analysis']
        candidates = [dict(zip(columns, row)) for row in cur.fetchall()]

        return candidates

    def build_embedding_text(self, candidate: Dict) -> str:
        """Build text for embedding from candidate data"""
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
        if analysis:
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

    def save_embedding(self, candidate_id: int, embedding: List[float]):
        """Save embedding to database"""
        conn = self.connect_db()
        cur = conn.cursor()

        # Convert to PostgreSQL vector format
        vector_str = '[' + ','.join(str(x) for x in embedding) + ']'

        cur.execute("""
            INSERT INTO sourcing.embeddings (candidate_id, embedding, model_version)
            VALUES (%s, %s::vector, %s)
            ON CONFLICT (candidate_id) DO UPDATE
            SET embedding = EXCLUDED.embedding,
                model_version = EXCLUDED.model_version,
                created_at = NOW()
        """, (candidate_id, vector_str, 'gemini-embedding-001'))

        conn.commit()

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


def main():
    parser = argparse.ArgumentParser(description='Generate embeddings for sourcing candidates')
    parser.add_argument('--batch-size', type=int, default=50, help='Candidates per batch')
    parser.add_argument('--delay', type=float, default=0.1, help='Delay between API calls')
    parser.add_argument('--limit', type=int, help='Limit number of candidates')
    parser.add_argument('--dry-run', action='store_true', help='Run without saving')

    args = parser.parse_args()

    try:
        pipeline = GeminiEmbeddingPipeline()
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
