"""
Integration test configuration and fixtures for Headhunter v2.0

This module provides comprehensive test fixtures for:
- Database setup and cleanup
- Mock external services
- Test data factories
- Authentication helpers
- Performance monitoring
"""

import asyncio
import json
import os
import pytest
import pytest_asyncio
from typing import Dict, List, Any, Generator, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import shutil
from datetime import datetime, timedelta
import uuid

# Test configuration
TEST_CONFIG = {
    "firebase": {
        "project_id": "headhunter-test",
        "service_account_path": os.getenv("FIREBASE_TEST_CREDENTIALS"),
        "emulator_host": "localhost:8080"
    },
    "postgres": {
        "host": "localhost",
        "port": 5432,
        "database": "headhunter_test",
        "user": "test_user", 
        "password": "test_password"
    },
    "together_ai": {
        "api_key": "test_key_together_ai",
        "base_url": "https://api.together.xyz"
    },
    "vertex_ai": {
        "project_id": "headhunter-test",
        "location": "us-central1"
    }
}


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire test session"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
    """Test configuration fixture"""
    return TEST_CONFIG


@pytest.fixture
def temp_directory() -> Generator[str, None, None]:
    """Create temporary directory for test files"""
    temp_dir = tempfile.mkdtemp(prefix="headhunter_test_")
    yield temp_dir
    shutil.rmtree(temp_dir)


# Mock External Services
@pytest.fixture
def mock_together_ai():
    """Mock Together AI API responses"""
    with patch('scripts.enhanced_together_ai_processor.requests.post') as mock_post:
        # Mock successful candidate analysis response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "enhanced_analysis": {
                            "career_trajectory": {
                                "current_level": "Senior",
                                "progression_speed": "fast",
                                "trajectory_type": "technical_leadership",
                                "years_experience": 8
                            },
                            "technical_skills": {
                                "core_competencies": ["Python", "React", "PostgreSQL"],
                                "skill_depth": "expert",
                                "learning_velocity": "high"
                            },
                            "explicit_skills": {
                                "technical_skills": [
                                    {"skill": "Python", "confidence": 95, "evidence": ["8 years experience", "multiple projects"]},
                                    {"skill": "React", "confidence": 90, "evidence": ["frontend development", "component architecture"]},
                                    {"skill": "PostgreSQL", "confidence": 85, "evidence": ["database design", "performance optimization"]}
                                ],
                                "soft_skills": [
                                    {"skill": "Leadership", "confidence": 80, "evidence": ["team management", "mentoring"]},
                                    {"skill": "Communication", "confidence": 90, "evidence": ["presentations", "documentation"]}
                                ]
                            }
                        }
                    })
                }
            }]
        }
        mock_post.return_value = mock_response
        yield mock_post


@pytest.fixture
def mock_vertex_ai_embeddings():
    """Mock VertexAI embedding generation"""
    with patch('google.cloud.aiplatform.TextEmbeddingModel') as mock_model:
        mock_instance = MagicMock()
        mock_instance.get_embeddings.return_value = [
            MagicMock(values=[0.1] * 768)  # Mock 768-dimensional embedding
        ]
        mock_model.from_pretrained.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_firebase_client():
    """Mock Firebase Firestore client"""
    with patch('firebase_admin.firestore.client') as mock_client:
        mock_db = MagicMock()
        
        # Mock collection and document operations
        mock_collection = MagicMock()
        mock_document = MagicMock()
        mock_document.get.return_value.exists = True
        mock_document.get.return_value.to_dict.return_value = {
            "candidate_id": "test_123",
            "enhanced_analysis": {"technical_skills": {"core_competencies": ["Python"]}},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        mock_collection.document.return_value = mock_document
        mock_collection.add.return_value = (None, mock_document)
        mock_collection.stream.return_value = [mock_document]
        
        mock_db.collection.return_value = mock_collection
        mock_client.return_value = mock_db
        
        yield mock_db


@pytest.fixture
def mock_postgres_connection():
    """Mock PostgreSQL connection for pgvector operations"""
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        
        # Mock vector search results
        mock_cursor.fetchall.return_value = [
            ("candidate_123", 0.95, {"name": "John Doe", "skills": ["Python", "React"]}),
            ("candidate_456", 0.89, {"name": "Jane Smith", "skills": ["Python", "Vue"]}),
            ("candidate_789", 0.82, {"name": "Bob Wilson", "skills": ["JavaScript", "Node.js"]})
        ]
        
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        yield mock_conn


# Test Data Factories
class TestDataFactory:
    """Factory for generating realistic test data"""
    
    @staticmethod
    def create_candidate_profile(
        candidate_id: str = None,
        name: str = "John Doe", 
        experience_years: int = 5,
        skills: List[str] = None
    ) -> Dict[str, Any]:
        """Create a realistic candidate profile"""
        if candidate_id is None:
            candidate_id = f"test_{uuid.uuid4().hex[:8]}"
        
        if skills is None:
            skills = ["Python", "React", "PostgreSQL", "AWS", "Docker"]
        
        return {
            "candidate_id": candidate_id,
            "name": name,
            "email": f"{name.lower().replace(' ', '.')}@example.com",
            "enhanced_analysis": {
                "career_trajectory": {
                    "current_level": "Senior" if experience_years >= 5 else "Mid-level",
                    "progression_speed": "fast",
                    "trajectory_type": "technical_leadership",
                    "years_experience": experience_years
                },
                "technical_skills": {
                    "core_competencies": skills,
                    "skill_depth": "expert" if experience_years >= 8 else "intermediate",
                    "learning_velocity": "high"
                },
                "explicit_skills": {
                    "technical_skills": [
                        {"skill": skill, "confidence": min(95, 70 + experience_years * 3), "evidence": [f"{experience_years} years experience", "multiple projects"]}
                        for skill in skills[:3]
                    ],
                    "soft_skills": [
                        {"skill": "Communication", "confidence": 85, "evidence": ["presentations", "documentation"]},
                        {"skill": "Problem Solving", "confidence": 90, "evidence": ["complex debugging", "system design"]}
                    ]
                },
                "leadership_scope": {
                    "has_leadership": experience_years >= 6,
                    "team_size": max(0, experience_years - 5),
                    "leadership_level": "team_lead" if experience_years >= 6 else "individual_contributor"
                },
                "company_pedigree": {
                    "company_tier": "enterprise",
                    "stability_pattern": "stable"
                },
                "executive_summary": {
                    "one_line_pitch": f"{experience_years}+ year {skills[0]} developer with {skills[1]} expertise",
                    "overall_rating": min(95, 70 + experience_years * 3)
                }
            },
            "embedding": [0.1 + i * 0.001 for i in range(768)],  # Mock 768-dim vector
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_job_description(
        job_title: str = "Senior Python Developer",
        required_skills: List[str] = None,
        experience_years: int = 5
    ) -> Dict[str, Any]:
        """Create a realistic job description"""
        if required_skills is None:
            required_skills = ["Python", "Django", "PostgreSQL", "AWS", "Docker"]
        
        return {
            "job_id": f"job_{uuid.uuid4().hex[:8]}",
            "title": job_title,
            "description": f"""
            We are seeking a {job_title} with {experience_years}+ years of experience.
            
            Required Skills:
            {', '.join(required_skills)}
            
            Responsibilities:
            - Design and implement scalable web applications
            - Collaborate with cross-functional teams
            - Mentor junior developers
            - Participate in code reviews
            """,
            "required_skills": required_skills,
            "experience_required": experience_years,
            "location": "San Francisco, CA",
            "employment_type": "Full-time",
            "salary_range": {"min": 120000, "max": 180000},
            "embedding": [0.2 + i * 0.001 for i in range(768)]  # Mock job embedding
        }


@pytest.fixture
def test_data_factory():
    """Test data factory fixture"""
    return TestDataFactory


@pytest.fixture
def sample_candidates(test_data_factory) -> List[Dict[str, Any]]:
    """Generate sample candidate profiles for testing"""
    return [
        test_data_factory.create_candidate_profile(
            candidate_id="candidate_1",
            name="Alice Johnson", 
            experience_years=8,
            skills=["Python", "React", "PostgreSQL", "AWS", "Kubernetes"]
        ),
        test_data_factory.create_candidate_profile(
            candidate_id="candidate_2", 
            name="Bob Smith",
            experience_years=5,
            skills=["JavaScript", "Vue.js", "MongoDB", "Node.js", "Docker"]
        ),
        test_data_factory.create_candidate_profile(
            candidate_id="candidate_3",
            name="Carol Davis",
            experience_years=12,
            skills=["Python", "Machine Learning", "TensorFlow", "Kubernetes", "GCP"]
        )
    ]


@pytest.fixture
def sample_job_description(test_data_factory) -> Dict[str, Any]:
    """Generate sample job description for testing"""
    return test_data_factory.create_job_description(
        job_title="Senior Full-Stack Developer",
        required_skills=["Python", "React", "PostgreSQL", "AWS", "Docker"],
        experience_years=5
    )


# Performance monitoring fixtures
@pytest.fixture
def performance_monitor():
    """Performance monitoring fixture"""
    class PerformanceMonitor:
        def __init__(self):
            self.metrics = {}
            self.start_times = {}
        
        def start_timer(self, operation: str):
            self.start_times[operation] = datetime.utcnow()
        
        def end_timer(self, operation: str):
            if operation in self.start_times:
                duration = datetime.utcnow() - self.start_times[operation]
                self.metrics[operation] = duration.total_seconds()
                del self.start_times[operation]
        
        def get_metrics(self) -> Dict[str, float]:
            return self.metrics.copy()
        
        def assert_performance(self, operation: str, max_seconds: float):
            """Assert that operation completed within time limit"""
            assert operation in self.metrics, f"Operation {operation} was not measured"
            assert self.metrics[operation] <= max_seconds, \
                f"Operation {operation} took {self.metrics[operation]:.3f}s, expected ≤{max_seconds}s"
    
    return PerformanceMonitor()


# Authentication fixtures
@pytest.fixture
def mock_firebase_auth():
    """Mock Firebase Authentication"""
    with patch('firebase_admin.auth') as mock_auth:
        mock_auth.verify_id_token.return_value = {
            'uid': 'test_user_123',
            'email': 'test@example.com',
            'email_verified': True,
            'role': 'recruiter'
        }
        yield mock_auth


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """Generate authentication headers for test requests"""
    return {
        'Authorization': 'Bearer test_jwt_token',
        'Content-Type': 'application/json'
    }


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Automatically cleanup test data after each test"""
    yield
    # Cleanup logic would go here in a real implementation
    # For now, we'll rely on mocks and temporary directories


# Error simulation fixtures
@pytest.fixture
def error_simulator():
    """Fixture for simulating various error conditions"""
    class ErrorSimulator:
        def __init__(self):
            self.active_errors = set()
        
        def simulate_network_error(self, service: str):
            """Simulate network connectivity issues"""
            self.active_errors.add(f"network_{service}")
        
        def simulate_service_unavailable(self, service: str):
            """Simulate service unavailability"""
            self.active_errors.add(f"unavailable_{service}")
        
        def simulate_database_timeout(self):
            """Simulate database timeout"""
            self.active_errors.add("db_timeout")
        
        def clear_errors(self):
            """Clear all simulated errors"""
            self.active_errors.clear()
        
        def has_error(self, error_type: str) -> bool:
            """Check if specific error is active"""
            return error_type in self.active_errors
    
    return ErrorSimulator()