#!/usr/bin/env python3
"""
Local Webhook Server
FastAPI server that receives webhook requests from Firebase Cloud Functions
and processes them using local Ollama LLM pipeline
"""

import asyncio
import logging
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

# Import existing processing components
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / 'scripts'))
sys.path.append(str(REPO_ROOT / 'config'))

from llm_processor import LLMProcessor
from cloud_integration import CloudAPIClient
from webhook_config import get_config, WebhookIntegrationConfig
from queue import Queue, Empty
import threading
from dataclasses import dataclass, asdict


# Pydantic models for API requests/responses
class CandidateData(BaseModel):
    """Input data for candidate processing"""
    candidate_id: str
    name: Optional[str] = None
    resume_text: Optional[str] = None
    resume_file_url: Optional[str] = None
    recruiter_comments: Optional[str] = None
    role_level: Optional[str] = None
    priority: int = Field(default=1, ge=1, le=3)  # 1=low, 2=medium, 3=high
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('candidate_id')
    def validate_candidate_id(cls, v):
        if not v or not v.strip():
            raise ValueError('candidate_id is required and cannot be empty')
        return v.strip()


class WebhookRequest(BaseModel):
    """Webhook request from cloud functions"""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: str = Field(..., regex="^(process_candidate|process_batch|health_check)$")
    data: Union[CandidateData, List[CandidateData], Dict[str, Any]]
    callback_url: Optional[str] = None
    timeout: Optional[int] = Field(default=300, ge=30, le=3600)
    timestamp: datetime = Field(default_factory=datetime.now)


class ProcessingStatus(BaseModel):
    """Processing status response"""
    request_id: str
    status: str  # queued, processing, completed, failed
    progress: float = Field(ge=0.0, le=1.0)
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class QueueStats(BaseModel):
    """Queue statistics"""
    queue_size: int
    processing_count: int
    completed_count: int
    failed_count: int
    worker_count: int
    uptime: float


class HealthStatus(BaseModel):
    """System health status"""
    status: str
    timestamp: datetime
    ollama_status: Dict[str, Any]
    queue_stats: QueueStats
    system_info: Dict[str, Any]


@dataclass
class ProcessingJob:
    """Job for processing queue"""
    request_id: str
    action: str
    data: Any
    callback_url: Optional[str]
    timeout: int
    priority: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "queued"  # queued, processing, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: float = 0.0
    
    def to_status(self) -> ProcessingStatus:
        """Convert to ProcessingStatus for API response"""
        processing_time = None
        if self.started_at and self.completed_at:
            processing_time = (self.completed_at - self.started_at).total_seconds()
        
        return ProcessingStatus(
            request_id=self.request_id,
            status=self.status,
            progress=self.progress,
            message=f"Job {self.status}",
            result=self.result,
            error=self.error,
            processing_time=processing_time,
            timestamp=datetime.now()
        )


class WebhookQueueManager:
    """Queue manager for webhook processing requests"""
    
    def __init__(self, config: WebhookIntegrationConfig):
        self.config = config
        self.queue = Queue(maxsize=config.queue.max_queue_size)
        self.priority_queues = {
            1: Queue(maxsize=config.queue.max_queue_size // 3),  # Low priority
            2: Queue(maxsize=config.queue.max_queue_size // 3),  # Medium priority  
            3: Queue(maxsize=config.queue.max_queue_size // 3),  # High priority
        }
        self.processing_jobs: Dict[str, ProcessingJob] = {}
        self.completed_jobs: Dict[str, ProcessingJob] = {}
        self.workers: List[threading.Thread] = []
        self.running = False
        self.stats_start_time = datetime.now()
        self.logger = logging.getLogger(__name__)
    
    def start_workers(self):
        """Start worker threads"""
        if self.running:
            return
        
        self.running = True
        for i in range(self.config.queue.worker_count):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"WebhookWorker-{i+1}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        self.logger.info(f"Started {len(self.workers)} webhook workers")
    
    def stop_workers(self):
        """Stop worker threads"""
        self.running = False
        
        # Add sentinel values to wake up workers
        for _ in self.workers:
            try:
                self.queue.put(None, timeout=1)
            except:
                pass
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5)
        
        self.workers.clear()
        self.logger.info("Stopped webhook workers")
    
    def add_job(self, job: ProcessingJob) -> bool:
        """Add job to appropriate priority queue"""
        try:
            # Add to priority queue first
            priority_queue = self.priority_queues.get(job.priority)
            if priority_queue:
                priority_queue.put(job, timeout=1)
            
            # Add to main queue
            self.queue.put(job, timeout=1)
            self.processing_jobs[job.request_id] = job
            
            self.logger.info(f"Added job {job.request_id} to queue (priority: {job.priority})")
            return True
        except Exception as e:
            self.logger.error(f"Failed to add job to queue: {e}")
            return False
    
    def get_job_status(self, request_id: str) -> Optional[ProcessingStatus]:
        """Get job status by request ID"""
        # Check processing jobs
        if request_id in self.processing_jobs:
            return self.processing_jobs[request_id].to_status()
        
        # Check completed jobs
        if request_id in self.completed_jobs:
            return self.completed_jobs[request_id].to_status()
        
        return None
    
    def get_queue_stats(self) -> QueueStats:
        """Get queue statistics"""
        uptime = (datetime.now() - self.stats_start_time).total_seconds()
        
        return QueueStats(
            queue_size=self.queue.qsize(),
            processing_count=len([j for j in self.processing_jobs.values() if j.status == "processing"]),
            completed_count=len(self.completed_jobs),
            failed_count=len([j for j in self.completed_jobs.values() if j.status == "failed"]),
            worker_count=len([w for w in self.workers if w.is_alive()]),
            uptime=uptime
        )
    
    def _get_next_job(self) -> Optional[ProcessingJob]:
        """Get next job from priority queues"""
        # Check high priority first
        for priority in [3, 2, 1]:
            try:
                priority_queue = self.priority_queues[priority]
                return priority_queue.get_nowait()
            except Empty:
                continue
        
        # Fallback to main queue
        try:
            return self.queue.get(timeout=1)
        except Empty:
            return None
    
    def _worker_loop(self):
        """Main worker loop"""
        worker_name = threading.current_thread().name
        self.logger.info(f"Starting worker: {worker_name}")
        
        # Initialize processor for this worker
        processor = LLMProcessor(
            model=self.config.ollama.model,
            log_level=self.config.processing.log_level
        )
        
        cloud_client = CloudAPIClient(self.config)
        
        while self.running:
            try:
                job = self._get_next_job()
                if job is None:
                    continue
                
                if job is None:  # Sentinel value to stop
                    break
                
                self.logger.info(f"Worker {worker_name} processing job {job.request_id}")
                self._process_job(job, processor, cloud_client)
                
            except Exception as e:
                self.logger.error(f"Worker {worker_name} error: {e}")
                traceback.print_exc()
        
        self.logger.info(f"Worker {worker_name} stopped")
    
    def _process_job(self, job: ProcessingJob, processor: LLMProcessor, cloud_client: CloudAPIClient):
        """Process a single job"""
        try:
            # Update job status
            job.status = "processing"
            job.started_at = datetime.now()
            job.progress = 0.1
            
            # Send status update to cloud
            if job.callback_url:
                asyncio.create_task(cloud_client.send_status_update(job.request_id, job.to_status()))
            
            # Process based on action type
            if job.action == "process_candidate":
                result = self._process_single_candidate(job.data, processor)
                job.result = result
            elif job.action == "process_batch":
                result = self._process_candidate_batch(job.data, processor)
                job.result = result
            elif job.action == "health_check":
                result = processor.health_check()
                job.result = result
            else:
                raise ValueError(f"Unknown action: {job.action}")
            
            # Job completed successfully
            job.status = "completed"
            job.progress = 1.0
            job.completed_at = datetime.now()
            
            # Send results to cloud
            if job.callback_url:
                asyncio.create_task(cloud_client.send_processing_results(job.request_id, job.result))
            
            self.logger.info(f"Job {job.request_id} completed successfully")
            
        except Exception as e:
            # Job failed
            job.status = "failed"
            job.error = str(e)
            job.completed_at = datetime.now()
            
            self.logger.error(f"Job {job.request_id} failed: {e}")
            
            # Send error to cloud
            if job.callback_url:
                asyncio.create_task(cloud_client.send_processing_error(job.request_id, str(e)))
        
        finally:
            # Move job to completed
            if job.request_id in self.processing_jobs:
                del self.processing_jobs[job.request_id]
            self.completed_jobs[job.request_id] = job
            
            # Cleanup old completed jobs (keep last 1000)
            if len(self.completed_jobs) > 1000:
                oldest_jobs = sorted(self.completed_jobs.keys(), 
                                   key=lambda x: self.completed_jobs[x].completed_at or datetime.min)
                for job_id in oldest_jobs[:100]:
                    del self.completed_jobs[job_id]
    
    def _process_single_candidate(self, data: CandidateData, processor: LLMProcessor) -> Dict[str, Any]:
        """Process single candidate"""
        # Convert to record format expected by processor
        record = {
            'candidate_id': data.candidate_id,
            'name': data.name,
            'resume_text': data.resume_text,
            'resume_file': data.resume_file_url,
            'recruiter_comments': data.recruiter_comments,
            'role_level': data.role_level
        }
        
        # Process candidate
        profile = processor.process_single_record(record)
        
        # Convert to dictionary for serialization
        return profile.to_dict()
    
    def _process_candidate_batch(self, data: List[CandidateData], processor: LLMProcessor) -> Dict[str, Any]:
        """Process batch of candidates"""
        records = []
        for candidate in data:
            record = {
                'candidate_id': candidate.candidate_id,
                'name': candidate.name,
                'resume_text': candidate.resume_text,
                'resume_file': candidate.resume_file_url,
                'recruiter_comments': candidate.recruiter_comments,
                'role_level': candidate.role_level
            }
            records.append(record)
        
        # Process batch
        profiles, stats = processor.process_batch(records)
        
        return {
            'profiles': [profile.to_dict() for profile in profiles],
            'stats': asdict(stats)
        }


class WebhookServer:
    """Main webhook server class"""
    
    def __init__(self, config: WebhookIntegrationConfig):
        self.config = config
        self.queue_manager = WebhookQueueManager(config)
        self.cloud_client = CloudAPIClient(config)
        self.logger = logging.getLogger(__name__)
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, config.processing.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(config.monitoring.log_file),
                logging.StreamHandler()
            ]
        )
    
    def create_app(self) -> FastAPI:
        """Create FastAPI application"""
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            self.logger.info("Starting webhook server...")
            self.queue_manager.start_workers()
            yield
            # Shutdown
            self.logger.info("Shutting down webhook server...")
            self.queue_manager.stop_workers()
        
        app = FastAPI(
            title="Headhunter Webhook Server",
            description="Local webhook server for processing candidates with Ollama",
            version="1.0.0",
            lifespan=lifespan
        )
        
        # CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.server.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Security
        security = HTTPBearer() if self.config.security.enable_auth else None
        
        def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
            if self.config.security.enable_auth and self.config.security.api_key:
                if not credentials or credentials.credentials != self.config.security.api_key:
                    raise HTTPException(status_code=401, detail="Invalid authentication token")
            return credentials
        
        # Routes
        @app.get("/health")
        async def health_check():
            """Health check endpoint"""
            try:
                # Check Ollama health
                processor = LLMProcessor(model=self.config.ollama.model)
                ollama_health = processor.health_check()
                
                # Get queue stats
                queue_stats = self.queue_manager.get_queue_stats()
                
                # System info
                system_info = {
                    "uptime": queue_stats.uptime,
                    "environment": self.config.environment.value,
                    "version": "1.0.0"
                }
                
                return HealthStatus(
                    status="healthy" if ollama_health["overall_status"] == "healthy" else "unhealthy",
                    timestamp=datetime.now(),
                    ollama_status=ollama_health,
                    queue_stats=queue_stats,
                    system_info=system_info
                )
            except Exception as e:
                return JSONResponse(
                    status_code=503,
                    content={"status": "unhealthy", "error": str(e)}
                )
        
        @app.get("/status/{request_id}")
        async def get_processing_status(request_id: str, auth = Depends(verify_token)):
            """Get processing status for a request"""
            status = self.queue_manager.get_job_status(request_id)
            if status is None:
                raise HTTPException(status_code=404, detail="Request not found")
            return status
        
        @app.get("/queue/status")
        async def get_queue_status(auth = Depends(verify_token)):
            """Get queue statistics"""
            return self.queue_manager.get_queue_stats()
        
        @app.post("/webhook/process-candidate")
        async def process_candidate_webhook(
            request: WebhookRequest,
            background_tasks: BackgroundTasks,
            auth = Depends(verify_token)
        ):
            """Process single candidate via webhook"""
            try:
                # Validate data
                if not isinstance(request.data, dict):
                    raise HTTPException(status_code=400, detail="Invalid candidate data format")
                
                candidate_data = CandidateData(**request.data)
                
                # Create processing job
                job = ProcessingJob(
                    request_id=request.request_id,
                    action="process_candidate",
                    data=candidate_data,
                    callback_url=request.callback_url,
                    timeout=request.timeout,
                    priority=candidate_data.priority,
                    created_at=datetime.now()
                )
                
                # Add to queue
                if not self.queue_manager.add_job(job):
                    raise HTTPException(status_code=503, detail="Queue is full")
                
                return {
                    "status": "queued",
                    "request_id": request.request_id,
                    "message": "Candidate processing request queued successfully"
                }
                
            except Exception as e:
                self.logger.error(f"Error processing candidate webhook: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/webhook/process-batch")
        async def process_batch_webhook(
            request: WebhookRequest,
            background_tasks: BackgroundTasks,
            auth = Depends(verify_token)
        ):
            """Process batch of candidates via webhook"""
            try:
                # Validate data
                if not isinstance(request.data, list):
                    raise HTTPException(status_code=400, detail="Invalid batch data format")
                
                candidates_data = [CandidateData(**item) for item in request.data]
                
                # Create processing job
                job = ProcessingJob(
                    request_id=request.request_id,
                    action="process_batch",
                    data=candidates_data,
                    callback_url=request.callback_url,
                    timeout=request.timeout,
                    priority=max(c.priority for c in candidates_data),
                    created_at=datetime.now()
                )
                
                # Add to queue
                if not self.queue_manager.add_job(job):
                    raise HTTPException(status_code=503, detail="Queue is full")
                
                return {
                    "status": "queued",
                    "request_id": request.request_id,
                    "message": f"Batch processing request queued successfully ({len(candidates_data)} candidates)"
                }
                
            except Exception as e:
                self.logger.error(f"Error processing batch webhook: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/metrics")
        async def get_metrics(auth = Depends(verify_token)):
            """Get system metrics"""
            queue_stats = self.queue_manager.get_queue_stats()
            
            # Calculate additional metrics
            processing_jobs = list(self.queue_manager.processing_jobs.values())
            completed_jobs = list(self.queue_manager.completed_jobs.values())
            
            total_processing_time = sum(
                (job.completed_at - job.started_at).total_seconds() 
                for job in completed_jobs 
                if job.started_at and job.completed_at
            )
            
            avg_processing_time = (
                total_processing_time / len(completed_jobs) 
                if completed_jobs else 0
            )
            
            return {
                "queue_stats": queue_stats,
                "metrics": {
                    "total_jobs_processed": len(completed_jobs),
                    "success_rate": len([j for j in completed_jobs if j.status == "completed"]) / len(completed_jobs) if completed_jobs else 0,
                    "average_processing_time": avg_processing_time,
                    "current_processing_jobs": len(processing_jobs)
                }
            }
        
        return app
    
    def run(self):
        """Run the webhook server"""
        app = self.create_app()
        
        self.logger.info(f"Starting webhook server on {self.config.server.host}:{self.config.server.port}")
        
        uvicorn.run(
            app,
            host=self.config.server.host,
            port=self.config.server.port,
            log_level=self.config.processing.log_level.lower(),
            access_log=True
        )


def main():
    """Main function for CLI usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Webhook Server for Headhunter AI')
    parser.add_argument('--env', choices=['development', 'production', 'testing'],
                       default='development', help='Environment to run in')
    parser.add_argument('--host', help='Server host')
    parser.add_argument('--port', type=int, help='Server port')
    parser.add_argument('--config', help='Configuration file path')
    
    args = parser.parse_args()
    
    # Load configuration
    if args.config:
        config = WebhookIntegrationConfig.load_from_file(args.config)
    else:
        from webhook_config import Environment
        env = Environment(args.env)
        config = get_config(env)
    
    # Override with command line arguments
    if args.host:
        config.server.host = args.host
    if args.port:
        config.server.port = args.port
    
    # Create and run server
    server = WebhookServer(config)
    server.run()


if __name__ == "__main__":
    main()