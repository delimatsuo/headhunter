import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from scripts.firestore_streamer import FirestoreStreamer, StreamingResult


@pytest.fixture
def mock_firestore_client():
    """Mock Firestore client for testing"""
    mock_client = Mock()
    mock_batch = Mock()
    mock_client.batch.return_value = mock_batch
    mock_client.collection.return_value.document.return_value = Mock()
    return mock_client


@pytest.fixture
def sample_candidate_data():
    """Sample candidate data for testing"""
    return {
        "candidate_id": "test_123",
        "name": "John Doe",
        "intelligent_analysis": {
            "career_trajectory_analysis": {
                "current_level": "senior",
                "years_experience": 8
            },
            "explicit_skills": {
                "technical_skills": ["Python", "AWS"]
            },
            "recruiter_insights": {
                "overall_rating": "A",
                "one_line_pitch": "Senior backend engineer"
            }
        },
        "processing_metadata": {
            "timestamp": datetime.now(),
            "processor": "test_processor"
        }
    }


def test_firestore_streamer_initialization(mock_firestore_client):
    """Test FirestoreStreamer initializes with correct configuration"""
    streamer = FirestoreStreamer(
        firestore_client=mock_firestore_client,
        batch_size=100,
        collections=["candidates", "enriched_profiles"]
    )
    
    assert streamer.batch_size == 100
    assert streamer.collections == ["candidates", "enriched_profiles"]
    assert streamer.firestore_client == mock_firestore_client
    assert all(len(writes) == 0 for writes in streamer.pending_writes.values())
    assert streamer.stats.total_documents == 0


def test_add_document_accumulates_in_batches(mock_firestore_client, sample_candidate_data):
    """Test that documents accumulate in batches before writing"""
    streamer = FirestoreStreamer(firestore_client=mock_firestore_client, batch_size=2)
    
    # Add first document - should not trigger write
    result = streamer.add_document("candidates", "doc_1", sample_candidate_data)
    assert not result.written_immediately
    assert streamer.stats.pending_documents == 1
    assert "candidates" in streamer.pending_writes
    
    # Add second document - should trigger batch write
    result = streamer.add_document("candidates", "doc_2", sample_candidate_data)
    assert result.written_immediately  # Batch size reached
    assert streamer.stats.pending_documents == 0


def test_data_flattening_creates_search_fields(mock_firestore_client, sample_candidate_data):
    """Test that data is flattened for search optimization"""
    streamer = FirestoreStreamer(firestore_client=mock_firestore_client)
    
    flattened = streamer._flatten_for_search(sample_candidate_data)
    
    # Should create flattened fields for search
    assert "search_name" in flattened
    assert "search_skills" in flattened
    assert "search_level" in flattened
    assert "search_rating" in flattened
    
    # Verify flattening content
    assert flattened["search_name"] == "john doe"
    assert "python" in flattened["search_skills"]
    assert "aws" in flattened["search_skills"]
    assert flattened["search_level"] == "senior"
    assert flattened["search_rating"] == "a"


def test_upsert_logic_with_existing_documents(mock_firestore_client):
    """Test upsert behavior handles existing documents correctly"""
    streamer = FirestoreStreamer(firestore_client=mock_firestore_client)
    
    # Mock existing document
    mock_doc_ref = Mock()
    mock_doc_ref.get.return_value.exists = True
    mock_doc_ref.get.return_value.to_dict.return_value = {"existing": "data"}
    
    mock_firestore_client.collection.return_value.document.return_value = mock_doc_ref
    
    data = {"new": "data", "candidate_id": "test_123"}
    streamer.add_document("candidates", "test_123", data, upsert=True)
    
    # Should store the document reference in pending writes
    pending_items = streamer.pending_writes["candidates"]
    assert len(pending_items) == 1
    doc_ref, data, upsert_flag = pending_items[0]
    assert upsert_flag == True


@pytest.mark.asyncio
async def test_flush_batch_commits_pending_writes(mock_firestore_client, sample_candidate_data):
    """Test that flush_batch commits all pending writes"""
    streamer = FirestoreStreamer(firestore_client=mock_firestore_client, batch_size=10)
    
    # Add some documents without triggering auto-flush
    streamer.add_document("candidates", "doc_1", sample_candidate_data)
    streamer.add_document("enriched_profiles", "doc_2", sample_candidate_data)
    
    assert streamer.stats.pending_documents == 2
    
    # Flush manually
    result = await streamer.flush_batch()
    
    assert result.success
    assert result.documents_written == 2
    assert streamer.stats.pending_documents == 0
    assert streamer.stats.total_documents == 2


@pytest.mark.asyncio  
async def test_transaction_support_with_rollback(mock_firestore_client):
    """Test transaction support with rollback on failure"""
    streamer = FirestoreStreamer(firestore_client=mock_firestore_client)
    
    # Mock transaction
    mock_transaction = Mock()
    mock_firestore_client.transaction.return_value = mock_transaction
    
    # Simulate transaction failure
    mock_transaction.commit.side_effect = Exception("Transaction failed")
    
    data = {"test": "data"}
    
    with pytest.raises(Exception):
        await streamer.write_with_transaction("candidates", [("doc_1", data)])
    
    # Should attempt rollback
    mock_transaction.rollback.assert_called_once()


def test_checkpoint_creation_and_loading(mock_firestore_client, tmp_path):
    """Test checkpoint saving and loading for resume capability"""
    checkpoint_file = tmp_path / "checkpoint.json"
    
    streamer = FirestoreStreamer(
        firestore_client=mock_firestore_client,
        checkpoint_file=str(checkpoint_file)
    )
    
    # Create some state
    streamer.stats.total_documents = 100
    streamer.stats.failed_writes = 5
    
    # Save checkpoint
    streamer.save_checkpoint(last_processed_id="candidate_100")
    
    assert checkpoint_file.exists()
    
    # Load checkpoint in new streamer
    new_streamer = FirestoreStreamer(
        firestore_client=mock_firestore_client,
        checkpoint_file=str(checkpoint_file)
    )
    
    checkpoint = new_streamer.load_checkpoint()
    assert checkpoint["last_processed_id"] == "candidate_100"
    assert checkpoint["stats"]["total_documents"] == 100


@pytest.mark.asyncio
async def test_error_handling_and_retry_logic(mock_firestore_client):
    """Test error handling with retry logic"""
    streamer = FirestoreStreamer(firestore_client=mock_firestore_client, max_retries=3)
    
    # Mock batch commit to fail twice, then succeed
    mock_batch = mock_firestore_client.batch.return_value
    mock_batch.commit.side_effect = [Exception("Network error"), Exception("Timeout"), None]
    
    data = {"test": "data"}
    streamer.add_document("candidates", "doc_1", data)
    
    # Should succeed after retries
    result = await streamer.flush_batch()
    assert result.success
    assert result.retry_attempts == 2


def test_collection_validation_rejects_invalid_names(mock_firestore_client):
    """Test that invalid collection names are rejected"""
    with pytest.raises(ValueError, match="Invalid collection name"):
        FirestoreStreamer(
            firestore_client=mock_firestore_client,
            collections=["invalid-collection!"]
        )


def test_batch_size_optimization_metrics(mock_firestore_client):
    """Test that streamer tracks metrics for batch size optimization"""
    streamer = FirestoreStreamer(firestore_client=mock_firestore_client)
    
    # Add some documents and flush
    for i in range(5):
        streamer.add_document("candidates", f"doc_{i}", {"test": i})
    
    # Check metrics
    metrics = streamer.get_metrics()
    assert "average_batch_size" in metrics
    assert "write_latency_ms" in metrics
    assert "documents_per_second" in metrics
    assert "pending_documents" in metrics