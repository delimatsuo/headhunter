#!/usr/bin/env python3
"""
Direct Database Embedding Fix
==============================

Bypasses hh-embed-svc and directly updates embeddings in pgvector database.
Much faster and simpler for bulk operations.

Usage:
    python3 scripts/direct_embedding_fix.py --task reembed --limit 100
    python3 scripts/direct_embedding_fix.py --task reembed  # All enriched candidates
"""

import asyncio
import json
import argparse
import os
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values
import vertexai
from vertexai.language_models import TextEmbeddingModel

# Configuration
PROJECT_ID = "headhunter-ai-0088"
LOCATION = "us-central1"
MODEL_NAME = "text-embedding-004"
ENRICHED_FILE = Path("data/enriched/enriched_candidates_full.json")
BATCH_SIZE = 50  # Process 50 at a time

# Database connection via Cloud SQL Proxy (should be running on localhost:5432)
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "headhunter"
DB_USER = "postgres"  # Or appropriate user
TENANT_ID = "tenant-alpha"


def build_searchable_profile(candidate: Dict[str, Any]) -> str:
    """
    Build searchable profile from enriched candidate data.
    Same logic as in parallel_enrichment_and_embedding.py
    """
    parts: List[str] = []

    def get_string(path: str) -> str:
        keys = path.split('.')
        value = candidate.get('intelligent_analysis', {})
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, '')
            else:
                return ''
        return str(value) if value else ''

    def get_array(path: str) -> List[str]:
        keys = path.split('.')
        value = candidate.get('intelligent_analysis', {})
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, [])
            else:
                return []
        return value if isinstance(value, list) else []

    # 1. Technical Skills
    explicit_skills = get_array('explicit_skills')
    inferred_skills = get_array('inferred_skills')
    all_skills = list(set(explicit_skills + inferred_skills))
    if all_skills:
        parts.append(f"Technical Skills: {', '.join(all_skills[:20])}")

    # 2. Current Role and Level
    current_level = get_string('career_trajectory_analysis.current_level')
    if current_level:
        parts.append(f"Level: {current_level}")

    years_exp = get_string('career_trajectory_analysis.years_experience')
    if years_exp:
        parts.append(f"Experience: {years_exp} years")

    # 3. Market Positioning
    market_segment = get_string('market_positioning.target_market_segment')
    if market_segment:
        parts.append(f"Market Segment: {market_segment}")

    # 4. Company Context
    company_context = get_array('company_context_skills')
    if company_context:
        parts.append(f"Company Skills: {', '.join(company_context[:10])}")

    # 5. Role Competencies
    role_comps = get_array('role_based_competencies')
    if role_comps:
        parts.append(f"Role Competencies: {', '.join(role_comps[:10])}")

    # 6. Recruiter Insights
    insights = get_string('recruiter_insights.key_strengths')
    if insights:
        parts.append(f"Strengths: {insights}")

    ideal_roles = get_array('recruiter_insights.ideal_roles')
    if ideal_roles:
        parts.append(f"Ideal Roles: {', '.join(ideal_roles[:5])}")

    return '\n'.join(parts)


def get_db_connection():
    """Get database connection"""
    # Try to get password from environment or secret
    password = os.getenv('PGPASSWORD', '')

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=password
    )


def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a batch of texts using VertexAI"""

    # Initialize Vertex AI
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    model = TextEmbeddingModel.from_pretrained(MODEL_NAME)

    # Generate embeddings
    embeddings = model.get_embeddings(texts)

    return [emb.values for emb in embeddings]


def process_reembedding(candidates: List[Dict[str, Any]], limit: int = None):
    """Process re-embedding of enriched candidates"""

    if limit:
        candidates = candidates[:limit]

    print(f"\n{'='*70}")
    print(f"RE-EMBEDDING {len(candidates)} ENRICHED CANDIDATES")
    print(f"{'='*70}\n")

    # Initialize database connection
    conn = get_db_connection()
    cursor = conn.cursor()

    successful = 0
    failed = 0
    start_time = datetime.now()

    try:
        # Process in batches
        for i in range(0, len(candidates), BATCH_SIZE):
            batch = candidates[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(candidates) + BATCH_SIZE - 1) // BATCH_SIZE

            print(f"Processing batch {batch_num}/{total_batches} ({len(batch)} candidates)...")

            try:
                # Build searchable profiles
                profiles = []
                candidate_ids = []

                for candidate in batch:
                    candidate_id = candidate.get('candidate_id')
                    if not candidate_id:
                        failed += 1
                        continue

                    profile = build_searchable_profile(candidate)
                    if not profile:
                        failed += 1
                        continue

                    profiles.append(profile)
                    candidate_ids.append(candidate_id)

                if not profiles:
                    continue

                # Generate embeddings
                print(f"  Generating {len(profiles)} embeddings...")
                embeddings = generate_embeddings_batch(profiles)

                # Upsert into database
                print(f"  Upserting {len(embeddings)} embeddings to database...")

                upsert_data = []
                for candidate_id, profile, embedding in zip(candidate_ids, profiles, embeddings):
                    upsert_data.append((
                        TENANT_ID,
                        str(candidate_id),
                        embedding,
                        profile,
                        json.dumps({"reembedded_at": datetime.now().isoformat(), "source": "enriched_data"}),
                        MODEL_NAME,
                        'default'
                    ))

                # Use INSERT ... ON CONFLICT UPDATE
                execute_values(
                    cursor,
                    """
                    INSERT INTO search.candidate_embeddings
                        (tenant_id, entity_id, embedding, embedding_text, metadata, model_version, chunk_type)
                    VALUES %s
                    ON CONFLICT (tenant_id, entity_id, chunk_type)
                    DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        embedding_text = EXCLUDED.embedding_text,
                        metadata = EXCLUDED.metadata,
                        model_version = EXCLUDED.model_version,
                        updated_at = NOW()
                    """,
                    upsert_data
                )

                conn.commit()
                successful += len(embeddings)
                print(f"  ✅ Batch {batch_num} complete ({successful}/{len(candidates)} total)")

            except Exception as e:
                print(f"  ❌ Batch {batch_num} failed: {str(e)[:200]}")
                failed += len(batch)
                conn.rollback()

        elapsed = (datetime.now() - start_time).total_seconds()
        rate = successful / elapsed if elapsed > 0 else 0

        print(f"\n{'='*70}")
        print(f"✅ RE-EMBEDDING COMPLETE!")
        print(f"   Successful: {successful}/{len(candidates)}")
        print(f"   Failed: {failed}")
        print(f"   Duration: {elapsed/60:.1f} minutes")
        print(f"   Rate: {rate:.1f} embeddings/second")
        print(f"{'='*70}\n")

    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Direct database embedding fix")
    parser.add_argument(
        "--task",
        choices=["reembed"],
        default="reembed",
        help="Task to run (only reembed supported for now)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of candidates to process (for testing)"
    )

    args = parser.parse_args()

    print(f"Loading enriched candidates from {ENRICHED_FILE}...")
    with open(ENRICHED_FILE, 'r') as f:
        enriched = json.load(f)

    print(f"Loaded {len(enriched)} enriched candidates")

    if args.task == "reembed":
        process_reembedding(enriched, args.limit)


if __name__ == "__main__":
    main()
