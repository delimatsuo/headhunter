import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from scripts.batch_processor import BatchProcessor


@pytest.mark.asyncio
async def test_concurrent_batch_operations():
    """Test multiple batch operations running concurrently"""
    processor = BatchProcessor(max_concurrent=3)
    
    # Create two separate batches
    batch1 = [{"id": f"batch1_{i}"} for i in range(5)]
    batch2 = [{"id": f"batch2_{i}"} for i in range(5)]
    
    processed_items = []
    
    async def tracking_processor(item):
        await asyncio.sleep(0.1)
        processed_items.append(item["id"])
        return {"id": item["id"], "processed": True}
    
    # Run both batches concurrently
    task1 = asyncio.create_task(processor.process_batch(batch1, tracking_processor))
    task2 = asyncio.create_task(processor.process_batch(batch2, tracking_processor))
    
    results = await asyncio.gather(task1, task2)
    
    assert all(r.success for r in results)
    assert len(processed_items) == 10
    # Should have items from both batches interleaved due to concurrency
    batch1_items = [item for item in processed_items if "batch1" in item]
    batch2_items = [item for item in processed_items if "batch2" in item]
    assert len(batch1_items) == 5
    assert len(batch2_items) == 5


@pytest.mark.asyncio
async def test_async_exception_handling():
    """Test exception handling in async processing context"""
    processor = BatchProcessor(max_concurrent=2)
    
    exception_count = 0
    
    async def error_prone_processor(item):
        nonlocal exception_count
        if item["id"] == "error":
            exception_count += 1
            raise RuntimeError("Async processing error")
        await asyncio.sleep(0.05)
        return {"id": item["id"], "success": True}
    
    items = [
        {"id": "normal1"},
        {"id": "error"},
        {"id": "normal2"},
        {"id": "error"},  # Another error
        {"id": "normal3"}
    ]
    
    result = await processor.process_batch(items, error_prone_processor)
    
    assert result.success  # Overall success despite errors
    assert result.processed_count == 3  # 3 successful
    assert result.failed_count == 2    # 2 failed
    assert exception_count == 2        # Both exceptions were caught


@pytest.mark.asyncio 
async def test_async_timeout_handling():
    """Test handling of async operations that timeout"""
    processor = BatchProcessor(max_concurrent=2, timeout_seconds=0.2)
    
    async def slow_processor(item):
        # Some items take too long
        delay = 0.5 if item["id"] == "slow" else 0.05
        await asyncio.sleep(delay)
        return {"id": item["id"], "completed": True}
    
    items = [
        {"id": "fast1"},
        {"id": "slow"},     # This should timeout
        {"id": "fast2"},
        {"id": "slow"},     # This should also timeout
    ]
    
    result = await processor.process_batch(items, slow_processor)
    
    # Should handle timeouts gracefully
    assert result.processed_count == 2  # Only fast items completed
    assert result.failed_count == 2     # Slow items timed out


@pytest.mark.asyncio
async def test_cancellation_and_cleanup():
    """Test proper cleanup when async operations are cancelled"""
    processor = BatchProcessor(max_concurrent=3)
    
    cleanup_called = []
    
    async def processor_with_cleanup(item):
        try:
            await asyncio.sleep(1.0)  # Long operation
            return {"id": item["id"]}
        except asyncio.CancelledError:
            cleanup_called.append(item["id"])
            raise
    
    items = [{"id": str(i)} for i in range(5)]
    
    # Start processing and cancel after short delay
    task = asyncio.create_task(processor.process_batch(items, processor_with_cleanup))
    await asyncio.sleep(0.1)
    task.cancel()
    
    with pytest.raises(asyncio.CancelledError):
        await task
    
    # Should have called cleanup for cancelled items
    assert len(cleanup_called) > 0


@pytest.mark.asyncio
async def test_async_resource_management():
    """Test proper async resource management (context managers, etc.)"""
    processor = BatchProcessor()
    
    resource_states = []
    
    class AsyncResource:
        def __init__(self, name):
            self.name = name
            
        async def __aenter__(self):
            resource_states.append(f"{self.name}_opened")
            return self
            
        async def __aexit__(self, *args):
            resource_states.append(f"{self.name}_closed")
    
    async def resource_using_processor(item):
        async with AsyncResource(f"resource_{item['id']}") as resource:
            await asyncio.sleep(0.05)
            return {"id": item["id"], "resource": resource.name}
    
    items = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    
    result = await processor.process_batch(items, resource_using_processor)
    
    assert result.success
    assert result.processed_count == 3
    
    # All resources should have been properly opened and closed
    opened = [s for s in resource_states if "_opened" in s]
    closed = [s for s in resource_states if "_closed" in s]
    assert len(opened) == 3
    assert len(closed) == 3


@pytest.mark.asyncio
async def test_async_progress_tracking():
    """Test progress tracking with async callbacks"""
    processor = BatchProcessor()
    
    progress_updates = []
    
    async def progress_callback(processed, total, current_item):
        progress_updates.append({
            "processed": processed,
            "total": total,
            "current": current_item.get("id")
        })
    
    async def simple_processor(item):
        await asyncio.sleep(0.05)
        return {"id": item["id"]}
    
    items = [{"id": str(i)} for i in range(5)]
    
    result = await processor.process_batch(
        items, 
        simple_processor,
        progress_callback=progress_callback
    )
    
    assert result.success
    assert len(progress_updates) == 5
    assert progress_updates[-1]["processed"] == 5
    assert progress_updates[-1]["total"] == 5


@pytest.mark.asyncio
async def test_async_backpressure_handling():
    """Test handling of backpressure in async processing"""
    processor = BatchProcessor(max_concurrent=2)
    
    queue_sizes = []
    
    async def backpressure_processor(item):
        # Simulate varying processing speeds creating backpressure
        if int(item["id"]) % 3 == 0:
            await asyncio.sleep(0.3)  # Slow processing
        else:
            await asyncio.sleep(0.05)  # Fast processing
        
        # Record approximate queue size (pending tasks)
        queue_sizes.append(len(asyncio.all_tasks()) - 1)
        
        return {"id": item["id"], "processed": True}
    
    items = [{"id": str(i)} for i in range(10)]
    
    result = await processor.process_batch(items, backpressure_processor)
    
    assert result.success
    assert result.processed_count == 10
    
    # Queue sizes should vary due to backpressure
    assert max(queue_sizes) > min(queue_sizes)


@pytest.mark.asyncio
async def test_async_memory_cleanup():
    """Test that async processing doesn't leak memory"""
    processor = BatchProcessor(max_concurrent=5)
    
    initial_task_count = len(asyncio.all_tasks())
    
    async def memory_test_processor(item):
        # Create some temporary objects
        temp_data = [f"data_{i}" for i in range(100)]
        await asyncio.sleep(0.01)
        return {"id": item["id"], "data_length": len(temp_data)}
    
    items = [{"id": str(i)} for i in range(20)]
    
    result = await processor.process_batch(items, memory_test_processor)
    
    assert result.success
    
    # Allow some time for cleanup
    await asyncio.sleep(0.1)
    
    final_task_count = len(asyncio.all_tasks())
    
    # Should not have leaked tasks
    assert final_task_count <= initial_task_count + 1  # Allow for current task