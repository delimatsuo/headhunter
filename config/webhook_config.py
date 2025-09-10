#!/usr/bin/env python3
"""
Webhook Integration Configuration
Configuration settings for connecting local Ollama processing with Firebase Cloud Functions
"""

import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import json
from enum import Enum


class Environment(Enum):
    """Environment types for webhook configuration"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class ProcessingMode(Enum):
    """Processing modes for webhook requests"""
    SINGLE = "single"        # Process one candidate at a time
    BATCH = "batch"          # Process multiple candidates in batches
    QUEUE = "queue"          # Queue-based processing with workers
    PRIORITY = "priority"    # Priority-based processing


@dataclass
class OllamaConfig:
    """Configuration for Ollama LLM"""
    model: str = "llama3.1:8b"
    base_url: str = "http://localhost:11434"
    timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 2.0
    health_check_interval: int = 300  # 5 minutes


@dataclass
class FirebaseConfig:
    """Configuration for Firebase/Cloud Functions integration"""
    project_id: str = "headhunter-ai-0088"
    functions_base_url: str = "https://us-central1-headhunter-ai-0088.cloudfunctions.net"
    service_account_path: str = ".gcp/headhunter-service-key.json"
    firestore_database: str = "(default)"
    storage_bucket: str = "headhunter-ai-0088.appspot.com"
    timeout: int = 300
    max_retries: int = 3


@dataclass
class WebhookServerConfig:
    """Configuration for the local webhook server"""
    host: str = "localhost"
    port: int = 8080
    debug: bool = False
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    max_payload_size: int = 10 * 1024 * 1024  # 10MB
    request_timeout: int = 300
    max_concurrent_requests: int = 10
    auth_token: Optional[str] = None


@dataclass
class QueueConfig:
    """Configuration for request queue management"""
    max_queue_size: int = 1000
    worker_count: int = 3
    batch_size: int = 5
    batch_timeout: int = 30
    priority_levels: int = 3
    persistence_path: str = "queue_state.json"
    cleanup_interval: int = 3600  # 1 hour


@dataclass
class ProcessingConfig:
    """Configuration for candidate processing"""
    default_mode: ProcessingMode = ProcessingMode.QUEUE
    max_processing_time: int = 600  # 10 minutes per candidate
    enable_validation: bool = True
    save_intermediate_results: bool = True
    results_directory: str = "webhook_results"
    log_level: str = "INFO"
    enable_metrics: bool = True


@dataclass
class SecurityConfig:
    """Security configuration for webhook integration"""
    enable_auth: bool = True
    api_key: Optional[str] = None
    allowed_ips: List[str] = field(default_factory=list)
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # 1 hour
    encrypt_payloads: bool = False
    webhook_secret: Optional[str] = None


@dataclass
class MonitoringConfig:
    """Monitoring and logging configuration"""
    log_file: str = "webhook_integration.log"
    max_log_size: int = 100 * 1024 * 1024  # 100MB
    log_rotation_count: int = 5
    metrics_file: str = "webhook_metrics.json"
    health_check_endpoint: bool = True
    status_update_interval: int = 60  # 1 minute


@dataclass
class WebhookIntegrationConfig:
    """Complete webhook integration configuration"""
    environment: Environment = Environment.DEVELOPMENT
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    firebase: FirebaseConfig = field(default_factory=FirebaseConfig)
    server: WebhookServerConfig = field(default_factory=WebhookServerConfig)
    queue: QueueConfig = field(default_factory=QueueConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    def __post_init__(self):
        """Post-initialization configuration adjustments"""
        # Adjust configuration based on environment
        if self.environment == Environment.PRODUCTION:
            self.server.debug = False
            self.server.cors_origins = [
                "https://headhunter-ai-0088.web.app",
                "https://headhunter-ai-0088.firebaseapp.com"
            ]
            self.security.enable_auth = True
            self.monitoring.log_level = "WARNING"
        elif self.environment == Environment.DEVELOPMENT:
            self.server.debug = True
            self.server.cors_origins = ["*"]
            self.security.enable_auth = False
            self.monitoring.log_level = "DEBUG"
        
        # Load environment variables
        self._load_environment_variables()
        
        # Create necessary directories
        self._create_directories()
    
    def _load_environment_variables(self):
        """Load configuration from environment variables"""
        # Server configuration
        self.server.host = os.getenv("WEBHOOK_HOST", self.server.host)
        self.server.port = int(os.getenv("WEBHOOK_PORT", str(self.server.port)))
        self.server.auth_token = os.getenv("WEBHOOK_AUTH_TOKEN")
        
        # Firebase configuration
        self.firebase.project_id = os.getenv("FIREBASE_PROJECT_ID", self.firebase.project_id)
        service_account_env = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if service_account_env:
            self.firebase.service_account_path = service_account_env
        
        # Ollama configuration
        self.ollama.model = os.getenv("OLLAMA_MODEL", self.ollama.model)
        self.ollama.base_url = os.getenv("OLLAMA_BASE_URL", self.ollama.base_url)
        
        # Security configuration
        self.security.api_key = os.getenv("WEBHOOK_API_KEY")
        self.security.webhook_secret = os.getenv("WEBHOOK_SECRET")
        
        # Environment detection
        env_name = os.getenv("ENVIRONMENT", "development").lower()
        if env_name in [e.value for e in Environment]:
            self.environment = Environment(env_name)
    
    def _create_directories(self):
        """Create necessary directories"""
        directories = [
            self.processing.results_directory,
            Path(self.monitoring.log_file).parent,
            Path(self.queue.persistence_path).parent,
            Path(self.firebase.service_account_path).parent,
        ]
        
        for directory in directories:
            if directory and directory != Path("."):
                Path(directory).mkdir(parents=True, exist_ok=True)
    
    def get_cloud_endpoints(self) -> Dict[str, str]:
        """Get Cloud Functions endpoints"""
        base_url = self.firebase.functions_base_url
        return {
            "receive_analysis": f"{base_url}/receiveAnalysis",
            "update_status": f"{base_url}/updateProcessingStatus",
            "get_candidate": f"{base_url}/getCandidate",
            "health_check": f"{base_url}/healthCheck",
            "webhook_register": f"{base_url}/registerWebhook"
        }
    
    def get_local_endpoints(self) -> Dict[str, str]:
        """Get local webhook endpoints"""
        base_url = f"http://{self.server.host}:{self.server.port}"
        return {
            "process_candidate": f"{base_url}/webhook/process-candidate",
            "process_batch": f"{base_url}/webhook/process-batch",
            "health_check": f"{base_url}/health",
            "status": f"{base_url}/status",
            "metrics": f"{base_url}/metrics",
            "queue_status": f"{base_url}/queue/status"
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        result = {}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if hasattr(value, '__dict__'):
                result[field_name] = value.__dict__
            elif isinstance(value, Enum):
                result[field_name] = value.value
            else:
                result[field_name] = value
        return result
    
    def save_to_file(self, file_path: str):
        """Save configuration to JSON file"""
        config_dict = self.to_dict()
        with open(file_path, 'w') as f:
            json.dump(config_dict, f, indent=2, default=str)
    
    @classmethod
    def load_from_file(cls, file_path: str) -> 'WebhookIntegrationConfig':
        """Load configuration from JSON file"""
        with open(file_path, 'r') as f:
            config_dict = json.load(f)
        
        # Convert nested dictionaries back to dataclass instances
        config = cls()
        for field_name, field_def in cls.__dataclass_fields__.items():
            if field_name in config_dict:
                value = config_dict[field_name]
                if hasattr(field_def.type, '__dataclass_fields__'):
                    # Convert dict to dataclass
                    setattr(config, field_name, field_def.type(**value))
                elif field_name == 'environment':
                    setattr(config, field_name, Environment(value))
                elif field_name.endswith('_mode'):
                    setattr(config, field_name, ProcessingMode(value))
                else:
                    setattr(config, field_name, value)
        
        return config


# Global configuration instance
_config: Optional[WebhookIntegrationConfig] = None


def get_config(environment: Optional[Environment] = None) -> WebhookIntegrationConfig:
    """Get global configuration instance"""
    global _config
    if _config is None or (environment and _config.environment != environment):
        _config = WebhookIntegrationConfig(
            environment=environment or Environment.DEVELOPMENT
        )
    return _config


def load_config_from_file(file_path: str) -> WebhookIntegrationConfig:
    """Load and set global configuration from file"""
    global _config
    _config = WebhookIntegrationConfig.load_from_file(file_path)
    return _config


# Configuration presets
def get_development_config() -> WebhookIntegrationConfig:
    """Get development configuration preset"""
    config = WebhookIntegrationConfig(environment=Environment.DEVELOPMENT)
    config.server.debug = True
    config.server.port = 8080
    config.ollama.timeout = 60
    config.queue.worker_count = 2
    config.processing.log_level = "DEBUG"
    return config


def get_production_config() -> WebhookIntegrationConfig:
    """Get production configuration preset"""
    config = WebhookIntegrationConfig(environment=Environment.PRODUCTION)
    config.server.debug = False
    config.server.port = 80
    config.ollama.timeout = 300
    config.queue.worker_count = 5
    config.processing.log_level = "INFO"
    config.security.enable_auth = True
    return config


def get_testing_config() -> WebhookIntegrationConfig:
    """Get testing configuration preset"""
    config = WebhookIntegrationConfig(environment=Environment.TESTING)
    config.server.debug = True
    config.server.port = 8081
    config.ollama.timeout = 30
    config.queue.worker_count = 1
    config.processing.log_level = "DEBUG"
    config.processing.enable_validation = False
    return config


if __name__ == "__main__":
    # Example usage and configuration testing
    print("Webhook Integration Configuration")
    print("=" * 50)
    
    # Test different environment configurations
    environments = [Environment.DEVELOPMENT, Environment.PRODUCTION, Environment.TESTING]
    
    for env in environments:
        print(f"\n{env.value.upper()} Configuration:")
        config = get_config(env)
        
        print(f"  Server: {config.server.host}:{config.server.port}")
        print(f"  Ollama: {config.ollama.model} @ {config.ollama.base_url}")
        print(f"  Firebase: {config.firebase.project_id}")
        print(f"  Queue Workers: {config.queue.worker_count}")
        print(f"  Security Auth: {config.security.enable_auth}")
        print(f"  Log Level: {config.processing.log_level}")
    
    # Test configuration serialization
    config = get_development_config()
    config.save_to_file("webhook_config_example.json")
    print(f"\n✓ Configuration saved to webhook_config_example.json")
    
    # Test loading from file
    loaded_config = WebhookIntegrationConfig.load_from_file("webhook_config_example.json")
    print(f"✓ Configuration loaded from file")
    
    # Display endpoints
    print(f"\nLocal Endpoints:")
    for name, url in loaded_config.get_local_endpoints().items():
        print(f"  {name}: {url}")
    
    print(f"\nCloud Endpoints:")
    for name, url in loaded_config.get_cloud_endpoints().items():
        print(f"  {name}: {url}")