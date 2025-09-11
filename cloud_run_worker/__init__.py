"""
Cloud Run worker package for candidate enrichment processing
"""

# Don't import app by default to avoid config initialization during imports
# from .main import app
from .config import Config
from .models import ProcessingStatus, PubSubMessage, ProcessingResult
from .candidate_processor import CandidateProcessor
from .metrics import MetricsCollector, initialize_metrics, get_metrics

__version__ = "1.0.0"
__all__ = [
    "Config", 
    "ProcessingStatus",
    "PubSubMessage",
    "ProcessingResult",
    "CandidateProcessor",
    "MetricsCollector",
    "initialize_metrics",
    "get_metrics"
]