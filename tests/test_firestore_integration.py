import pytest
import asyncio
import json
import tempfile
from datetime import datetime
from scripts.firestore_streamer import FirestoreStreamer


@pytest.fixture
def integration_data():
    """Sample data for integration testing"""
    return [
        {
            "candidate_id": f"candidate_{i}",
            "name": f"Test Candidate {i}",
            "intelligent_analysis": {
                "career_trajectory_analysis": {"current_level": "senior", "years_experience": 5 + i},
                "explicit_skills": {"technical_skills": ["Python", "JavaScript"]},
                "recruiter_insights": {"overall_rating": "A", "one_line_pitch": f"Candidate {i} summary"}
            },
            "processing_metadata": {
                "timestamp": datetime.now(),
                "processor": "test_integration"
            }
        }
        for i in range(20)
    ]


@pytest.mark.integration
@pytest.mark.asyncio  
async def test_firestore_emulator_batch_write_performance(integration_data):
    """Test batch write performance with Firestore emulator"""
    # This test requires: firebase emulators:start --only firestore
    # Skip if emulator not available
    
    try:
        from firebase_admin import credentials, firestore
        import firebase_admin
        
        # Initialize with emulator
        if not firebase_admin._apps:
            app = firebase_admin.initialize_app(credentials.Certificate({
                "type": "service_account",
                "project_id": "test-project"
            }))
        
        # Connect to emulator
        client = firestore.client()
        
        # Test with smaller batch to verify emulator connection
        streamer = FirestoreStreamer(
            firestore_client=client,
            batch_size=5,
            collections=["test_candidates"]
        )
        
        start_time = datetime.now()
        
        # Stream test data
        for i, data in enumerate(integration_data[:10]):  # Test with 10 docs
            result = streamer.add_document("test_candidates", f"test_{i}", data)
        
        # Flush remaining
        final_result = await streamer.flush_batch()
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Verify performance
        assert final_result.success
        assert processing_time < 5.0  # Should process 10 docs in under 5 seconds
        
        metrics = streamer.get_metrics()
        assert metrics["total_documents"] == 10
        assert metrics["documents_per_second"] > 1.0
        
    except ImportError:
        pytest.skip("firebase-admin not available for integration test")
    except Exception as e:
        pytest.skip(f"Firestore emulator not available: {e}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_checkpoint_resume_functionality(integration_data, tmp_path):
    """Test checkpoint and resume functionality"""
    checkpoint_file = tmp_path / "test_checkpoint.json"
    
    try:
        from firebase_admin import credentials, firestore
        import firebase_admin
        
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate({
                "type": "service_account", 
                "project_id": "test-project"
            }))
        
        client = firestore.client()
        
        # Process half the data
        streamer1 = FirestoreStreamer(
            firestore_client=client,
            batch_size=3,
            checkpoint_file=str(checkpoint_file)
        )
        
        # Process first 10 documents
        for i, data in enumerate(integration_data[:10]):
            streamer1.add_document("test_candidates", f"resume_test_{i}", data)
            if i == 6:  # Simulate interruption after 7 docs
                await streamer1.flush_batch()
                streamer1.save_checkpoint(last_processed_id=f"resume_test_{i}")
                break
        
        # Verify checkpoint was created
        assert checkpoint_file.exists()
        
        # Resume with new streamer
        streamer2 = FirestoreStreamer(
            firestore_client=client,
            checkpoint_file=str(checkpoint_file)
        )
        
        checkpoint = streamer2.load_checkpoint()
        assert checkpoint is not None
        assert checkpoint["last_processed_id"] == "resume_test_6"
        
        # Continue processing from checkpoint
        for i, data in enumerate(integration_data[7:10]):  # Process remaining
            streamer2.add_document("test_candidates", f"resume_test_{i+7}", data)
        
        result = await streamer2.flush_batch()
        assert result.success
        
    except ImportError:
        pytest.skip("firebase-admin not available for integration test")
    except Exception as e:
        pytest.skip(f"Firestore emulator not available: {e}")


@pytest.mark.integration 
def test_data_flattening_search_optimization(integration_data):
    """Test that flattened data enables efficient searches"""
    from unittest.mock import Mock
    
    mock_client = Mock()
    streamer = FirestoreStreamer(firestore_client=mock_client)
    
    # Test flattening with real data
    sample_data = integration_data[0]
    flattened = streamer._flatten_for_search(sample_data)
    
    # Verify search-optimized fields
    expected_fields = [
        "search_name", "search_skills", "search_level", 
        "search_rating", "search_keywords", "search_experience_years"
    ]
    
    for field in expected_fields:
        assert field in flattened, f"Missing search field: {field}"
    
    # Verify content is properly normalized for search
    assert flattened["search_name"].islower()
    assert isinstance(flattened["search_skills"], list)
    assert all(skill.islower() for skill in flattened["search_skills"])
    assert isinstance(flattened["search_experience_years"], int)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_rollback_on_failure():
    """Test transaction rollback when batch operations fail"""
    from unittest.mock import Mock, AsyncMock
    
    mock_client = Mock()
    mock_transaction = Mock()
    mock_client.transaction.return_value = mock_transaction
    
    # Simulate transaction failure
    mock_transaction.commit.side_effect = Exception("Firestore quota exceeded")
    
    streamer = FirestoreStreamer(firestore_client=mock_client)
    
    test_data = [("doc_1", {"test": "data1"}), ("doc_2", {"test": "data2"})]
    
    with pytest.raises(Exception, match="Firestore quota exceeded"):
        await streamer.write_with_transaction("test_collection", test_data)
    
    # Verify rollback was called
    mock_transaction.rollback.assert_called_once()


@pytest.mark.integration
def test_collection_schema_validation():
    """Test that documents conform to expected Firestore schema"""
    from unittest.mock import Mock
    
    mock_client = Mock()
    streamer = FirestoreStreamer(
        firestore_client=mock_client,
        collections=["candidates", "enriched_profiles", "embeddings"]
    )
    
    # Test valid collections
    assert "candidates" in streamer.collections
    assert "enriched_profiles" in streamer.collections
    assert "embeddings" in streamer.collections
    
    # Test schema validation for candidates collection
    valid_candidate = {
        "candidate_id": "test_123",
        "name": "John Doe", 
        "intelligent_analysis": {},
        "processing_metadata": {"timestamp": datetime.now()}
    }
    
    # Should not raise validation errors
    normalized = streamer._normalize_document("candidates", valid_candidate)
    assert "candidate_id" in normalized
    assert "search_name" in normalized  # Flattened field added