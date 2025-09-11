"""
Metrics collection and monitoring for Cloud Run worker
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque

from .config import Config
from .models import ProcessingMetrics, HealthCheckResult

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and manages processing metrics"""
    
    def __init__(self, config: Config):
        self.config = config
        self.start_time = datetime.now()
        
        # Processing metrics
        self.messages_processed = 0
        self.success_count = 0
        self.error_count = 0
        self.processing_times: deque = deque(maxlen=1000)  # Keep last 1000 processing times
        
        # Rate limiting metrics
        self.requests_per_minute: deque = deque(maxlen=60)  # Track requests per minute
        self.last_minute_bucket = datetime.now().minute
        
        # Error tracking
        self.error_types: Dict[str, int] = defaultdict(int)
        self.recent_errors: deque = deque(maxlen=100)  # Keep last 100 errors
        
        # Health check results
        self.health_checks: Dict[str, HealthCheckResult] = {}
        
        # Active processing tracking
        self.active_processors: Dict[str, Dict[str, Any]] = {}
        
        # Resource usage tracking
        self.peak_memory_usage = 0
        self.peak_cpu_usage = 0.0
        
        # Performance thresholds
        self.error_rate_threshold = config.error_rate_threshold
        self.response_time_threshold = config.response_time_threshold
        
    def record_request_start(self, candidate_id: str) -> str:
        """Record the start of request processing"""
        request_id = f"{candidate_id}_{int(time.time())}"
        
        self.active_processors[request_id] = {
            "candidate_id": candidate_id,
            "start_time": datetime.now(),
            "status": "processing"
        }
        
        # Update rate limiting metrics
        current_minute = datetime.now().minute
        if current_minute != self.last_minute_bucket:
            self.requests_per_minute.append(0)
            self.last_minute_bucket = current_minute
        
        if self.requests_per_minute:
            self.requests_per_minute[-1] += 1
        else:
            self.requests_per_minute.append(1)
        
        logger.debug(f"Started processing request: {request_id}")
        return request_id
    
    def record_request_success(self, request_id: str, processing_time: float):
        """Record successful request completion"""
        if request_id in self.active_processors:
            self.active_processors[request_id]["status"] = "completed"
            self.active_processors[request_id]["end_time"] = datetime.now()
            del self.active_processors[request_id]
        
        self.messages_processed += 1
        self.success_count += 1
        self.processing_times.append(processing_time)
        
        logger.debug(f"Completed request: {request_id}, time: {processing_time:.2f}s")
    
    def record_request_error(self, request_id: str, error: str, error_type: str = "unknown"):
        """Record request processing error"""
        if request_id in self.active_processors:
            self.active_processors[request_id]["status"] = "failed"
            self.active_processors[request_id]["error"] = error
            self.active_processors[request_id]["end_time"] = datetime.now()
            del self.active_processors[request_id]
        
        self.messages_processed += 1
        self.error_count += 1
        self.error_types[error_type] += 1
        
        self.recent_errors.append({
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "error": error,
            "error_type": error_type
        })
        
        logger.error(f"Request failed: {request_id}, error: {error}")
    
    def record_health_check(self, service: str, status: str, response_time_ms: Optional[float] = None, error: Optional[str] = None):
        """Record health check result"""
        self.health_checks[service] = HealthCheckResult(
            service=service,
            status=status,
            response_time_ms=response_time_ms,
            error=error,
            timestamp=datetime.now()
        )
    
    def update_resource_usage(self, memory_mb: float, cpu_percent: float):
        """Update resource usage metrics"""
        self.peak_memory_usage = max(self.peak_memory_usage, memory_mb)
        self.peak_cpu_usage = max(self.peak_cpu_usage, cpu_percent)
    
    def get_current_metrics(self) -> ProcessingMetrics:
        """Get current processing metrics"""
        return ProcessingMetrics(
            messages_processed=self.messages_processed,
            processing_times=list(self.processing_times),
            error_count=self.error_count,
            success_count=self.success_count,
            active_processors={req_id: proc["status"] for req_id, proc in self.active_processors.items()},
            start_time=self.start_time
        )
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """Get detailed statistics"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        # Calculate processing statistics
        avg_processing_time = sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0
        p95_processing_time = sorted(self.processing_times)[int(0.95 * len(self.processing_times))] if self.processing_times else 0
        p99_processing_time = sorted(self.processing_times)[int(0.99 * len(self.processing_times))] if self.processing_times else 0
        
        # Calculate error rate
        error_rate = (self.error_count / self.messages_processed) if self.messages_processed > 0 else 0
        
        # Calculate throughput
        throughput = self.messages_processed / (uptime / 60) if uptime > 0 else 0  # messages per minute
        
        # Recent request rate
        recent_requests = sum(self.requests_per_minute) if self.requests_per_minute else 0
        
        return {
            "uptime_seconds": uptime,
            "messages_processed": self.messages_processed,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "error_rate": error_rate,
            "active_requests": len(self.active_processors),
            
            # Performance metrics
            "avg_processing_time_seconds": avg_processing_time,
            "p95_processing_time_seconds": p95_processing_time,
            "p99_processing_time_seconds": p99_processing_time,
            "throughput_per_minute": throughput,
            "recent_requests_per_minute": recent_requests,
            
            # Error breakdown
            "error_types": dict(self.error_types),
            "recent_errors": list(self.recent_errors)[-10:],  # Last 10 errors
            
            # Health status
            "health_checks": {
                service: {
                    "status": check.status,
                    "response_time_ms": check.response_time_ms,
                    "last_check": check.timestamp.isoformat(),
                    "error": check.error
                }
                for service, check in self.health_checks.items()
            },
            
            # Resource usage
            "peak_memory_mb": self.peak_memory_usage,
            "peak_cpu_percent": self.peak_cpu_usage,
            
            # Status indicators
            "is_healthy": self.is_healthy(),
            "alerts": self.get_alerts()
        }
    
    def is_healthy(self) -> bool:
        """Check if the service is in a healthy state"""
        # Check error rate
        if self.messages_processed > 0:
            error_rate = self.error_count / self.messages_processed
            if error_rate > self.error_rate_threshold:
                return False
        
        # Check response times
        if self.processing_times:
            avg_time = sum(self.processing_times) / len(self.processing_times)
            if avg_time > self.response_time_threshold:
                return False
        
        # Check health checks
        for service, check in self.health_checks.items():
            if check.status == "unhealthy":
                return False
            
            # Check if health check is stale (older than 5 minutes)
            if (datetime.now() - check.timestamp).total_seconds() > 300:
                return False
        
        return True
    
    def get_alerts(self) -> List[Dict[str, Any]]:
        """Get current alerts based on metrics"""
        alerts = []
        
        # High error rate alert
        if self.messages_processed > 10:  # Only alert after processing some messages
            error_rate = self.error_count / self.messages_processed
            if error_rate > self.error_rate_threshold:
                alerts.append({
                    "type": "high_error_rate",
                    "severity": "critical",
                    "message": f"Error rate {error_rate:.2%} exceeds threshold {self.error_rate_threshold:.2%}",
                    "value": error_rate,
                    "threshold": self.error_rate_threshold
                })
        
        # High response time alert
        if self.processing_times:
            avg_time = sum(self.processing_times) / len(self.processing_times)
            if avg_time > self.response_time_threshold:
                alerts.append({
                    "type": "high_response_time",
                    "severity": "warning",
                    "message": f"Average response time {avg_time:.2f}s exceeds threshold {self.response_time_threshold}s",
                    "value": avg_time,
                    "threshold": self.response_time_threshold
                })
        
        # Too many active requests
        if len(self.active_processors) > 50:
            alerts.append({
                "type": "high_active_requests",
                "severity": "warning",
                "message": f"High number of active requests: {len(self.active_processors)}",
                "value": len(self.active_processors)
            })
        
        # Service health alerts
        for service, check in self.health_checks.items():
            if check.status == "unhealthy":
                alerts.append({
                    "type": "service_unhealthy",
                    "severity": "critical",
                    "message": f"Service {service} is unhealthy: {check.error}",
                    "service": service,
                    "error": check.error
                })
        
        return alerts
    
    def reset_metrics(self):
        """Reset all metrics (useful for testing)"""
        self.start_time = datetime.now()
        self.messages_processed = 0
        self.success_count = 0
        self.error_count = 0
        self.processing_times.clear()
        self.requests_per_minute.clear()
        self.error_types.clear()
        self.recent_errors.clear()
        self.health_checks.clear()
        self.active_processors.clear()
        self.peak_memory_usage = 0
        self.peak_cpu_usage = 0.0
        
        logger.info("Metrics reset")
    
    # Additional methods expected by main.py
    def get_messages_processed(self) -> int:
        """Get total messages processed"""
        return self.messages_processed
    
    def get_average_processing_time(self) -> float:
        """Get average processing time"""
        if not self.processing_times:
            return 0.0
        return sum(self.processing_times) / len(self.processing_times)
    
    def get_error_count(self) -> int:
        """Get total error count"""
        return self.error_count
    
    def get_success_rate(self) -> float:
        """Get success rate as percentage"""
        if self.messages_processed == 0:
            return 0.0
        return (self.success_count / self.messages_processed) * 100
    
    def get_active_processors(self) -> Dict[str, bool]:
        """Get active processors status"""
        return {req_id: proc["status"] == "processing" for req_id, proc in self.active_processors.items()}
    
    def increment_messages_processed(self):
        """Increment messages processed counter"""
        self.messages_processed += 1
    
    def increment_error_count(self):
        """Increment error counter"""
        self.error_count += 1
    
    def set_active_processor(self, candidate_id: str, active: bool):
        """Set active processor status"""
        if active:
            self.active_processors[candidate_id] = {
                "candidate_id": candidate_id,
                "start_time": datetime.now(),
                "status": "processing"
            }
        else:
            if candidate_id in self.active_processors:
                del self.active_processors[candidate_id]
    
    def record_processing_time(self, processing_time: float):
        """Record processing time"""
        self.processing_times.append(processing_time)
    
    async def start_monitoring(self):
        """Start background monitoring tasks"""
        logger.info("Starting metrics monitoring")
        
        # Start resource monitoring
        asyncio.create_task(self._monitor_resources())
        
        # Start cleanup task for stale active processors
        asyncio.create_task(self._cleanup_stale_processors())
    
    async def _monitor_resources(self):
        """Monitor system resource usage"""
        try:
            import psutil
            
            while True:
                try:
                    # Get current process
                    process = psutil.Process()
                    
                    # Memory usage
                    memory_info = process.memory_info()
                    memory_mb = memory_info.rss / (1024 * 1024)
                    
                    # CPU usage
                    cpu_percent = process.cpu_percent()
                    
                    # Update metrics
                    self.update_resource_usage(memory_mb, cpu_percent)
                    
                    # Log high resource usage
                    if memory_mb > 1000:  # 1GB threshold
                        logger.warning(f"High memory usage: {memory_mb:.1f}MB")
                    
                    if cpu_percent > 80:
                        logger.warning(f"High CPU usage: {cpu_percent:.1f}%")
                    
                except Exception as e:
                    logger.error(f"Resource monitoring error: {e}")
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
        except ImportError:
            logger.warning("psutil not available, resource monitoring disabled")
    
    async def _cleanup_stale_processors(self):
        """Clean up processors that have been active too long"""
        while True:
            try:
                current_time = datetime.now()
                stale_processors = []
                
                for request_id, processor_info in self.active_processors.items():
                    start_time = processor_info["start_time"]
                    if (current_time - start_time).total_seconds() > 300:  # 5 minutes timeout
                        stale_processors.append(request_id)
                
                for request_id in stale_processors:
                    logger.warning(f"Cleaning up stale processor: {request_id}")
                    self.record_request_error(request_id, "Processing timeout", "timeout")
                
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
            
            await asyncio.sleep(60)  # Check every minute


# Global metrics instance
_metrics_collector: Optional[MetricsCollector] = None


def initialize_metrics(config: Config) -> MetricsCollector:
    """Initialize global metrics collector"""
    global _metrics_collector
    _metrics_collector = MetricsCollector(config)
    return _metrics_collector


def get_metrics() -> Optional[MetricsCollector]:
    """Get global metrics collector instance"""
    return _metrics_collector


def record_request_start(candidate_id: str) -> str:
    """Convenience function to record request start"""
    if _metrics_collector:
        return _metrics_collector.record_request_start(candidate_id)
    return f"{candidate_id}_{int(time.time())}"


def record_request_success(request_id: str, processing_time: float):
    """Convenience function to record request success"""
    if _metrics_collector:
        _metrics_collector.record_request_success(request_id, processing_time)


def record_request_error(request_id: str, error: str, error_type: str = "unknown"):
    """Convenience function to record request error"""
    if _metrics_collector:
        _metrics_collector.record_request_error(request_id, error, error_type)


def record_health_check(service: str, status: str, response_time_ms: Optional[float] = None, error: Optional[str] = None):
    """Convenience function to record health check"""
    if _metrics_collector:
        _metrics_collector.record_health_check(service, status, response_time_ms, error)