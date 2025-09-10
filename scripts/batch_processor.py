import asyncio
import json
import csv
import psutil
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """Result of batch processing operation"""
    success: bool
    processed_count: int = 0
    failed_count: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    estimated_cost: float = 0.0
    processing_time_seconds: float = 0.0
    peak_memory_mb: float = 0.0


@dataclass
class ProcessingStats:
    """Statistics for batch processing operations"""
    total_items: int = 0
    processed: int = 0
    failed: int = 0
    start_time: Optional[datetime] = None
    response_times_ms: List[float] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        return self.processed / max(1, self.total_items)
    
    @property
    def failure_rate(self) -> float:
        return self.failed / max(1, self.total_items)
    
    @property
    def average_response_time_ms(self) -> float:
        return sum(self.response_times_ms) / len(self.response_times_ms) if self.response_times_ms else 0.0
    
    @property
    def throughput_per_second(self) -> float:
        if not self.start_time:
            return 0.0
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return self.processed / elapsed if elapsed > 0 else 0.0


class BatchProcessor:
    """Async batch processor with concurrency control and progress tracking"""
    
    def __init__(
        self,
        max_concurrent: int = 10,
        cost_per_request: float = 0.0,
        max_estimated_cost: float = float('inf'),
        checkpoint_file: Optional[str] = None,
        adaptive_concurrency: bool = False,
        monitor_memory: bool = False,
        timeout_seconds: Optional[float] = None
    ):
        self.max_concurrent = max_concurrent
        self.cost_per_request = cost_per_request
        self.max_estimated_cost = max_estimated_cost
        self.checkpoint_file = checkpoint_file
        self.adaptive_concurrency = adaptive_concurrency
        self.monitor_memory = monitor_memory
        self.timeout_seconds = timeout_seconds
        
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.stats = ProcessingStats()
        self._shutdown_requested = False
        self._current_concurrency = max_concurrent
    
    async def load_from_csv(self, file_path: str) -> List[Dict[str, Any]]:
        """Load candidates from CSV file"""
        candidates = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    candidates.append(dict(row))
            logger.info(f"📁 Loaded {len(candidates)} candidates from CSV: {file_path}")
            return candidates
        except Exception as e:
            logger.error(f"Failed to load CSV {file_path}: {e}")
            raise
    
    async def load_from_json(self, file_path: str) -> List[Dict[str, Any]]:
        """Load candidates from JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                candidates = json.load(f)
            
            if not isinstance(candidates, list):
                raise ValueError("JSON file must contain a list of candidates")
            
            logger.info(f"📁 Loaded {len(candidates)} candidates from JSON: {file_path}")
            return candidates
        except Exception as e:
            logger.error(f"Failed to load JSON {file_path}: {e}")
            raise
    
    def request_shutdown(self):
        """Request graceful shutdown of processing"""
        self._shutdown_requested = True
        logger.info("🛑 Graceful shutdown requested")
    
    async def process_batch(
        self,
        items: List[Dict[str, Any]],
        processor_func: Callable,
        progress_callback: Optional[Callable] = None
    ) -> BatchResult:
        """Process a batch of items with concurrency control"""
        start_time = datetime.now()
        
        # Initialize stats
        self.stats.total_items = len(items)
        self.stats.start_time = start_time
        self.stats.processed = 0
        self.stats.failed = 0
        
        # Cost estimation check
        estimated_cost = len(items) * self.cost_per_request
        if estimated_cost > self.max_estimated_cost:
            return BatchResult(
                success=False,
                estimated_cost=estimated_cost,
                error_message=f"Estimated cost ${estimated_cost:.2f} exceeds limit ${self.max_estimated_cost:.2f}"
            )
        
        logger.info(f"🚀 Starting batch processing: {len(items)} items, estimated cost: ${estimated_cost:.2f}")
        
        results = []
        peak_memory = 0.0
        
        try:
            # Create tasks with semaphore control
            tasks = []
            
            # Create tasks in smaller batches to allow for more responsive shutdown
            batch_size = min(self.max_concurrent, 5)  # Create max 5 tasks at a time
            
            for batch_start in range(0, len(items), batch_size):
                if self._shutdown_requested:
                    logger.info("🛑 Shutdown requested, stopping task creation")
                    break
                
                batch_end = min(batch_start + batch_size, len(items))
                batch_items = items[batch_start:batch_end]
                
                # Create batch of tasks
                for i, item in enumerate(batch_items, start=batch_start):
                    if self._shutdown_requested:
                        logger.info("🛑 Shutdown requested during batch creation")
                        break
                        
                    task = asyncio.create_task(
                        self._process_item_with_semaphore(item, processor_func, i, progress_callback)
                    )
                    tasks.append(task)
                
                # Short yield to allow shutdown requests to be processed
                await asyncio.sleep(0.001)
                
                # Monitor memory if requested
                if self.monitor_memory:
                    current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                    peak_memory = max(peak_memory, current_memory)
            
            # Wait for all tasks to complete or handle shutdown
            if self._shutdown_requested and tasks:
                logger.info(f"🛑 Cancelling {sum(1 for t in tasks if not t.done())} remaining tasks")
                # Cancel remaining tasks that haven't started yet
                for task in tasks:
                    if not task.done():
                        task.cancel()
                
                completed_results = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                completed_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(completed_results):
                if isinstance(result, asyncio.CancelledError):
                    self.stats.failed += 1
                    logger.debug("Task was cancelled due to shutdown")
                elif isinstance(result, Exception):
                    self.stats.failed += 1
                    logger.error(f"Task {i} failed: {result}")
                elif result is not None:
                    results.append(result)
                    self.stats.processed += 1
                else:
                    self.stats.failed += 1
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            success = not self._shutdown_requested and len(results) > 0
            error_message = "Processing interrupted by shutdown request" if self._shutdown_requested else None
            
            return BatchResult(
                success=success,
                processed_count=self.stats.processed,
                failed_count=self.stats.failed,
                results=results,
                error_message=error_message,
                estimated_cost=estimated_cost,
                processing_time_seconds=processing_time,
                peak_memory_mb=peak_memory
            )
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            return BatchResult(
                success=False,
                error_message=str(e),
                estimated_cost=estimated_cost,
                processing_time_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    async def _process_item_with_semaphore(
        self,
        item: Dict[str, Any],
        processor_func: Callable,
        index: int,
        progress_callback: Optional[Callable] = None
    ) -> Optional[Dict[str, Any]]:
        """Process single item with semaphore control"""
        async with self._semaphore:
            if self._shutdown_requested:
                return None
            
            try:
                start_time = datetime.now()
                
                # Simple approach: just call the processor function directly
                # For graceful shutdown in long-running operations, we'll rely on
                # the batch-level task cancellation rather than individual item interruption
                if self.timeout_seconds:
                    result = await asyncio.wait_for(
                        processor_func(item),
                        timeout=self.timeout_seconds
                    )
                else:
                    result = await processor_func(item)
                
                # Check shutdown after completion
                if self._shutdown_requested:
                    return None
                
                # Record response time
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                self.stats.response_times_ms.append(response_time)
                
                # Adaptive concurrency adjustment
                if self.adaptive_concurrency:
                    await self._adjust_concurrency(response_time)
                
                # Progress callback - use index + 1 for progress count since we're processing concurrently
                if progress_callback:
                    await progress_callback(index + 1, self.stats.total_items, item)
                
                return result
                
            except asyncio.TimeoutError:
                logger.warning(f"Item {index} timed out after {self.timeout_seconds}s")
                return None
            except Exception as e:
                logger.error(f"Error processing item {index}: {e}")
                raise
    
    async def _adjust_concurrency(self, response_time_ms: float):
        """Adjust concurrency based on response times"""
        if len(self.stats.response_times_ms) < 10:
            return  # Need enough samples
        
        avg_response_time = self.stats.average_response_time_ms
        
        # Simple adaptive logic
        if response_time_ms > avg_response_time * 2:
            # Slow responses, reduce concurrency
            self._current_concurrency = max(1, self._current_concurrency - 1)
        elif response_time_ms < avg_response_time * 0.5:
            # Fast responses, increase concurrency
            self._current_concurrency = min(self.max_concurrent, self._current_concurrency + 1)
    
    async def save_checkpoint(self, last_processed_id: str, additional_data: Optional[Dict] = None):
        """Save processing checkpoint"""
        if not self.checkpoint_file:
            return
        
        checkpoint = {
            "last_processed_id": last_processed_id,
            "timestamp": datetime.now().isoformat(),
            "stats": {
                "total_items": self.stats.total_items,
                "processed": self.stats.processed,
                "failed": self.stats.failed,
                "success_rate": self.stats.success_rate
            },
            "additional_data": additional_data or {}
        }
        
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(checkpoint, f, indent=2)
            logger.info(f"💾 Checkpoint saved: {last_processed_id}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    async def load_checkpoint(self) -> Optional[Dict]:
        """Load processing checkpoint"""
        if not self.checkpoint_file:
            return None
        
        try:
            with open(self.checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
            logger.info(f"📁 Checkpoint loaded: {checkpoint.get('last_processed_id')}")
            return checkpoint
        except FileNotFoundError:
            logger.info("No checkpoint file found")
            return None
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None