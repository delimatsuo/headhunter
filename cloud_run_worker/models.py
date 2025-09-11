"""
Data models for Cloud Run worker
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class ProcessingStatus(Enum):
    """Processing status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


class PubSubMessage(BaseModel):
    """Parsed Pub/Sub message"""
    candidate_id: str
    action: str = "enrich_profile"
    org_id: Optional[str] = None
    priority: str = "normal"
    message_id: str
    publish_time: str
    attributes: Dict[str, str] = {}
    timestamp: datetime = Field(default_factory=datetime.now)


class CandidateProcessingRequest(BaseModel):
    """Request for candidate processing"""
    candidate_id: str
    action: str = "enrich_profile"
    org_id: Optional[str] = None
    priority: str = "normal"
    retry_count: int = 0
    metadata: Dict[str, Any] = {}


class ProcessingResult(BaseModel):
    """Result of candidate processing"""
    candidate_id: Optional[str] = None
    status: str
    processing_time_seconds: Optional[float] = None
    error: Optional[str] = None
    timestamp: str
    retry_count: int = 0
    metadata: Dict[str, Any] = {}


class CandidateData(BaseModel):
    """Candidate data structure"""
    candidate_id: str
    name: str
    email: Optional[str] = None
    resume_text: Optional[str] = None
    recruiter_comments: Optional[str] = None
    org_id: str
    uploaded_at: str
    status: str = "pending_enrichment"
    metadata: Dict[str, Any] = {}


class EnrichedCandidateData(BaseModel):
    """Enriched candidate data from Together AI"""
    resume_analysis: Dict[str, Any] = {}
    recruiter_insights: Dict[str, Any] = {}
    overall_score: float = 0.0
    processing_metadata: Dict[str, Any] = {}


class TogetherAIRequest(BaseModel):
    """Request to Together AI API"""
    messages: List[Dict[str, str]]
    model: str = "meta-llama/Llama-3.1-8B-Instruct-Turbo"
    max_tokens: int = 2048
    temperature: float = 0.1
    top_p: float = 0.9
    stream: bool = False


class TogetherAIResponse(BaseModel):
    """Response from Together AI API"""
    choices: List[Dict[str, Any]]
    usage: Dict[str, int] = {}
    model: str
    created: int


class ProcessingMetrics(BaseModel):
    """Processing metrics data"""
    messages_processed: int = 0
    processing_times: List[float] = []
    error_count: int = 0
    success_count: int = 0
    active_processors: Dict[str, bool] = {}
    start_time: datetime = Field(default_factory=datetime.now)


class HealthCheckResult(BaseModel):
    """Health check result"""
    service: str
    status: str  # "healthy", "unhealthy", "degraded"
    response_time_ms: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class BatchProcessingRequest(BaseModel):
    """Batch processing request"""
    candidate_ids: List[str]
    priority: str = "normal"
    org_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


class BatchProcessingResult(BaseModel):
    """Batch processing result"""
    total_candidates: int
    successful: int
    failed: int
    results: List[ProcessingResult]
    processing_time_seconds: float
    timestamp: str


class DeadLetterMessage(BaseModel):
    """Dead letter queue message"""
    original_message: Dict[str, Any]
    error: str
    retry_count: int
    failed_at: datetime = Field(default_factory=datetime.now)
    candidate_id: Optional[str] = None
    org_id: Optional[str] = None