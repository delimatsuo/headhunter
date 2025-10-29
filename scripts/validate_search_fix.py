#!/usr/bin/env python3
"""
Validate Search Fix - Comprehensive Validation Script
=====================================================
Validates that the search fix is complete and working correctly.

Checks:
1. Database state (embeddings, vectors, entity_id format)
2. Hybrid search functionality
3. Multiple query patterns

Usage:
    python3 scripts/validate_search_fix.py
"""

import asyncio
import subprocess
import sys
from typing import Dict, List, Tuple
import psycopg2
import aiohttp
import json


def get_db_password() -> str:
    """Get database password from Secret Manager"""
    try:
        result = subprocess.run(
            ["gcloud", "secrets", "versions", "access", "latest",
             "--secret=db-analytics-password",
             "--project=headhunter-ai-0088"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to get database password: {e.stderr}")
        sys.exit(1)


def validate_database() -> Tuple[bool, Dict]:
    """Validate database state"""
    print("=" * 80)
    print("🗄️  DATABASE VALIDATION")
    print("=" * 80)
    print()

    db_password = get_db_password()

    try:
        conn = psycopg2.connect(
            host="localhost",
            port="5433",  # Via Cloud SQL proxy
            database="headhunter",
            user="hh_analytics",
            password=db_password
        )
        cursor = conn.cursor()

        results = {}
        all_passed = True

        # Test 1: Overall embedding statistics
        print("📊 Test 1: Overall Embedding Statistics")
        print("-" * 80)
        cursor.execute("""
            SELECT
                COUNT(*) as total_embeddings,
                COUNT(*) FILTER (WHERE embedding IS NOT NULL) as has_vectors,
                COUNT(*) FILTER (WHERE embedding IS NULL) as null_vectors,
                ROUND(100.0 * COUNT(*) FILTER (WHERE embedding IS NOT NULL) / COUNT(*), 1) as percent_complete
            FROM search.candidate_embeddings
            WHERE tenant_id = 'tenant-alpha';
        """)

        total, has_vectors, null_vectors, percent = cursor.fetchone()
        results['total_embeddings'] = total
        results['has_vectors'] = has_vectors
        results['null_vectors'] = null_vectors
        results['percent_complete'] = float(percent)

        print(f"Total embeddings: {total:,}")
        print(f"Has vectors: {has_vectors:,} ({percent}%)")
        print(f"NULL vectors: {null_vectors:,}")

        test1_pass = percent >= 95.0
        print(f"Status: {'✅ PASS' if test1_pass else '❌ FAIL'} (Expected: ≥95% complete)")
        print()
        all_passed = all_passed and test1_pass

        # Test 2: Entity ID format (no prefixes)
        print("🏷️  Test 2: Entity ID Format Validation")
        print("-" * 80)
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE entity_id LIKE 'tenant-%:%') as prefixed,
                COUNT(*) FILTER (WHERE entity_id NOT LIKE '%:%') as plain
            FROM search.candidate_embeddings
            WHERE tenant_id = 'tenant-alpha';
        """)

        total, prefixed, plain = cursor.fetchone()
        results['prefixed_ids'] = prefixed
        results['plain_ids'] = plain

        print(f"Total embeddings: {total:,}")
        print(f"Prefixed IDs: {prefixed:,}")
        print(f"Plain IDs: {plain:,}")

        test2_pass = prefixed == 0
        print(f"Status: {'✅ PASS' if test2_pass else '❌ FAIL'} (Expected: 0 prefixed IDs)")
        print()
        all_passed = all_passed and test2_pass

        # Test 3: Vector dimensions
        print("📏 Test 3: Vector Dimensions")
        print("-" * 80)
        cursor.execute("""
            SELECT
                vector_dims(embedding) as dimensions,
                COUNT(*) as count
            FROM search.candidate_embeddings
            WHERE tenant_id = 'tenant-alpha'
              AND embedding IS NOT NULL
            GROUP BY vector_dims(embedding)
            ORDER BY count DESC;
        """)

        dim_results = cursor.fetchall()
        results['dimension_counts'] = {dim: count for dim, count in dim_results}

        for dim, count in dim_results:
            print(f"Dimension {dim}: {count:,} embeddings")

        test3_pass = len(dim_results) == 1 and dim_results[0][0] == 768
        print(f"Status: {'✅ PASS' if test3_pass else '❌ FAIL'} (Expected: All 768 dimensions)")
        print()
        all_passed = all_passed and test3_pass

        # Test 4: Source breakdown
        print("📦 Test 4: Embeddings by Source")
        print("-" * 80)
        cursor.execute("""
            SELECT
                metadata->>'source' as source,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE embedding IS NOT NULL) as has_vectors,
                COUNT(*) FILTER (WHERE embedding IS NULL) as null_vectors
            FROM search.candidate_embeddings
            WHERE tenant_id = 'tenant-alpha'
            GROUP BY metadata->>'source'
            ORDER BY has_vectors DESC;
        """)

        source_results = cursor.fetchall()
        results['sources'] = {}

        for source, total, has_vec, null_vec in source_results:
            source_name = source or "(null)"
            results['sources'][source_name] = {
                'total': total,
                'has_vectors': has_vec,
                'null_vectors': null_vec
            }
            print(f"{source_name:30} | Total: {total:6,} | Vectors: {has_vec:6,} | NULL: {null_vec:6,}")

        # Check that phase2_structured_reembedding has good coverage
        phase2_count = results['sources'].get('phase2_structured_reembedding', {}).get('has_vectors', 0)
        test4_pass = phase2_count > 25000  # Should have ~28,988
        print(f"Status: {'✅ PASS' if test4_pass else '❌ FAIL'} (Expected: phase2_structured_reembedding ≥25,000)")
        print()
        all_passed = all_passed and test4_pass

        # Test 5: Sample recent embeddings
        print("🔬 Test 5: Sample Recent Embeddings")
        print("-" * 80)
        cursor.execute("""
            SELECT
                entity_id,
                CASE WHEN embedding IS NOT NULL THEN 'HAS_VECTOR' ELSE 'NULL' END as status,
                vector_dims(embedding) as dimensions,
                metadata->>'source' as source
            FROM search.candidate_embeddings
            WHERE tenant_id = 'tenant-alpha'
              AND metadata->>'source' = 'phase2_structured_reembedding'
            ORDER BY created_at DESC
            LIMIT 10;
        """)

        samples = cursor.fetchall()
        sample_pass = all(status == 'HAS_VECTOR' and dim == 768 for _, status, dim, _ in samples)

        for entity_id, status, dim, source in samples[:5]:  # Show first 5
            print(f"{entity_id:15} | {status:10} | {dim:4} dims | {source}")

        print(f"Status: {'✅ PASS' if sample_pass else '❌ FAIL'} (Expected: All samples have 768-dim vectors)")
        print()
        all_passed = all_passed and sample_pass

        # Test 6: JOIN compatibility
        print("🔗 Test 6: JOIN with Candidate Profiles")
        print("-" * 80)
        cursor.execute("""
            SELECT COUNT(DISTINCT ce.entity_id) as matches
            FROM search.candidate_embeddings ce
            INNER JOIN search.candidate_profiles cp
              ON ce.entity_id = cp.candidate_id
            WHERE ce.tenant_id = 'tenant-alpha'
              AND ce.embedding IS NOT NULL;
        """)

        join_matches = cursor.fetchone()[0]
        results['join_matches'] = join_matches

        print(f"Embeddings that JOIN with profiles: {join_matches:,}")

        test6_pass = join_matches > 25000  # Should be close to total with vectors
        print(f"Status: {'✅ PASS' if test6_pass else '❌ FAIL'} (Expected: ≥25,000 matches)")
        print()
        all_passed = all_passed and test6_pass

        cursor.close()
        conn.close()

        return all_passed, results

    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
        return False, {}


async def validate_search_endpoint() -> Tuple[bool, Dict]:
    """Validate hybrid search endpoint"""
    print("=" * 80)
    print("🔍 SEARCH ENDPOINT VALIDATION")
    print("=" * 80)
    print()

    api_key = "AIzaSyD4fwoF0SMDVsA4A1Ip0_dT-qfP1OYPODs"
    tenant_id = "tenant-alpha"
    search_url = "https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/search/hybrid"

    test_queries = [
        ("Senior Python Developer with machine learning", 5),
        ("Java Backend Engineer Spring Boot microservices", 5),
        ("Full Stack Developer React Node.js", 5),
        ("DevOps Engineer Kubernetes Docker", 5),
    ]

    results = {}
    all_passed = True

    async with aiohttp.ClientSession() as session:
        for i, (query, limit) in enumerate(test_queries, 1):
            print(f"🧪 Test {i}: Query: '{query}'")
            print("-" * 80)

            payload = {
                "query": query,
                "limit": limit,
                "includeDebug": True
            }

            headers = {
                "x-api-key": api_key,
                "X-Tenant-ID": tenant_id,
                "Content-Type": "application/json"
            }

            try:
                async with session.post(search_url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"❌ HTTP {response.status}: {error_text}")
                        results[f"query_{i}"] = {"status": "error", "error": error_text}
                        all_passed = False
                        continue

                    data = await response.json()

                    num_results = len(data.get('results', []))
                    total = data.get('total', 0)

                    print(f"Results returned: {num_results}")
                    print(f"Total matches: {total}")

                    if 'debug' in data:
                        debug = data['debug']
                        print(f"Debug info:")
                        print(f"  - Vector results: {debug.get('vectorResults', 'N/A')}")
                        print(f"  - Profiles joined: {debug.get('profilesJoined', 'N/A')}")

                    # Show sample result
                    if data.get('results'):
                        sample = data['results'][0]
                        print(f"Sample result: ID={sample.get('candidateId')}, Score={sample.get('score', 0):.3f}")

                    test_pass = num_results > 0 and total > 0
                    print(f"Status: {'✅ PASS' if test_pass else '❌ FAIL'} (Expected: results > 0)")
                    print()

                    results[f"query_{i}"] = {
                        "status": "success" if test_pass else "no_results",
                        "num_results": num_results,
                        "total": total
                    }

                    all_passed = all_passed and test_pass

            except Exception as e:
                print(f"❌ REQUEST ERROR: {e}")
                results[f"query_{i}"] = {"status": "error", "error": str(e)}
                all_passed = False
                print()

    return all_passed, results


async def main():
    """Run all validation tests"""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "SEARCH FIX VALIDATION" + " " * 37 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    overall_results = {
        "database": {},
        "search": {}
    }

    # Validate database
    db_pass, db_results = validate_database()
    overall_results["database"] = {
        "passed": db_pass,
        "results": db_results
    }

    # Validate search endpoint
    search_pass, search_results = await validate_search_endpoint()
    overall_results["search"] = {
        "passed": search_pass,
        "results": search_results
    }

    # Final summary
    print("=" * 80)
    print("📋 FINAL SUMMARY")
    print("=" * 80)
    print()

    print(f"Database Validation: {'✅ PASS' if db_pass else '❌ FAIL'}")
    print(f"Search Validation: {'✅ PASS' if search_pass else '❌ FAIL'}")
    print()

    overall_pass = db_pass and search_pass

    if overall_pass:
        print("🎉 " + "=" * 76)
        print("🎉 ALL TESTS PASSED - SEARCH FIX IS COMPLETE!")
        print("🎉 " + "=" * 76)
        print()
        print("✅ Entity ID format: Fixed (no prefixes)")
        print("✅ Embedding vectors: Generated (768 dimensions)")
        print("✅ Database JOIN: Working")
        print("✅ Hybrid search: Returning results")
        print()
        print("Next steps:")
        print("1. Update docs/HANDOVER.md with resolution")
        print("2. Mark incident as closed")
        print("3. Monitor production metrics")
    else:
        print("❌ " + "=" * 76)
        print("❌ VALIDATION FAILED - FURTHER INVESTIGATION REQUIRED")
        print("❌ " + "=" * 76)
        print()

        if not db_pass:
            print("Database issues detected:")
            if overall_results["database"]["results"].get("percent_complete", 0) < 95:
                print("  - Insufficient embeddings with vectors (<95%)")
            if overall_results["database"]["results"].get("prefixed_ids", 0) > 0:
                print("  - Entity IDs still have prefixes")
            if overall_results["database"]["results"].get("join_matches", 0) < 25000:
                print("  - JOIN with profiles returning too few matches")

        if not search_pass:
            print("Search endpoint issues detected:")
            print("  - Some queries returning 0 results")
            print("  - Check Cloud Logging for hh-search-svc errors")

    print()

    # Save results to file
    results_file = "/tmp/search_validation_results.json"
    with open(results_file, 'w') as f:
        json.dump(overall_results, f, indent=2)

    print(f"📄 Full results saved to: {results_file}")
    print()

    return 0 if overall_pass else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
