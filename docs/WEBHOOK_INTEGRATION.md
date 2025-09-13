# Webhook Integration System (Legacy / Dev-Only)

> Note: This document describes a legacy/dev-only local webhook + Ollama flow. The PRD and current architecture use Together AI (cloud) for production Stage‑1 enrichment. Treat this as optional developer tooling, not the production path.

A complete webhook integration system that connects Firebase Cloud Functions with local Ollama processing pipeline for the Headhunter AI recruitment system.

## Overview

The webhook integration enables seamless communication between:
- **Cloud Functions** (Firebase) - Web interface and data management
- **Local Processing** (Ollama + Llama 3.1 8b) - AI analysis and insights
- **Bidirectional Communication** - Real-time status updates and results

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web App       │    │ Cloud Functions │    │ Local Webhook   │
│   (React/UI)    │───▶│   (Firebase)    │───▶│    Server       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Firestore     │    │ Ollama LLM      │
                       │   Database      │    │ (Llama 3.1 8b)  │
                       └─────────────────┘    └─────────────────┘
```

## Components

### 1. Configuration System (`config/webhook_config.py`)
- Environment-specific configurations (dev/prod/test)
- Ollama, Firebase, server, security, and monitoring settings
- Automatic environment detection and validation

### 2. Local Webhook Server (`scripts/webhook_server.py`)
- FastAPI-based server for receiving cloud requests
- Queue management with priority processing
- Background workers for concurrent processing
- Real-time status updates and progress tracking
- Comprehensive health monitoring and metrics

### 3. Cloud Integration Client (`scripts/cloud_integration.py`)
- Bidirectional communication with Firebase Cloud Functions
- File download from Cloud Storage
- Firestore database integration
- Retry logic with exponential backoff
- Authentication and security features

### 4. Queue Management System
- Priority-based job queues (high/medium/low priority)
- Configurable worker threads for parallel processing
- Job persistence and recovery
- Real-time progress tracking

## Installation & Setup

### Prerequisites
```bash
# Install Ollama
brew install ollama

# Pull the required model
ollama pull llama3.1:8b

# Install Python dependencies
pip install -r scripts/requirements_webhook.txt
```

### Quick Start
```bash
# Start the webhook server
./scripts/start_webhook_server.sh start

# Check server status
./scripts/start_webhook_server.sh status

# Run integration tests
./scripts/start_webhook_server.sh test
```

### Manual Setup
```bash
# 1. Configure environment variables
export ENVIRONMENT=development
export WEBHOOK_HOST=localhost
export WEBHOOK_PORT=8080

# 2. Start Ollama service
ollama serve

# 3. Start webhook server
python3 scripts/webhook_server.py --env development
```

## Configuration

### Environment Variables
```bash
# Core settings
ENVIRONMENT=development|production|testing
WEBHOOK_HOST=localhost
WEBHOOK_PORT=8080

# Firebase settings
FIREBASE_PROJECT_ID=headhunter-ai-0088
GOOGLE_APPLICATION_CREDENTIALS=.gcp/headhunter-service-key.json

# Security settings
WEBHOOK_API_KEY=your_api_key_here
WEBHOOK_SECRET=your_webhook_secret
```

### Configuration File Example
```python
# Create custom configuration
from webhook_config import WebhookIntegrationConfig, Environment

config = WebhookIntegrationConfig(
    environment=Environment.PRODUCTION
)
config.server.port = 80
config.ollama.model = "llama3.1:8b"
config.queue.worker_count = 5
```

## API Endpoints

### Local Webhook Server

#### Health & Status
- `GET /health` - Server health check
- `GET /status/{request_id}` - Processing status for specific request
- `GET /queue/status` - Queue statistics
- `GET /metrics` - Server metrics and performance data

#### Processing Endpoints
- `POST /webhook/process-candidate` - Process single candidate
- `POST /webhook/process-batch` - Process batch of candidates

### Request Format
```json
{
  "request_id": "unique-request-id",
  "action": "process_candidate",
  "data": {
    "candidate_id": "candidate_123",
    "name": "John Doe",
    "resume_text": "Resume content...",
    "resume_file_url": "https://storage.googleapis.com/...",
    "recruiter_comments": "Great candidate...",
    "role_level": "senior",
    "priority": 2
  },
  "callback_url": "https://cloud-function-url/receiveAnalysis",
  "timeout": 300
}
```

### Response Format
```json
{
  "status": "queued|processing|completed|failed",
  "request_id": "unique-request-id",
  "progress": 0.75,
  "result": {
    "candidate_id": "candidate_123",
    "resume_analysis": { ... },
    "recruiter_insights": { ... },
    "overall_score": 0.85,
    "recommendation": "hire"
  },
  "processing_time": 45.2,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Cloud Functions Integration

### Expected Cloud Function Endpoints
The local webhook server communicates with these cloud endpoints:

```typescript
// Firebase Cloud Functions
exports.receiveAnalysis = functions.https.onRequest(...)
exports.updateProcessingStatus = functions.https.onRequest(...)
exports.getCandidate = functions.https.onRequest(...)
exports.healthCheck = functions.https.onRequest(...)
exports.registerWebhook = functions.https.onRequest(...)
```

### Integration Flow
1. **User Upload** → Web App → Cloud Function → Firebase Storage
2. **Cloud Function** → Webhook POST → Local Server
3. **Local Processing** → Ollama Analysis → Results
4. **Results** → Cloud Function → Firestore → Web App

## Processing Pipeline

### Single Candidate Processing
1. Receive webhook request with candidate data
2. Download resume file if needed (from Cloud Storage)
3. Extract text using existing resume_extractor.py
4. Analyze with LLM using existing llm_processor.py
5. Validate results using quality_validator.py
6. Send results back to cloud
7. Update Firestore database

### Batch Processing
1. Receive batch of candidates
2. Create individual processing jobs
3. Process in parallel using worker threads
4. Aggregate results and statistics
5. Send batch results to cloud

## Monitoring & Logging

### Logs
- Server logs: `logs/webhook_integration.log`
- Processing logs: Individual job logging
- Rotating logs with size limits

### Metrics
- Processing time per candidate
- Success/failure rates
- Queue size and throughput
- Memory and CPU usage
- Ollama model performance

### Health Checks
```bash
# Manual health check
curl http://localhost:8080/health

# Automated monitoring
./scripts/start_webhook_server.sh status
```

## Testing

### Automated Test Suite
```bash
# Run comprehensive tests
python3 scripts/webhook_test.py

# Quick health check
python3 scripts/webhook_test.py --quick

# Load testing
python3 scripts/webhook_test.py --load-test
```

### Manual Testing
```bash
# Test single candidate
curl -X POST http://localhost:8080/webhook/process-candidate \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "test-123",
    "action": "process_candidate",
    "data": {
      "candidate_id": "test_candidate",
      "name": "Test User",
      "resume_text": "Software Engineer with 5 years experience..."
    }
  }'

# Check processing status
curl http://localhost:8080/status/test-123
```

## Security Features

### Authentication
- API key authentication for webhook endpoints
- HMAC signature verification for webhook payloads
- IP whitelist for production environments

### Data Protection
- Temporary file cleanup after processing
- Encrypted communication with cloud services
- No permanent storage of sensitive data

### Rate Limiting
- Request rate limiting per IP
- Queue size limits to prevent resource exhaustion
- Timeout protection for long-running processes

## Production Deployment

### Systemd Service (Linux)
```ini
[Unit]
Description=Headhunter Webhook Server
After=network.target

[Service]
Type=simple
User=headhunter
WorkingDirectory=/opt/headhunter
Environment=ENVIRONMENT=production
Environment=WEBHOOK_PORT=80
ExecStart=/opt/headhunter/scripts/start_webhook_server.sh start
Restart=always

[Install]
WantedBy=multi-user.target
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements_webhook.txt .
RUN pip install -r requirements_webhook.txt
COPY scripts/ scripts/
COPY config/ config/
EXPOSE 8080
CMD ["python3", "scripts/webhook_server.py", "--env", "production"]
```

### Environment Configuration
```bash
# Production environment variables
export ENVIRONMENT=production
export WEBHOOK_HOST=0.0.0.0
export WEBHOOK_PORT=80
export WEBHOOK_API_KEY=production_api_key
export GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/service-account.json
```

## Troubleshooting

### Common Issues

#### Ollama Connection Issues
```bash
# Check if Ollama is running
curl http://localhost:11434/api/version

# Start Ollama service
ollama serve

# Check available models
ollama list
```

#### Server Won't Start
```bash
# Check logs
tail -f logs/webhook_server.log

# Check port availability
lsof -i :8080

# Check permissions
ls -la scripts/webhook_server.py
```

#### Processing Failures
```bash
# Check queue status
curl http://localhost:8080/queue/status

# Check server metrics
curl http://localhost:8080/metrics

# Review processing logs
grep ERROR logs/webhook_server.log
```

### Performance Tuning

#### Queue Configuration
```python
# Increase worker count for higher throughput
config.queue.worker_count = 10

# Adjust batch sizes
config.queue.batch_size = 10

# Tune timeouts
config.processing.max_processing_time = 900
```

#### Ollama Optimization
```bash
# Use faster model for development
export OLLAMA_MODEL=llama3.1:7b

# Increase timeout for complex processing
export OLLAMA_TIMEOUT=300
```

## Development

### Adding New Features
1. Update configuration in `webhook_config.py`
2. Modify server endpoints in `webhook_server.py`
3. Extend cloud integration in `cloud_integration.py`
4. Add tests in `webhook_test.py`
5. Update documentation

### Code Structure
```
scripts/
├── webhook_server.py       # Main FastAPI server
├── cloud_integration.py    # Cloud communication
├── webhook_test.py         # Test suite
├── start_webhook_server.sh # Management script
└── requirements_webhook.txt

config/
└── webhook_config.py       # Configuration system

docs/
└── WEBHOOK_INTEGRATION.md  # This documentation
```

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review server logs
3. Run the test suite
4. Check Ollama service status
5. Verify Firebase configuration

## Version History

### v1.0.0 (Current)
- Complete webhook integration system
- FastAPI server with queue management
- Firebase Cloud Functions integration
- Comprehensive testing and monitoring
- Production-ready deployment scripts