import pytest
import asyncio
import tempfile
import json
import csv
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from scripts.batch_processor import BatchProcessor, BatchResult, ProcessingStats


@pytest.fixture
def sample_csv_data():
    """Sample CSV data for testing"""
    return """candidate_id,name,role_level,resume_file,recruiter_comments
1,John Doe,Senior,resumes/john.pdf,Great technical skills
2,Jane Smith,Mid,resumes/jane.pdf,Strong communication
3,Bob Wilson,Senior,resumes/bob.pdf,Leadership potential"""


@pytest.fixture
def sample_json_data():
    """Sample JSON data for testing"""
    return [
        {
            "candidate_id": "1",
            "name": "John Doe", 
            "role_level": "Senior",
            "experience": "8 years Python development",
            "education": "BS Computer Science"
        },
        {
            "candidate_id": "2",
            "name": "Jane Smith",
            "role_level": "Mid",
            "experience": "4 years frontend development", 
            "education": "BS Information Systems"
        }
    ]


@pytest.fixture
def mock_processor_func():
    """Mock processing function for testing"""
    async def mock_process(candidate):
        await asyncio.sleep(0.01)  # Simulate processing time
        if candidate.get("candidate_id") == "error":
            raise ValueError("Processing error")
        return {
            "candidate_id": candidate["candidate_id"],
            "processed": True,
            "analysis": {"rating": "A"}
        }
    return mock_process


def test_batch_processor_initialization():
    """Test BatchProcessor initializes with correct configuration"""
    processor = BatchProcessor(
        max_concurrent=5,
        cost_per_request=0.001,
        max_estimated_cost=10.0
    )
    
    assert processor.max_concurrent == 5
    assert processor.cost_per_request == 0.001
    assert processor.max_estimated_cost == 10.0
    assert processor.stats.total_items == 0
    assert processor.stats.processed == 0
    assert processor._semaphore._value == 5


@pytest.mark.asyncio
async def test_csv_parsing(sample_csv_data, tmp_path):
    """Test CSV file parsing"""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(sample_csv_data)
    
    processor = BatchProcessor()
    candidates = await processor.load_from_csv(str(csv_file))
    
    assert len(candidates) == 3
    assert candidates[0]["candidate_id"] == "1"
    assert candidates[0]["name"] == "John Doe"
    assert candidates[1]["role_level"] == "Mid"


@pytest.mark.asyncio
async def test_json_parsing(sample_json_data, tmp_path):
    """Test JSON file parsing"""
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(sample_json_data))
    
    processor = BatchProcessor()
    candidates = await processor.load_from_json(str(json_file))
    
    assert len(candidates) == 2
    assert candidates[0]["candidate_id"] == "1"
    assert candidates[1]["name"] == "Jane Smith"


@pytest.mark.asyncio
async def test_concurrency_control_with_semaphore(mock_processor_func):
    """Test that semaphore limits concurrent processing"""
    processor = BatchProcessor(max_concurrent=2)
    
    # Create test data
    candidates = [{"candidate_id": str(i)} for i in range(5)]
    
    # Track concurrent executions
    concurrent_count = 0
    max_concurrent_seen = 0
    
    async def tracking_processor(candidate):
        nonlocal concurrent_count, max_concurrent_seen
        concurrent_count += 1
        max_concurrent_seen = max(max_concurrent_seen, concurrent_count)
        
        await asyncio.sleep(0.1)  # Simulate work
        
        concurrent_count -= 1
        return {"candidate_id": candidate["candidate_id"], "processed": True}
    
    result = await processor.process_batch(candidates, tracking_processor)
    
    assert result.success
    assert result.processed_count == 5
    assert max_concurrent_seen <= 2  # Should not exceed semaphore limit


@pytest.mark.asyncio
async def test_cost_estimation_and_safeguards():
    """Test cost estimation prevents expensive operations"""
    processor = BatchProcessor(
        cost_per_request=1.0,
        max_estimated_cost=3.0
    )
    
    # 5 items * $1.0 each = $5.0 > $3.0 limit
    candidates = [{"candidate_id": str(i)} for i in range(5)]
    
    async def dummy_processor(candidate):
        return {"processed": True}
    
    result = await processor.process_batch(candidates, dummy_processor)
    
    assert not result.success
    assert "exceeds limit" in result.error_message.lower()
    assert result.estimated_cost == 5.0


@pytest.mark.asyncio
async def test_checkpoint_saving_and_loading(tmp_path):
    """Test checkpoint save/load functionality"""
    checkpoint_file = tmp_path / "checkpoint.json"
    processor = BatchProcessor(checkpoint_file=str(checkpoint_file))
    
    # Simulate some processing
    processor.stats.total_items = 100
    processor.stats.processed = 50
    processor.stats.failed = 2
    
    # Save checkpoint
    await processor.save_checkpoint("candidate_50")
    
    assert checkpoint_file.exists()
    
    # Load in new processor
    new_processor = BatchProcessor(checkpoint_file=str(checkpoint_file))
    checkpoint = await new_processor.load_checkpoint()
    
    assert checkpoint is not None
    assert checkpoint["last_processed_id"] == "candidate_50"
    assert checkpoint["stats"]["processed"] == 50


@pytest.mark.asyncio
async def test_graceful_shutdown_handling():
    """Test graceful shutdown stops processing cleanly"""
    processor = BatchProcessor()
    
    candidates = [{"candidate_id": str(i)} for i in range(10)]
    
    async def slow_processor(candidate):
        await asyncio.sleep(0.5)  # Slow processing
        return {"candidate_id": candidate["candidate_id"]}
    
    # Start processing and request shutdown after short delay
    process_task = asyncio.create_task(processor.process_batch(candidates, slow_processor))
    
    await asyncio.sleep(0.1)  # Let some processing start
    processor.request_shutdown()
    
    result = await process_task
    
    assert not result.success  # Should be marked as incomplete
    assert "shutdown" in result.error_message.lower()
    assert result.processed_count < len(candidates)  # Should have stopped early


@pytest.mark.asyncio
async def test_error_handling_continues_processing(mock_processor_func):
    """Test that individual errors don't stop batch processing"""
    processor = BatchProcessor()
    
    candidates = [
        {"candidate_id": "1"},
        {"candidate_id": "error"},  # This will cause an error
        {"candidate_id": "3"},
    ]
    
    result = await processor.process_batch(candidates, mock_processor_func)
    
    assert result.success  # Overall success despite individual error
    assert result.processed_count == 2  # Two successful
    assert result.failed_count == 1     # One failed
    assert len(result.results) == 2     # Only successful results returned


@pytest.mark.asyncio
async def test_adaptive_concurrency_adjustment():
    """Test adaptive concurrency based on response times"""
    processor = BatchProcessor(
        max_concurrent=10,
        adaptive_concurrency=True
    )
    
    response_times = []
    
    async def variable_time_processor(candidate):
        # Simulate varying response times
        delay = 0.01 if int(candidate["candidate_id"]) < 5 else 0.5
        response_times.append(delay)
        await asyncio.sleep(delay)
        return {"candidate_id": candidate["candidate_id"]}
    
    candidates = [{"candidate_id": str(i)} for i in range(8)]
    
    result = await processor.process_batch(candidates, variable_time_processor)
    
    assert result.success
    # Should have adjusted concurrency based on response times
    # (Implementation details depend on adaptive logic)


@pytest.mark.asyncio
async def test_memory_usage_monitoring():
    """Test memory usage monitoring during processing"""
    processor = BatchProcessor(monitor_memory=True)
    
    candidates = [{"candidate_id": str(i)} for i in range(5)]
    
    async def memory_heavy_processor(candidate):
        # Simulate some memory usage
        data = [i for i in range(1000)]  # Small memory allocation
        return {"candidate_id": candidate["candidate_id"], "data_size": len(data)}
    
    result = await processor.process_batch(candidates, memory_heavy_processor)
    
    assert result.success
    assert hasattr(result, 'peak_memory_mb')
    assert result.peak_memory_mb > 0


def test_processing_stats_calculations():
    """Test ProcessingStats calculations"""
    stats = ProcessingStats()
    stats.total_items = 100
    stats.processed = 75
    stats.failed = 5
    stats.start_time = datetime.now()
    
    # Add some response times
    stats.response_times_ms = [100, 200, 150, 300, 250]
    
    assert stats.success_rate == 0.75  # 75/100
    assert stats.failure_rate == 0.05  # 5/100
    assert stats.average_response_time_ms == 200.0  # Mean of response times
    assert stats.throughput_per_second > 0


@pytest.mark.asyncio
async def test_resume_from_checkpoint_functionality(tmp_path):
    """Test resuming processing from checkpoint"""
    checkpoint_file = tmp_path / "resume_test.json"
    
    # First processor processes half the data
    processor1 = BatchProcessor(checkpoint_file=str(checkpoint_file))
    candidates = [{"candidate_id": str(i)} for i in range(10)]
    
    async def checkpoint_processor(candidate):
        # Save checkpoint every 3 items
        if int(candidate["candidate_id"]) % 3 == 0:
            await processor1.save_checkpoint(candidate["candidate_id"])
        return {"candidate_id": candidate["candidate_id"]}
    
    # Process first 6 items
    partial_candidates = candidates[:6]
    result1 = await processor1.process_batch(partial_candidates, checkpoint_processor)
    
    assert result1.success
    assert result1.processed_count == 6
    
    # Second processor resumes from checkpoint
    processor2 = BatchProcessor(checkpoint_file=str(checkpoint_file))
    checkpoint = await processor2.load_checkpoint()
    
    assert checkpoint is not None
    # Resume processing would skip already processed items
    # (Implementation details depend on resume logic)