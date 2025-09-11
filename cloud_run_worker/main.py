"""
Cloud Run Pub/Sub Worker for Candidate Processing
FastAPI service that processes candidate enrichment requests via Pub/Sub
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

from .config import Config
from .pubsub_handler import PubSubHandler
from .candidate_processor import CandidateProcessor
from .models import PubSubMessage, ProcessingResult
from .metrics import MetricsCollector

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Headhunter Candidate Processing Worker",
    description="Cloud Run service for processing candidate enrichment via Pub/Sub",
    version="1.0.0"
)

# Initialize components - conditional for testing
try:
    config = Config()
    pubsub_handler = PubSubHandler(config)
    candidate_processor = CandidateProcessor(config)
    metrics = MetricsCollector(config)
except ValueError as e:
    # Allow imports during testing when env vars may not be set
    logger.warning(f"Configuration warning: {e}")
    config = None
    pubsub_handler = None
    candidate_processor = None
    metrics = None


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    try:
        # Quick health checks
        firestore_healthy = await candidate_processor.health_check()
        together_ai_healthy = await candidate_processor.together_ai_client.health_check()
        
        status = "healthy" if firestore_healthy and together_ai_healthy else "degraded"
        
        return {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "components": {
                "firestore": "healthy" if firestore_healthy else "unhealthy",
                "together_ai": "healthy" if together_ai_healthy else "unhealthy"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
        )


@app.get("/metrics")
async def get_metrics():
    """Return processing metrics for monitoring"""
    return {
        "messages_processed": metrics.get_messages_processed(),
        "processing_times": metrics.get_average_processing_time(),
        "error_count": metrics.get_error_count(),
        "success_rate": metrics.get_success_rate(),
        "active_processors": metrics.get_active_processors(),
        "timestamp": datetime.now().isoformat()
    }


@app.post("/pubsub/webhook")
async def pubsub_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Pub/Sub webhook endpoint for processing candidate messages
    Cloud Run will receive Pub/Sub messages here
    """
    try:
        # Parse incoming Pub/Sub message
        message_data = await request.json()
        logger.info(f"Received Pub/Sub message: {message_data.get('message', {}).get('messageId')}")
        
        # Process message in background to avoid timeout
        background_tasks.add_task(process_candidate_message, message_data)
        
        # Return immediate response to Pub/Sub
        return {
            "status": "accepted",
            "message_id": message_data.get("message", {}).get("messageId"),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        metrics.increment_error_count()
        
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


async def process_candidate_message(message_data: Dict[str, Any]) -> ProcessingResult:
    """
    Main processing function for candidate enrichment
    This is where the actual work happens
    """
    start_time = datetime.now()
    candidate_id = None
    
    try:
        # Parse Pub/Sub message
        parsed_message = pubsub_handler.parse_message(message_data)
        candidate_id = parsed_message.candidate_id
        
        logger.info(f"Processing candidate: {candidate_id}")
        metrics.increment_messages_processed()
        metrics.set_active_processor(candidate_id, True)
        
        # Fetch candidate data
        candidate_data = await candidate_processor.fetch_candidate_data(candidate_id)
        if not candidate_data:
            raise ValueError(f"Candidate {candidate_id} not found")
        
        # Process with Together AI
        enriched_data = await candidate_processor.process_with_together_ai(candidate_data)
        
        # Store results
        success = await candidate_processor.store_processing_result(candidate_id, enriched_data)
        
        if not success:
            raise Exception("Failed to store processing results")
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        metrics.record_processing_time(processing_time)
        
        logger.info(f"Successfully processed candidate {candidate_id} in {processing_time:.2f}s")
        
        return ProcessingResult(
            candidate_id=candidate_id,
            status="completed",
            processing_time_seconds=processing_time,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        error_msg = f"Processing failed for candidate {candidate_id}: {e}"
        logger.error(error_msg)
        metrics.increment_error_count()
        
        # Send to dead letter queue for manual review
        if candidate_id:
            await pubsub_handler.send_to_dead_letter_queue(message_data, error_msg)
        
        return ProcessingResult(
            candidate_id=candidate_id,
            status="failed",
            error=str(e),
            timestamp=datetime.now().isoformat()
        )
        
    finally:
        if candidate_id:
            metrics.set_active_processor(candidate_id, False)


@app.post("/process/batch")
async def process_batch(request: Request):
    """
    Endpoint for batch processing multiple candidates
    Useful for manual triggering or batch jobs
    """
    try:
        data = await request.json()
        candidate_ids = data.get("candidate_ids", [])
        
        if not candidate_ids:
            raise HTTPException(status_code=400, detail="No candidate IDs provided")
        
        logger.info(f"Starting batch processing for {len(candidate_ids)} candidates")
        
        # Process candidates concurrently (with concurrency limit)
        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent processes
        
        async def process_with_semaphore(candidate_id):
            async with semaphore:
                fake_message = {
                    "message": {
                        "data": json.dumps({
                            "candidate_id": candidate_id,
                            "action": "enrich_profile"
                        }),
                        "messageId": f"batch_{candidate_id}",
                        "publishTime": datetime.now().isoformat()
                    }
                }
                return await process_candidate_message(fake_message)
        
        results = await asyncio.gather(
            *[process_with_semaphore(cid) for cid in candidate_ids],
            return_exceptions=True
        )
        
        # Summarize results
        successful = sum(1 for r in results if isinstance(r, ProcessingResult) and r.status == "completed")
        failed = len(results) - successful
        
        return {
            "status": "completed",
            "total_candidates": len(candidate_ids),
            "successful": successful,
            "failed": failed,
            "results": [r.dict() if isinstance(r, ProcessingResult) else {"error": str(r)} for r in results],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Batch processing error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@app.get("/status/{candidate_id}")
async def get_processing_status(candidate_id: str):
    """Get processing status for a specific candidate"""
    try:
        status = candidate_processor.get_processing_status(candidate_id)
        return {
            "candidate_id": candidate_id,
            "status": status.value if status else "unknown",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting status for {candidate_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup"""
    logger.info("Starting Headhunter Candidate Processing Worker")
    logger.info(f"Configuration: Project={config.project_id}, Topic={config.pubsub_topic}")
    
    # Initialize connections
    await candidate_processor.initialize()
    await pubsub_handler.initialize()
    
    logger.info("Worker initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Candidate Processing Worker")
    
    # Graceful shutdown
    await candidate_processor.shutdown()
    await pubsub_handler.shutdown()
    
    logger.info("Worker shutdown complete")


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"error": str(exc), "type": "validation_error"}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "type": "server_error"}
    )


if __name__ == "__main__":
    # For local development
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        reload=True,
        log_level="info"
    )