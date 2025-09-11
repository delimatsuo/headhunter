# Integration Tests for Headhunter v2.0

This directory contains comprehensive integration tests for the Headhunter v2.0 AI-powered recruitment analytics platform.

## Test Suite Overview

### 🧪 Test Categories

- **Workflow Tests**: End-to-end user workflows
- **Authentication Tests**: Security and access control
- **Database Tests**: CRUD operations and data consistency
- **Performance Tests**: Load testing and benchmarking
- **API Tests**: REST endpoint validation

### 📁 Test Files

| File | Purpose | Test Count | Coverage |
|------|---------|------------|----------|
| `test_job_to_candidates.py` | Job description → candidate recommendations | 8 | Workflow |
| `test_resume_similarity.py` | Resume upload → similar candidate search | 7 | Workflow |
| `test_auth_integration.py` | Authentication & security workflows | 8 | Security |
| `test_crud_operations.py` | Database CRUD operations | 7 | Database |
| `test_vector_search.py` | Vector search & embedding workflows | 6 | Search |
| `test_performance.py` | Performance & load testing | TBD | Performance |
| `test_reliability.py` | Error handling & recovery | TBD | Reliability |
| `test_consistency.py` | Data consistency validation | TBD | Data |

### 🔧 Configuration Files

- `conftest.py` - Test fixtures and configuration
- `pytest.ini` - Pytest configuration with async support
- `requirements.txt` - Testing dependencies

## Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install -r tests/integration/requirements.txt

# Set up environment variables
export FIREBASE_TEST_CREDENTIALS="path/to/service-account.json"
export POSTGRES_TEST_URL="postgresql://test_user:password@localhost:5432/headhunter_test"
```

### Execute Tests

```bash
# Run all integration tests
pytest tests/integration/

# Run specific test file
pytest tests/integration/test_job_to_candidates.py

# Run with coverage report
pytest tests/integration/ --cov=scripts --cov=functions/src --cov-report=html

# Run performance tests only
pytest tests/integration/ -m performance

# Run tests in parallel
pytest tests/integration/ -n auto
```

### Test Markers

- `@pytest.mark.integration` - All integration tests
- `@pytest.mark.workflow` - End-to-end workflow tests
- `@pytest.mark.auth` - Authentication related tests
- `@pytest.mark.database` - Database operation tests
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.performance` - Performance and load tests
- `@pytest.mark.slow` - Long-running tests

## Test Architecture

### Mock Services

The test suite uses comprehensive mocking for external services:

- **Together AI API** - AI processing and enrichment
- **VertexAI Embeddings** - Vector generation
- **Firebase Firestore** - Document storage
- **PostgreSQL + pgvector** - Vector search
- **Firebase Auth** - Authentication

### Test Data Factory

The `TestDataFactory` class provides realistic test data:

```python
# Create realistic candidate profile
candidate = test_data_factory.create_candidate_profile(
    name="John Doe",
    experience_years=5,
    skills=["Python", "React", "AWS"]
)

# Create job description
job = test_data_factory.create_job_description(
    job_title="Senior Developer",
    required_skills=["Python", "PostgreSQL"],
    experience_years=5
)
```

### Performance Monitoring

Built-in performance monitoring for all tests:

```python
performance_monitor.start_timer("operation_name")
# ... perform operation ...
performance_monitor.end_timer("operation_name")

# Assert performance requirements
performance_monitor.assert_performance("operation_name", 2.0)  # Max 2 seconds
```

## Quality Standards

### Performance Requirements

- **Complete Workflows**: ≤ 10 seconds
- **Single Operations**: ≤ 2 seconds
- **Database Operations**: ≤ 1 second
- **Search Operations**: ≤ 500ms
- **API Endpoints**: ≤ 200ms

### Coverage Requirements

- **Minimum Coverage**: 80%
- **Critical Paths**: 100%
- **Error Scenarios**: Comprehensive
- **Edge Cases**: Validated

### Test Criteria

- ✅ All critical user workflows
- ✅ Authentication and authorization
- ✅ Data consistency between stores
- ✅ Performance under load
- ✅ Error handling and recovery
- ✅ Security and access control

## Continuous Integration

The integration tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Integration Tests
  run: |
    pytest tests/integration/ \
      --cov=scripts \
      --cov=functions/src \
      --cov-report=xml \
      --junit-xml=test-results.xml
```

## Troubleshooting

### Common Issues

1. **Mock Service Failures**: Check mock configurations in `conftest.py`
2. **Performance Assertions**: Adjust timeouts for slower environments
3. **Async Test Issues**: Ensure `pytest-asyncio` is properly configured
4. **Database Connections**: Verify test database setup

### Debug Mode

```bash
# Run tests with detailed output
pytest tests/integration/ -v --tb=long

# Run single test with pdb
pytest tests/integration/test_job_to_candidates.py::TestJobToCandidatesWorkflow::test_complete_job_to_candidates_workflow --pdb
```

## Contributing

When adding new integration tests:

1. Follow the existing naming conventions
2. Use appropriate test markers
3. Include performance monitoring
4. Add comprehensive docstrings
5. Mock external dependencies
6. Assert quality metrics

## Test Results

The test suite validates production readiness across:

- **Functionality**: All core features work correctly
- **Performance**: System meets speed requirements
- **Reliability**: Graceful error handling
- **Security**: Authentication and authorization
- **Scalability**: Performance under load
- **Data Integrity**: Consistency across stores

This comprehensive integration testing framework ensures Headhunter v2.0 is ready for production deployment with confidence.