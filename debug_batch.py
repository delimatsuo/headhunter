#!/usr/bin/env python3
"""Debug BatchProcessor issues"""

import asyncio
import sys
import os
import logging

# Set up logging to see what's happening
logging.basicConfig(level=logging.DEBUG)

sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

from batch_processor import BatchProcessor

async def simple_processor(item):
    try:
        print(f"Processing {item['candidate_id']}")
        await asyncio.sleep(0.1)
        print(f"Finished {item['candidate_id']}")
        return {"candidate_id": item["candidate_id"], "processed": True}
    except Exception as e:
        print(f"Exception in simple_processor: {e}")
        raise

async def main():
    processor = BatchProcessor(max_concurrent=2)
    candidates = [{"candidate_id": str(i)} for i in range(3)]
    
    print("Starting batch processing...")
    result = await processor.process_batch(candidates, simple_processor)
    
    print(f"Result success: {result.success}")
    print(f"Processed count: {result.processed_count}")
    print(f"Failed count: {result.failed_count}")
    print(f"Results: {result.results}")
    print(f"Error message: {result.error_message}")

if __name__ == "__main__":
    asyncio.run(main())