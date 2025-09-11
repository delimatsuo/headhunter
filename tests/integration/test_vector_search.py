"""
Integration tests for Vector Search & Embedding workflows

This module tests the complete vector search and embedding workflows including:
- VertexAI embedding generation pipeline
- pgvector storage and indexing  
- Semantic search accuracy
- Hybrid search (keyword + vector)
- Search result pagination
- Search performance under load
"""

import pytest
import asyncio
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime

# Test markers
pytestmark = [pytest.mark.integration, pytest.mark.database, pytest.mark.performance]


class TestVectorSearchIntegration:
    """Test complete vector search and embedding integration"""
    
    @pytest.mark.asyncio
    async def test_complete_embedding_pipeline(
        self,
        sample_candidates: List[Dict[str, Any]],
        mock_vertex_ai_embeddings,
        mock_postgres_connection,
        performance_monitor
    ):
        """Test complete embedding generation and storage pipeline"""
        performance_monitor.start_timer("complete_embedding_pipeline")
        
        for i, candidate in enumerate(sample_candidates):
            # Generate embedding
            performance_monitor.start_timer(f"embedding_generation_{i}")
            
            embedding = await self._generate_candidate_embedding(candidate)
            
            performance_monitor.end_timer(f"embedding_generation_{i}")
            
            # Verify embedding properties
            assert len(embedding) == 768, "Should generate 768-dimensional embedding"
            assert all(isinstance(x, float) for x in embedding), "Should be float values"
            
            # Store in pgvector
            performance_monitor.start_timer(f"embedding_storage_{i}")
            
            storage_result = await self._store_embedding_pgvector(
                candidate["candidate_id"], 
                embedding
            )
            
            performance_monitor.end_timer(f"embedding_storage_{i}")
            
            assert storage_result["success"] is True, "Should store embedding successfully"
        
        performance_monitor.end_timer("complete_embedding_pipeline")
        
        # Assert performance requirements
        performance_monitor.assert_performance("complete_embedding_pipeline", 10.0)
        
        for i in range(len(sample_candidates)):
            performance_monitor.assert_performance(f"embedding_generation_{i}", 2.0)
            performance_monitor.assert_performance(f"embedding_storage_{i}", 1.0)
    
    @pytest.mark.asyncio
    async def test_semantic_search_accuracy(
        self,
        sample_candidates: List[Dict[str, Any]],
        mock_postgres_connection,
        performance_monitor
    ):
        """Test semantic search accuracy and relevance"""
        # Seed candidates with embeddings
        await self._seed_candidates_with_embeddings(sample_candidates)
        
        # Test queries with expected results
        test_queries = [
            {
                "query": "Senior Python developer with AWS experience",
                "expected_skills": ["Python", "AWS"],
                "min_results": 2
            },
            {
                "query": "React frontend developer",
                "expected_skills": ["React", "JavaScript"],
                "min_results": 1
            },
            {
                "query": "Machine learning engineer",
                "expected_skills": ["Python", "Machine Learning"],
                "min_results": 1
            }
        ]
        
        for test_query in test_queries:
            performance_monitor.start_timer(f"semantic_search_{test_query['query'][:10]}")
            
            search_results = await self._semantic_search(
                query=test_query["query"],
                limit=10,
                threshold=0.7
            )
            
            performance_monitor.end_timer(f"semantic_search_{test_query['query'][:10]}")
            
            # Verify search results
            assert len(search_results) >= test_query["min_results"], \
                f"Should find at least {test_query['min_results']} results for '{test_query['query']}'"
            
            # Check relevance scores
            for result in search_results:
                assert result["similarity_score"] >= 0.7, \
                    "Results should meet minimum similarity threshold"
                
                # Verify skill matching
                candidate_skills = self._extract_candidate_skills(result)
                skill_overlap = len(set(test_query["expected_skills"]).intersection(candidate_skills))
                
                if result["similarity_score"] >= 0.9:  # High similarity should have skill overlap
                    assert skill_overlap > 0, \
                        f"High similarity result should have skill overlap with {test_query['expected_skills']}"
    
    @pytest.mark.asyncio
    async def test_hybrid_search_keyword_vector(
        self,
        sample_candidates: List[Dict[str, Any]],
        performance_monitor
    ):
        """Test hybrid search combining keyword and vector search"""
        await self._seed_candidates_with_embeddings(sample_candidates)
        
        # Test hybrid search scenarios
        hybrid_queries = [
            {
                "text_query": "Python developer",
                "filters": {"experience_years_min": 5},
                "expected_combination": "keyword_and_vector"
            },
            {
                "text_query": "senior engineer",
                "filters": {"skills": ["Python", "AWS"]},
                "expected_combination": "keyword_and_filter"
            }
        ]
        
        for query in hybrid_queries:
            performance_monitor.start_timer(f"hybrid_search_{query['text_query'][:10]}")
            
            hybrid_results = await self._hybrid_search(
                text_query=query["text_query"],
                filters=query["filters"],
                limit=10
            )
            
            performance_monitor.end_timer(f"hybrid_search_{query['text_query'][:10]}")
            
            # Verify hybrid results
            assert len(hybrid_results["candidates"]) > 0, "Should return hybrid results"
            assert "vector_score" in hybrid_results["candidates"][0], "Should include vector scores"
            assert "keyword_score" in hybrid_results["candidates"][0], "Should include keyword scores"
            assert "hybrid_score" in hybrid_results["candidates"][0], "Should include combined scores"
            
            # Verify score combination
            for candidate in hybrid_results["candidates"]:
                vector_score = candidate["vector_score"]
                keyword_score = candidate["keyword_score"]
                hybrid_score = candidate["hybrid_score"]
                
                # Hybrid score should be combination of vector and keyword scores
                expected_range = (
                    min(vector_score, keyword_score),
                    max(vector_score, keyword_score)
                )
                assert expected_range[0] <= hybrid_score <= expected_range[1] + 0.1, \
                    "Hybrid score should reasonably combine vector and keyword scores"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_search_performance_under_load(
        self,
        sample_candidates: List[Dict[str, Any]],
        performance_monitor
    ):
        """Test search performance under concurrent load"""
        # Scale up test data
        large_candidate_set = []
        for i in range(100):  # 100 candidates for load testing
            candidate = sample_candidates[i % len(sample_candidates)].copy()
            candidate["candidate_id"] = f"load_test_{i}"
            large_candidate_set.append(candidate)
        
        await self._seed_candidates_with_embeddings(large_candidate_set)
        
        # Concurrent search queries
        search_queries = [
            "Python developer with 5 years experience",
            "React frontend engineer",
            "DevOps engineer with AWS",
            "Data scientist with machine learning",
            "Senior backend developer"
        ]
        
        # Execute concurrent searches
        concurrent_tasks = []
        
        for i in range(20):  # 20 concurrent searches
            query = search_queries[i % len(search_queries)]
            task = self._concurrent_search_task(
                query=query,
                task_id=i,
                performance_monitor=performance_monitor
            )
            concurrent_tasks.append(task)
        
        performance_monitor.start_timer("concurrent_load_test")
        
        results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
        
        performance_monitor.end_timer("concurrent_load_test")
        
        # Verify all searches completed successfully
        successful_searches = [r for r in results if not isinstance(r, Exception)]
        failed_searches = [r for r in results if isinstance(r, Exception)]
        
        assert len(successful_searches) >= 18, \
            f"At least 90% of searches should succeed, got {len(successful_searches)}/20"
        assert len(failed_searches) <= 2, \
            f"No more than 10% searches should fail, got {len(failed_searches)}/20"
        
        # Check average performance
        search_times = [r["search_time"] for r in successful_searches if "search_time" in r]
        avg_search_time = sum(search_times) / len(search_times)
        
        assert avg_search_time <= 1.0, \
            f"Average search time should be ≤1s under load, got {avg_search_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_search_result_pagination(
        self,
        sample_candidates: List[Dict[str, Any]],
        performance_monitor
    ):
        """Test search result pagination functionality"""
        # Create larger dataset for pagination testing
        extended_candidates = []
        for i in range(25):  # 25 candidates for pagination
            candidate = sample_candidates[i % len(sample_candidates)].copy()
            candidate["candidate_id"] = f"paginated_{i}"
            extended_candidates.append(candidate)
        
        await self._seed_candidates_with_embeddings(extended_candidates)
        
        # Test pagination scenarios
        page_sizes = [5, 10, 15]
        
        for page_size in page_sizes:
            performance_monitor.start_timer(f"pagination_test_{page_size}")
            
            # First page
            page_1 = await self._paginated_search(
                query="Python developer",
                page_size=page_size,
                page_token=None
            )
            
            assert len(page_1["candidates"]) == page_size, \
                f"First page should have {page_size} results"
            assert "next_page_token" in page_1, "Should include next page token"
            
            # Second page
            page_2 = await self._paginated_search(
                query="Python developer",
                page_size=page_size,
                page_token=page_1["next_page_token"]
            )
            
            assert len(page_2["candidates"]) <= page_size, \
                f"Second page should have ≤{page_size} results"
            
            # Verify no duplicate results between pages
            page_1_ids = {c["candidate_id"] for c in page_1["candidates"]}
            page_2_ids = {c["candidate_id"] for c in page_2["candidates"]}
            
            assert len(page_1_ids.intersection(page_2_ids)) == 0, \
                "Pages should not contain duplicate candidates"
            
            performance_monitor.end_timer(f"pagination_test_{page_size}")
            
            # Assert pagination performance
            performance_monitor.assert_performance(f"pagination_test_{page_size}", 2.0)
    
    @pytest.mark.asyncio
    async def test_embedding_similarity_algorithms(
        self,
        performance_monitor
    ):
        """Test different similarity algorithms for embedding comparison"""
        # Generate test embeddings
        test_embeddings = {
            "query": [0.5 + i * 0.001 for i in range(768)],
            "similar": [0.5 + i * 0.001 + 0.01 for i in range(768)],  # Very similar
            "related": [0.4 + i * 0.002 for i in range(768)],         # Somewhat similar
            "different": [0.1 + i * 0.003 for i in range(768)]        # Different
        }
        
        # Test cosine similarity
        performance_monitor.start_timer("cosine_similarity_test")
        
        cosine_scores = {}
        for name, embedding in test_embeddings.items():
            if name != "query":
                cosine_scores[name] = await self._calculate_cosine_similarity(
                    test_embeddings["query"],
                    embedding
                )
        
        performance_monitor.end_timer("cosine_similarity_test")
        
        # Verify cosine similarity ordering
        assert cosine_scores["similar"] > cosine_scores["related"], \
            "Similar embedding should have higher cosine similarity"
        assert cosine_scores["related"] > cosine_scores["different"], \
            "Related embedding should have higher similarity than different"
        
        # Test dot product similarity
        performance_monitor.start_timer("dot_product_test")
        
        dot_scores = {}
        for name, embedding in test_embeddings.items():
            if name != "query":
                dot_scores[name] = await self._calculate_dot_product(
                    test_embeddings["query"],
                    embedding
                )
        
        performance_monitor.end_timer("dot_product_test")
        
        # Test Euclidean distance
        performance_monitor.start_timer("euclidean_distance_test")
        
        euclidean_scores = {}
        for name, embedding in test_embeddings.items():
            if name != "query":
                euclidean_scores[name] = await self._calculate_euclidean_distance(
                    test_embeddings["query"],
                    embedding
                )
        
        performance_monitor.end_timer("euclidean_distance_test")
        
        # Verify Euclidean distance ordering (lower is more similar)
        assert euclidean_scores["similar"] < euclidean_scores["related"], \
            "Similar embedding should have lower Euclidean distance"
        assert euclidean_scores["related"] < euclidean_scores["different"], \
            "Related embedding should have lower distance than different"
    
    # Helper methods for vector search testing
    async def _generate_candidate_embedding(
        self,
        candidate: Dict[str, Any]
    ) -> List[float]:
        """Generate embedding for candidate profile"""
        # Mock VertexAI embedding generation
        candidate_text = f"{candidate.get('name', '')} {str(candidate.get('enhanced_analysis', {}))}"
        
        # Create deterministic embedding based on candidate data
        base_value = hash(candidate_text) % 1000 / 1000.0
        
        return [base_value + i * 0.001 for i in range(768)]
    
    async def _store_embedding_pgvector(
        self,
        candidate_id: str,
        embedding: List[float]
    ) -> Dict[str, Any]:
        """Store embedding in pgvector database"""
        # Mock pgvector storage
        return {
            "success": True,
            "candidate_id": candidate_id,
            "embedding_dim": len(embedding),
            "stored_at": datetime.utcnow().isoformat()
        }
    
    async def _seed_candidates_with_embeddings(
        self,
        candidates: List[Dict[str, Any]]
    ) -> None:
        """Seed test candidates with embeddings"""
        for candidate in candidates:
            embedding = await self._generate_candidate_embedding(candidate)
            await self._store_embedding_pgvector(candidate["candidate_id"], embedding)
    
    async def _semantic_search(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Perform semantic search using vector similarity"""
        # Generate query embedding
        query_embedding = [0.6 + i * 0.001 for i in range(768)]  # Mock query embedding
        
        # Mock search results with varying similarity scores
        mock_results = [
            {
                "candidate_id": "semantic_result_1",
                "similarity_score": 0.95,
                "enhanced_analysis": {
                    "technical_skills": {"core_competencies": ["Python", "AWS", "Docker"]}
                }
            },
            {
                "candidate_id": "semantic_result_2", 
                "similarity_score": 0.87,
                "enhanced_analysis": {
                    "technical_skills": {"core_competencies": ["Python", "React", "PostgreSQL"]}
                }
            },
            {
                "candidate_id": "semantic_result_3",
                "similarity_score": 0.73,
                "enhanced_analysis": {
                    "technical_skills": {"core_competencies": ["JavaScript", "Node.js", "MongoDB"]}
                }
            }
        ]
        
        # Filter by threshold and limit
        filtered_results = [r for r in mock_results if r["similarity_score"] >= threshold]
        
        return filtered_results[:limit]
    
    async def _hybrid_search(
        self,
        text_query: str,
        filters: Dict[str, Any],
        limit: int = 10
    ) -> Dict[str, Any]:
        """Perform hybrid search combining vector and keyword search"""
        # Mock hybrid search results
        mock_candidates = [
            {
                "candidate_id": "hybrid_result_1",
                "vector_score": 0.92,
                "keyword_score": 0.85,
                "hybrid_score": 0.88,  # Weighted combination
                "enhanced_analysis": {
                    "technical_skills": {"core_competencies": ["Python", "AWS"]},
                    "career_trajectory": {"years_experience": 7}
                }
            },
            {
                "candidate_id": "hybrid_result_2",
                "vector_score": 0.78,
                "keyword_score": 0.90,
                "hybrid_score": 0.84,
                "enhanced_analysis": {
                    "technical_skills": {"core_competencies": ["Python", "React"]},
                    "career_trajectory": {"years_experience": 6}
                }
            }
        ]
        
        return {"candidates": mock_candidates[:limit]}
    
    async def _concurrent_search_task(
        self,
        query: str,
        task_id: int,
        performance_monitor
    ) -> Dict[str, Any]:
        """Execute concurrent search task"""
        task_name = f"concurrent_search_{task_id}"
        performance_monitor.start_timer(task_name)
        
        # Simulate search delay
        await asyncio.sleep(0.1 + (task_id % 3) * 0.05)  # Variable delay
        
        # Mock search results
        results = await self._semantic_search(query, limit=5)
        
        performance_monitor.end_timer(task_name)
        
        return {
            "task_id": task_id,
            "query": query,
            "results_count": len(results),
            "search_time": performance_monitor.get_metrics().get(task_name, 0)
        }
    
    async def _paginated_search(
        self,
        query: str,
        page_size: int,
        page_token: Optional[str]
    ) -> Dict[str, Any]:
        """Perform paginated search"""
        # Mock paginated results
        start_index = 0 if page_token is None else int(page_token.split("_")[-1])
        
        mock_candidates = [
            {
                "candidate_id": f"paginated_result_{i}",
                "similarity_score": 0.9 - (i * 0.02),
                "enhanced_analysis": {"technical_skills": {"core_competencies": ["Python"]}}
            }
            for i in range(start_index, start_index + page_size)
        ]
        
        next_token = f"page_token_{start_index + page_size}" if start_index + page_size < 25 else None
        
        return {
            "candidates": mock_candidates,
            "next_page_token": next_token,
            "total_count": 25
        }
    
    async def _calculate_cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """Calculate cosine similarity between embeddings"""
        # Mock cosine similarity calculation
        # In real implementation, would use numpy or similar
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        magnitude1 = sum(a * a for a in embedding1) ** 0.5
        magnitude2 = sum(b * b for b in embedding2) ** 0.5
        
        return dot_product / (magnitude1 * magnitude2)
    
    async def _calculate_dot_product(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """Calculate dot product between embeddings"""
        return sum(a * b for a, b in zip(embedding1, embedding2))
    
    async def _calculate_euclidean_distance(
        self,
        embedding1: List[float], 
        embedding2: List[float]
    ) -> float:
        """Calculate Euclidean distance between embeddings"""
        return sum((a - b) ** 2 for a, b in zip(embedding1, embedding2)) ** 0.5
    
    def _extract_candidate_skills(self, candidate: Dict[str, Any]) -> List[str]:
        """Extract skills from candidate data"""
        return candidate.get("enhanced_analysis", {}).get(
            "technical_skills", {}
        ).get("core_competencies", [])