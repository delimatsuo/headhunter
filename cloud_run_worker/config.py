"""
Configuration management for Cloud Run worker
"""

import os
from typing import Optional


class Config:
    """Configuration class that loads from environment variables"""
    
    def __init__(self, testing: bool = False):
        # Required configuration (allow defaults for testing)
        if testing:
            self.together_ai_api_key = os.getenv("TOGETHER_API_KEY", "test-api-key")
            self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "test-project")
        else:
            # Try to get API key from environment first, fallback to secret manager
            self.together_ai_api_key = self._get_together_ai_key()
            self.project_id = self._get_required_env("GOOGLE_CLOUD_PROJECT", "headhunter-ai-0088")
        
        # Optional configuration with defaults
        self.pubsub_topic = os.getenv("PUBSUB_TOPIC", "candidate-process-requests")
        self.pubsub_subscription = os.getenv("PUBSUB_SUBSCRIPTION", "candidate-worker-sub")
        self.dead_letter_topic = os.getenv("DEAD_LETTER_TOPIC", "candidate-process-dlq")
        
        # Together AI configuration (align with Stage 1 model env)
        self.together_ai_model = os.getenv("TOGETHER_MODEL_STAGE1", os.getenv("TOGETHER_AI_MODEL", "Qwen/Qwen2.5-32B-Instruct"))
        self.together_ai_base_url = os.getenv("TOGETHER_AI_BASE_URL", "https://api.together.xyz/v1")
        self.together_ai_timeout = int(os.getenv("TOGETHER_AI_TIMEOUT", "60"))
        self.together_ai_max_retries = int(os.getenv("TOGETHER_AI_MAX_RETRIES", "3"))
        
        # Firestore configuration
        self.firestore_collection = os.getenv("FIRESTORE_COLLECTION", "candidates")
        self.firestore_timeout = int(os.getenv("FIRESTORE_TIMEOUT", "30"))
        
        # Processing configuration
        self.max_concurrent_processes = int(os.getenv("MAX_CONCURRENT_PROCESSES", "10"))
        self.processing_timeout = int(os.getenv("PROCESSING_TIMEOUT", "300"))  # 5 minutes
        self.retry_max_attempts = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
        self.retry_base_delay = float(os.getenv("RETRY_BASE_DELAY", "1.0"))
        
        # Monitoring configuration
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.metrics_enabled = os.getenv("METRICS_ENABLED", "true").lower() == "true"
        
        # Health check configuration
        self.health_check_timeout = int(os.getenv("HEALTH_CHECK_TIMEOUT", "10"))
        
        # Performance thresholds for monitoring
        self.error_rate_threshold = float(os.getenv("ERROR_RATE_THRESHOLD", "0.1"))  # 10% error rate
        self.response_time_threshold = float(os.getenv("RESPONSE_TIME_THRESHOLD", "60.0"))  # 60 seconds
        
    def _get_required_env(self, key: str, default: Optional[str] = None) -> str:
        """Get required environment variable or raise error"""
        value = os.getenv(key, default)
        if not value:
            raise ValueError(f"{key} is required but not set in environment variables")
        return value
    
    def _get_together_ai_key(self) -> str:
        """Get Together AI API key from environment or Secret Manager"""
        # First try environment variable
        api_key = os.getenv("TOGETHER_API_KEY")
        if api_key:
            return api_key
        
        # Try to get from Secret Manager
        try:
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "headhunter-ai-0088")
            secret_name = f"projects/{project_id}/secrets/together-ai-credentials/versions/latest"
            response = client.access_secret_version(request={"name": secret_name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            raise ValueError(f"Could not retrieve Together AI API key from environment or Secret Manager: {e}")
    
    def validate(self):
        """Validate configuration"""
        errors = []
        
        # Validate numeric values
        if self.together_ai_timeout <= 0:
            errors.append("TOGETHER_AI_TIMEOUT must be positive")
        
        if self.max_concurrent_processes <= 0:
            errors.append("MAX_CONCURRENT_PROCESSES must be positive")
        
        if self.processing_timeout <= 0:
            errors.append("PROCESSING_TIMEOUT must be positive")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary (excluding sensitive data)"""
        return {
            "project_id": self.project_id,
            "pubsub_topic": self.pubsub_topic,
            "pubsub_subscription": self.pubsub_subscription,
            "together_ai_model": self.together_ai_model,
            "together_ai_base_url": self.together_ai_base_url,
            "together_ai_timeout": self.together_ai_timeout,
            "firestore_collection": self.firestore_collection,
            "max_concurrent_processes": self.max_concurrent_processes,
            "processing_timeout": self.processing_timeout,
            "log_level": self.log_level,
            "metrics_enabled": self.metrics_enabled
        }
