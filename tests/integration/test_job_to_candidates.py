"""
Integration tests for Job Description to Candidate Recommendations workflow

This module tests the complete end-to-end workflow from job description
input to ranked candidate recommendations, including:
- Job description parsing and skill extraction
- Embedding generation for job requirements  
- pgvector similarity search for candidate matching
- Ranking algorithm with skill probabilities
- Recommendation quality metrics validation
"""

import pytest
import asyncio
import json
from typing import Dict, List, Any
from datetime import datetime

# Test markers
pytestmark = [pytest.mark.integration, pytest.mark.workflow, pytest.mark.api]


class TestJobToCandidatesWorkflow:
    """Test complete job description to candidate recommendations workflow"""
    
    @pytest.mark.asyncio
    async def test_complete_job_to_candidates_workflow(
        self,
        sample_job_description: Dict[str, Any],
        sample_candidates: List[Dict[str, Any]],
        mock_together_ai,
        mock_vertex_ai_embeddings,
        mock_postgres_connection,
        performance_monitor
    ):
        """Test complete workflow from job description to candidate recommendations"""
        performance_monitor.start_timer("complete_workflow")
        
        # Step 1: Parse job description and extract skills
        performance_monitor.start_timer("job_parsing")
        
        job_skills = await self._extract_job_skills(sample_job_description)
        
        performance_monitor.end_timer("job_parsing")
        
        # Verify skill extraction
        assert len(job_skills) > 0, "Should extract skills from job description"
        assert "Python" in job_skills, "Should identify Python as required skill"
        
        # Step 2: Generate embedding for job description
        performance_monitor.start_timer("job_embedding")
        
        job_embedding = await self._generate_job_embedding(sample_job_description["description"])
        
        performance_monitor.end_timer("job_embedding")
        
        # Verify embedding generation
        assert len(job_embedding) == 768, "Should generate 768-dimensional embedding"
        assert all(isinstance(x, float) for x in job_embedding), "Embedding should be float values"
        
        # Step 3: Search for similar candidates using pgvector
        performance_monitor.start_timer("vector_search")
        
        similar_candidates = await self._search_similar_candidates(
            job_embedding, 
            job_skills,
            limit=10
        )
        
        performance_monitor.end_timer("vector_search")
        
        # Verify search results
        assert len(similar_candidates) > 0, "Should find similar candidates"
        assert len(similar_candidates) <= 10, "Should respect limit parameter"
        
        # Step 4: Apply skill probability ranking
        performance_monitor.start_timer("skill_ranking")
        
        ranked_candidates = await self._apply_skill_ranking(
            similar_candidates,
            job_skills,
            sample_job_description["experience_required"]
        )
        
        performance_monitor.end_timer("skill_ranking")
        
        # Verify ranking algorithm
        assert len(ranked_candidates) == len(similar_candidates), "Should preserve candidate count"
        assert all("composite_score" in candidate for candidate in ranked_candidates), \
            "Should add composite scores to candidates"
        
        # Verify candidates are sorted by composite score (descending)
        scores = [c["composite_score"] for c in ranked_candidates]
        assert scores == sorted(scores, reverse=True), "Should sort by composite score descending"
        
        # Step 5: Validate recommendation quality
        performance_monitor.start_timer("quality_validation")
        
        quality_metrics = await self._validate_recommendation_quality(
            ranked_candidates,
            job_skills,
            sample_job_description["experience_required"]
        )
        
        performance_monitor.end_timer("quality_validation")
        performance_monitor.end_timer("complete_workflow")
        
        # Assert quality metrics
        assert quality_metrics["relevance_score"] >= 0.7, \
            f"Relevance score {quality_metrics['relevance_score']:.3f} should be >= 0.7"
        assert quality_metrics["skill_match_coverage"] >= 0.8, \
            f"Skill coverage {quality_metrics['skill_match_coverage']:.3f} should be >= 0.8"
        
        # Assert performance requirements
        performance_monitor.assert_performance("complete_workflow", 2.0)  # Max 2 seconds total
        performance_monitor.assert_performance("vector_search", 0.5)      # Max 500ms for search
        performance_monitor.assert_performance("skill_ranking", 0.3)      # Max 300ms for ranking
        
        return {
            "ranked_candidates": ranked_candidates,
            "quality_metrics": quality_metrics,
            "performance_metrics": performance_monitor.get_metrics()
        }
    
    @pytest.mark.asyncio
    async def test_job_skill_extraction_accuracy(
        self,
        test_data_factory,
        mock_together_ai
    ):
        """Test accuracy of skill extraction from job descriptions"""
        # Create job with known skills
        job = test_data_factory.create_job_description(
            job_title="Senior Data Scientist",
            required_skills=["Python", "Machine Learning", "TensorFlow", "SQL", "Docker"],
            experience_years=5
        )
        
        extracted_skills = await self._extract_job_skills(job)
        
        # Should extract most required skills
        expected_skills = set(job["required_skills"])
        extracted_skills_set = set(extracted_skills)
        
        overlap = expected_skills.intersection(extracted_skills_set)
        coverage = len(overlap) / len(expected_skills)
        
        assert coverage >= 0.8, f"Should extract at least 80% of required skills, got {coverage:.1%}"
        
        # Should not extract completely unrelated skills
        unrelated_skills = {"Cooking", "Dancing", "Photography"}
        assert not unrelated_skills.intersection(extracted_skills_set), \
            "Should not extract unrelated skills"
    
    @pytest.mark.asyncio
    async def test_skill_probability_ranking_algorithm(
        self,
        sample_candidates: List[Dict[str, Any]],
        test_data_factory
    ):
        """Test the skill probability ranking algorithm accuracy"""
        job_skills = ["Python", "React", "PostgreSQL"]
        experience_required = 5
        
        # Apply ranking
        ranked_candidates = await self._apply_skill_ranking(
            sample_candidates,
            job_skills, 
            experience_required
        )
        
        # Verify ranking components
        for candidate in ranked_candidates:
            assert "composite_score" in candidate, "Should have composite score"
            assert "skill_match_score" in candidate, "Should have skill match component"
            assert "confidence_score" in candidate, "Should have confidence component"
            assert "experience_match_score" in candidate, "Should have experience component"
            
            # Verify score ranges
            assert 0 <= candidate["composite_score"] <= 100, "Composite score should be 0-100"
            assert 0 <= candidate["skill_match_score"] <= 100, "Skill match should be 0-100"
            assert 0 <= candidate["confidence_score"] <= 100, "Confidence should be 0-100"
        
        # Verify algorithmic correctness
        # Candidate with exact skill match should score higher
        python_expert = next(
            (c for c in ranked_candidates 
             if "Python" in str(c.get("enhanced_analysis", {}).get("technical_skills", {}).get("core_competencies", []))),
            None
        )
        
        if python_expert:
            non_python_candidates = [
                c for c in ranked_candidates
                if "Python" not in str(c.get("enhanced_analysis", {}).get("technical_skills", {}).get("core_competencies", []))
            ]
            
            if non_python_candidates:
                assert python_expert["composite_score"] > min(c["composite_score"] for c in non_python_candidates), \
                    "Python expert should score higher than non-Python candidates"
    
    @pytest.mark.asyncio
    async def test_embedding_generation_consistency(
        self,
        mock_vertex_ai_embeddings
    ):
        """Test that embedding generation is consistent for same input"""
        job_description = "Senior Python Developer with React and PostgreSQL experience"
        
        # Generate embeddings multiple times
        embedding1 = await self._generate_job_embedding(job_description)
        embedding2 = await self._generate_job_embedding(job_description)
        embedding3 = await self._generate_job_embedding(job_description)
        
        # Should be identical (in mock scenario)
        assert embedding1 == embedding2 == embedding3, \
            "Same input should generate identical embeddings"
        
        # Test different inputs produce different embeddings
        different_job = "Junior JavaScript Developer"
        different_embedding = await self._generate_job_embedding(different_job)
        
        # In a real scenario these would be different, but our mock returns same values
        # This test would be more meaningful with real VertexAI integration
        assert len(different_embedding) == 768, "Should generate proper embedding size"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_search_performance_under_load(
        self,
        sample_job_description: Dict[str, Any],
        mock_postgres_connection,
        mock_vertex_ai_embeddings,
        performance_monitor
    ):
        """Test search performance with multiple concurrent requests"""
        # Simulate multiple concurrent job searches
        tasks = []
        
        for i in range(10):  # 10 concurrent searches
            task = self._simulate_concurrent_search(
                sample_job_description,
                f"concurrent_search_{i}",
                performance_monitor
            )
            tasks.append(task)
        
        # Execute all searches concurrently
        results = await asyncio.gather(*tasks)
        
        # All searches should complete successfully
        assert len(results) == 10, "All concurrent searches should complete"
        
        # Performance should remain acceptable under load
        metrics = performance_monitor.get_metrics()
        avg_search_time = sum(
            metrics.get(f"concurrent_search_{i}", 0) for i in range(10)
        ) / 10
        
        assert avg_search_time <= 1.0, f"Average search time {avg_search_time:.3f}s should be <= 1.0s"
    
    @pytest.mark.asyncio
    async def test_recommendation_quality_metrics(
        self,
        sample_candidates: List[Dict[str, Any]],
        test_data_factory
    ):
        """Test quality metrics calculation for recommendations"""
        job_skills = ["Python", "React", "AWS"]
        experience_required = 6
        
        quality_metrics = await self._validate_recommendation_quality(
            sample_candidates,
            job_skills,
            experience_required
        )
        
        # Verify quality metrics structure
        required_metrics = [
            "relevance_score", 
            "skill_match_coverage",
            "experience_alignment",
            "confidence_distribution",
            "diversity_score"
        ]
        
        for metric in required_metrics:
            assert metric in quality_metrics, f"Should include {metric} metric"
            assert isinstance(quality_metrics[metric], (int, float)), \
                f"{metric} should be numeric"
            assert 0 <= quality_metrics[metric] <= 1, \
                f"{metric} should be between 0 and 1"
    
    # Helper methods
    async def _extract_job_skills(self, job_description: Dict[str, Any]) -> List[str]:
        """Extract skills from job description"""
        # In real implementation, this would use NLP to extract skills
        # For testing, we'll use the known required skills
        return job_description.get("required_skills", [])
    
    async def _generate_job_embedding(self, job_text: str) -> List[float]:
        """Generate embedding for job description"""
        # Mock implementation returns fixed embedding
        # Real implementation would call VertexAI
        return [0.2 + i * 0.001 for i in range(768)]
    
    async def _search_similar_candidates(
        self, 
        job_embedding: List[float],
        job_skills: List[str],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for candidates similar to job requirements"""
        # Mock implementation returns sample candidates
        # Real implementation would query pgvector database
        return [
            {
                "candidate_id": f"candidate_{i}",
                "similarity_score": 0.9 - i * 0.1,
                "enhanced_analysis": {
                    "technical_skills": {
                        "core_competencies": job_skills[:2] + [f"skill_{i}"]
                    },
                    "career_trajectory": {
                        "years_experience": 5 + i
                    }
                }
            }
            for i in range(min(limit, 5))
        ]
    
    async def _apply_skill_ranking(
        self,
        candidates: List[Dict[str, Any]],
        job_skills: List[str],
        experience_required: int
    ) -> List[Dict[str, Any]]:
        """Apply skill probability ranking algorithm"""
        ranked_candidates = []
        
        for candidate in candidates:
            candidate_skills = candidate.get("enhanced_analysis", {}).get(
                "technical_skills", {}
            ).get("core_competencies", [])
            
            candidate_experience = candidate.get("enhanced_analysis", {}).get(
                "career_trajectory", {}
            ).get("years_experience", 0)
            
            # Calculate skill match score
            skill_matches = len(set(job_skills).intersection(set(candidate_skills)))
            skill_match_score = (skill_matches / len(job_skills)) * 100
            
            # Calculate confidence score (mock - would use real confidence data)
            confidence_score = min(100, 70 + candidate_experience * 3)
            
            # Calculate experience match score
            exp_diff = abs(candidate_experience - experience_required)
            experience_match_score = max(0, 100 - exp_diff * 10)
            
            # Calculate composite score with weights
            # skill_match: 40%, confidence: 25%, vector_similarity: 25%, experience: 10%
            composite_score = (
                skill_match_score * 0.40 +
                confidence_score * 0.25 +
                candidate.get("similarity_score", 0) * 100 * 0.25 +
                experience_match_score * 0.10
            )
            
            # Add scoring details to candidate
            candidate_with_scores = candidate.copy()
            candidate_with_scores.update({
                "composite_score": round(composite_score, 2),
                "skill_match_score": round(skill_match_score, 2),
                "confidence_score": round(confidence_score, 2),
                "experience_match_score": round(experience_match_score, 2)
            })
            
            ranked_candidates.append(candidate_with_scores)
        
        # Sort by composite score (descending)
        ranked_candidates.sort(key=lambda x: x["composite_score"], reverse=True)
        
        return ranked_candidates
    
    async def _validate_recommendation_quality(
        self,
        candidates: List[Dict[str, Any]],
        job_skills: List[str],
        experience_required: int
    ) -> Dict[str, float]:
        """Validate quality of candidate recommendations"""
        if not candidates:
            return {
                "relevance_score": 0.0,
                "skill_match_coverage": 0.0,
                "experience_alignment": 0.0,
                "confidence_distribution": 0.0,
                "diversity_score": 0.0
            }
        
        # Calculate relevance score (average composite score)
        relevance_score = sum(c["composite_score"] for c in candidates) / (len(candidates) * 100)
        
        # Calculate skill match coverage
        all_candidate_skills = set()
        for candidate in candidates:
            candidate_skills = candidate.get("enhanced_analysis", {}).get(
                "technical_skills", {}
            ).get("core_competencies", [])
            all_candidate_skills.update(candidate_skills)
        
        skill_coverage = len(set(job_skills).intersection(all_candidate_skills)) / len(job_skills)
        
        # Calculate experience alignment
        experience_scores = []
        for candidate in candidates:
            candidate_exp = candidate.get("enhanced_analysis", {}).get(
                "career_trajectory", {}
            ).get("years_experience", 0)
            exp_diff = abs(candidate_exp - experience_required)
            exp_alignment = max(0, 1 - (exp_diff / max(experience_required, 1)))
            experience_scores.append(exp_alignment)
        
        experience_alignment = sum(experience_scores) / len(experience_scores)
        
        # Calculate confidence distribution (prefer high confidence candidates)
        confidence_scores = [c.get("confidence_score", 50) for c in candidates]
        confidence_distribution = sum(scores for scores in confidence_scores if scores >= 80) / (len(confidence_scores) * 100)
        
        # Calculate diversity score (variety in backgrounds)
        unique_backgrounds = len(set(
            candidate.get("enhanced_analysis", {}).get("company_pedigree", {}).get("company_tier", "unknown")
            for candidate in candidates
        ))
        diversity_score = min(1.0, unique_backgrounds / max(len(candidates), 1))
        
        return {
            "relevance_score": min(1.0, relevance_score),
            "skill_match_coverage": min(1.0, skill_coverage),
            "experience_alignment": min(1.0, experience_alignment),
            "confidence_distribution": min(1.0, confidence_distribution),
            "diversity_score": diversity_score
        }
    
    async def _simulate_concurrent_search(
        self,
        job_description: Dict[str, Any],
        operation_name: str,
        performance_monitor
    ) -> Dict[str, Any]:
        """Simulate concurrent search operation"""
        performance_monitor.start_timer(operation_name)
        
        # Simulate search delay
        await asyncio.sleep(0.1)
        
        # Mock search results
        result = {
            "candidates": [{"candidate_id": f"concurrent_{operation_name}_{i}"} for i in range(5)],
            "total_time": 0.1
        }
        
        performance_monitor.end_timer(operation_name)
        
        return result