"""
TDD tests for Cloud Run Pub/Sub Worker
Following TDD protocol - these tests define the expected behavior before implementation
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List
import base64
from datetime import datetime, timedelta

# Import the modules - should work now that we've implemented them
from cloud_run_worker.main import app, process_candidate_message
from cloud_run_worker.pubsub_handler import PubSubHandler
from cloud_run_worker.candidate_processor import CandidateProcessor
from cloud_run_worker.together_ai_client import TogetherAIClient
from cloud_run_worker.firestore_client import FirestoreClient
from cloud_run_worker.config import Config
from cloud_run_worker.models import (
    PubSubMessage, 
    CandidateProcessingRequest,
    ProcessingResult,
    ProcessingStatus
)


@pytest.fixture
def sample_pubsub_message():
    """Sample Pub/Sub message for testing"""
    return {
        "message": {
            "data": base64.b64encode(json.dumps({
                "candidate_id": "test_candidate_123",
                "action": "enrich_profile",
                "priority": "normal",
                "timestamp": datetime.now().isoformat()
            }).encode()).decode(),
            "messageId": "msg_123456",
            "publishTime": "2025-09-10T20:00:00.000Z",
            "attributes": {
                "source": "candidate_upload",
                "org_id": "org_test_123"
            }
        },
        "subscription": "projects/headhunter-ai-0088/subscriptions/candidate-worker-sub"
    }


@pytest.fixture
def sample_candidate_data():
    """Sample candidate data for processing"""
    return {
        "candidate_id": "test_candidate_123",
        "name": "John Doe",
        "email": "john.doe@example.com",
        "resume_text": "Senior Python developer with 8 years of experience...",
        "recruiter_comments": "Strong technical background, good communication skills",
        "org_id": "org_test_123",
        "uploaded_at": datetime.now().isoformat(),
        "status": "pending_enrichment"
    }


@pytest.fixture
def mock_together_ai_response():
    """Mock Together AI enrichment response"""
    return {
        "resume_analysis": {
            "career_trajectory": {
                "current_level": "Senior",
                "progression_speed": "Fast",
                "trajectory_type": "Technical Leadership"
            },
            "technical_skills": ["Python", "AWS", "Docker", "Kubernetes"],
            "years_experience": 8
        },
        "recruiter_insights": {
            "strengths": ["Strong technical skills", "Leadership potential"],
            "recommendation": "strong_hire"
        },
        "overall_score": 0.92
    }


class TestPubSubMessageProcessing:
    """Test Pub/Sub message handling and parsing"""

    def test_pubsub_message_parsing(self, sample_pubsub_message):
        """Test parsing of Pub/Sub message format"""
        # This test will fail initially - defines expected message parsing
        
        # Expected: Extract candidate_id from base64 encoded data
        handler = PubSubHandler()
        parsed_message = handler.parse_message(sample_pubsub_message)
        
        assert parsed_message.candidate_id == "test_candidate_123"
        assert parsed_message.action == "enrich_profile"
        assert parsed_message.org_id == "org_test_123"
        assert parsed_message.message_id == "msg_123456"

    def test_invalid_message_handling(self):
        """Test handling of malformed Pub/Sub messages"""
        handler = PubSubHandler()
        
        # Test missing data field
        invalid_message_1 = {"message": {"messageId": "123"}}
        with pytest.raises(ValueError, match="Missing message data"):
            handler.parse_message(invalid_message_1)
        
        # Test invalid base64 data
        invalid_message_2 = {
            "message": {
                "data": "invalid_base64!@#",
                "messageId": "123"
            }
        }
        with pytest.raises(ValueError, match="Invalid message data encoding"):
            handler.parse_message(invalid_message_2)

    def test_message_validation(self, sample_pubsub_message):
        """Test validation of required message fields"""
        handler = PubSubHandler()
        
        # Test missing candidate_id
        message_data = json.loads(base64.b64decode(sample_pubsub_message["message"]["data"]))
        del message_data["candidate_id"]
        
        invalid_message = sample_pubsub_message.copy()
        invalid_message["message"]["data"] = base64.b64encode(json.dumps(message_data).encode()).decode()
        
        with pytest.raises(ValueError, match="Missing required field: candidate_id"):
            handler.parse_message(invalid_message)


class TestCandidateProcessor:
    """Test candidate data processing logic"""

    @pytest.mark.asyncio
    async def test_candidate_data_fetching(self, sample_candidate_data):
        """Test fetching candidate data from Firestore"""
        processor = CandidateProcessor()
        
        # Mock Firestore client
        with patch.object(processor, 'firestore_client') as mock_firestore:
            mock_firestore.get_candidate.return_value = sample_candidate_data
            
            candidate = await processor.fetch_candidate_data("test_candidate_123")
            
            assert candidate["candidate_id"] == "test_candidate_123"
            assert candidate["name"] == "John Doe"
            assert candidate["status"] == "pending_enrichment"
            mock_firestore.get_candidate.assert_called_once_with("test_candidate_123")

    @pytest.mark.asyncio
    async def test_candidate_not_found_handling(self):
        """Test handling when candidate doesn't exist"""
        processor = CandidateProcessor()
        
        with patch.object(processor, 'firestore_client') as mock_firestore:
            mock_firestore.get_candidate.return_value = None
            
            with pytest.raises(ValueError, match="Candidate not found"):
                await processor.fetch_candidate_data("nonexistent_candidate")

    @pytest.mark.asyncio
    async def test_together_ai_processing(self, sample_candidate_data, mock_together_ai_response):
        """Test Together AI enrichment processing"""
        processor = CandidateProcessor()
        
        with patch.object(processor, 'together_ai_client') as mock_together_ai:
            mock_together_ai.enrich_candidate.return_value = mock_together_ai_response
            
            result = await processor.process_with_together_ai(sample_candidate_data)
            
            assert result["overall_score"] == 0.92
            assert result["resume_analysis"]["technical_skills"] == ["Python", "AWS", "Docker", "Kubernetes"]
            assert result["recruiter_insights"]["recommendation"] == "strong_hire"

    @pytest.mark.asyncio
    async def test_processing_result_storage(self, sample_candidate_data, mock_together_ai_response):
        """Test storing enriched results back to Firestore"""
        processor = CandidateProcessor()
        
        with patch.object(processor, 'firestore_client') as mock_firestore:
            mock_firestore.update_candidate.return_value = True
            
            success = await processor.store_processing_result(
                "test_candidate_123", 
                mock_together_ai_response
            )
            
            assert success is True
            mock_firestore.update_candidate.assert_called_once()
            
            # Verify the update call includes enriched data
            call_args = mock_firestore.update_candidate.call_args
            assert call_args[0][0] == "test_candidate_123"
            assert "resume_analysis" in call_args[0][1]
            assert call_args[0][1]["status"] == "enriched"


class TestTogetherAIIntegration:
    """Test Together AI API integration"""

    @pytest.mark.asyncio
    async def test_together_ai_client_initialization(self):
        """Test Together AI client setup and configuration"""
        client = TogetherAIClient(api_key="test_key")
        
        assert client.api_key == "test_key"
        assert client.model == "meta-llama/Llama-3.1-8B-Instruct-Turbo"
        assert client.base_url is not None

    @pytest.mark.asyncio
    async def test_candidate_enrichment_request(self, sample_candidate_data):
        """Test making enrichment request to Together AI"""
        client = TogetherAIClient(api_key="test_key")
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "resume_analysis": {"technical_skills": ["Python"]},
                            "overall_score": 0.85
                        })
                    }
                }]
            })
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await client.enrich_candidate(sample_candidate_data)
            
            assert "resume_analysis" in result
            assert result["overall_score"] == 0.85

    @pytest.mark.asyncio
    async def test_together_ai_error_handling(self, sample_candidate_data):
        """Test error handling for Together AI API failures"""
        client = TogetherAIClient(api_key="test_key")
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = Mock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")
            mock_post.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(Exception, match="Together AI API error"):
                await client.enrich_candidate(sample_candidate_data)

    @pytest.mark.asyncio
    async def test_together_ai_rate_limiting(self, sample_candidate_data):
        """Test handling of rate limiting from Together AI"""
        client = TogetherAIClient(api_key="test_key")
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            # First call returns rate limit error
            mock_response_1 = Mock()
            mock_response_1.status = 429
            mock_response_1.headers = {"Retry-After": "1"}
            
            # Second call succeeds
            mock_response_2 = Mock()
            mock_response_2.status = 200
            mock_response_2.json = AsyncMock(return_value={
                "choices": [{"message": {"content": '{"overall_score": 0.85}'}}]
            })
            
            mock_post.return_value.__aenter__.side_effect = [mock_response_1, mock_response_2]
            
            # Should retry and succeed
            result = await client.enrich_candidate(sample_candidate_data)
            assert result["overall_score"] == 0.85


class TestFirestoreIntegration:
    """Test Firestore client operations"""

    @pytest.mark.asyncio
    async def test_firestore_client_initialization(self):
        """Test Firestore client setup"""
        client = FirestoreClient(project_id="test-project")
        
        assert client.project_id == "test-project"
        assert client.collection_name == "candidates"

    @pytest.mark.asyncio
    async def test_get_candidate_operation(self, sample_candidate_data):
        """Test retrieving candidate from Firestore"""
        client = FirestoreClient()
        
        with patch.object(client, 'db') as mock_db:
            mock_doc = Mock()
            mock_doc.exists = True
            mock_doc.to_dict.return_value = sample_candidate_data
            mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
            
            result = await client.get_candidate("test_candidate_123")
            
            assert result == sample_candidate_data

    @pytest.mark.asyncio
    async def test_update_candidate_operation(self, mock_together_ai_response):
        """Test updating candidate with enriched data"""
        client = FirestoreClient()
        
        with patch.object(client, 'db') as mock_db:
            mock_db.collection.return_value.document.return_value.update.return_value = None
            
            success = await client.update_candidate("test_candidate_123", {
                "resume_analysis": mock_together_ai_response["resume_analysis"],
                "status": "enriched",
                "processed_at": datetime.now().isoformat()
            })
            
            assert success is True
            mock_db.collection.return_value.document.return_value.update.assert_called_once()


class TestRetryLogicAndErrorHandling:
    """Test retry mechanisms and error handling"""

    @pytest.mark.asyncio
    async def test_exponential_backoff_retry(self):
        """Test exponential backoff for retryable errors"""
        processor = CandidateProcessor()
        
        call_count = 0
        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await processor.retry_with_backoff(failing_function, max_retries=3)
        
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded"""
        processor = CandidateProcessor()
        
        async def always_failing_function():
            raise Exception("Permanent failure")
        
        with pytest.raises(Exception, match="Permanent failure"):
            await processor.retry_with_backoff(always_failing_function, max_retries=2)

    def test_dead_letter_queue_handling(self, sample_pubsub_message):
        """Test sending failed messages to dead letter queue"""
        handler = PubSubHandler()
        
        with patch.object(handler, 'dead_letter_publisher') as mock_publisher:
            handler.send_to_dead_letter_queue(
                sample_pubsub_message, 
                "Processing failed after max retries"
            )
            
            mock_publisher.publish.assert_called_once()
            # Verify message includes error details
            published_data = mock_publisher.publish.call_args[1]['data']
            error_info = json.loads(published_data)
            assert "error" in error_info
            assert "original_message" in error_info


class TestHealthChecksAndMetrics:
    """Test health monitoring and metrics collection"""

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self):
        """Test health check returns service status"""
        # This will test the FastAPI health endpoint
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert "timestamp" in response.json()
        assert "version" in response.json()

    @pytest.mark.asyncio
    async def test_metrics_collection(self):
        """Test metrics are properly collected during processing"""
        processor = CandidateProcessor()
        
        # Process a message and verify metrics are updated
        with patch.object(processor, 'metrics') as mock_metrics:
            await processor.process_candidate_message({
                "candidate_id": "test_123",
                "action": "enrich_profile"
            })
            
            # Verify metrics calls
            mock_metrics.increment_counter.assert_called()
            mock_metrics.record_processing_time.assert_called()

    def test_processing_status_tracking(self):
        """Test tracking of processing status and progress"""
        processor = CandidateProcessor()
        
        # Start processing
        processor.update_processing_status("test_123", ProcessingStatus.IN_PROGRESS)
        status = processor.get_processing_status("test_123")
        
        assert status == ProcessingStatus.IN_PROGRESS
        
        # Complete processing
        processor.update_processing_status("test_123", ProcessingStatus.COMPLETED)
        status = processor.get_processing_status("test_123")
        
        assert status == ProcessingStatus.COMPLETED


class TestFastAPIEndpoints:
    """Test FastAPI application endpoints"""

    def test_pubsub_webhook_endpoint(self, sample_pubsub_message):
        """Test Pub/Sub webhook endpoint for message processing"""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        with patch('cloud_run_worker.main.process_candidate_message') as mock_process:
            mock_process.return_value = {"status": "processed", "candidate_id": "test_123"}
            
            response = client.post("/pubsub/webhook", json=sample_pubsub_message)
            
            assert response.status_code == 200
            assert response.json()["status"] == "processed"
            mock_process.assert_called_once()

    def test_webhook_endpoint_error_handling(self, sample_pubsub_message):
        """Test webhook endpoint handles processing errors gracefully"""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        with patch('cloud_run_worker.main.process_candidate_message') as mock_process:
            mock_process.side_effect = Exception("Processing failed")
            
            response = client.post("/pubsub/webhook", json=sample_pubsub_message)
            
            assert response.status_code == 500
            assert "error" in response.json()

    def test_metrics_endpoint(self):
        """Test metrics endpoint returns processing statistics"""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics = response.json()
        assert "messages_processed" in metrics
        assert "processing_times" in metrics
        assert "error_count" in metrics


class TestIntegrationScenarios:
    """Test end-to-end integration scenarios"""

    @pytest.mark.asyncio
    async def test_complete_processing_workflow(self, sample_pubsub_message, sample_candidate_data, mock_together_ai_response):
        """Test complete message processing from Pub/Sub to Firestore"""
        
        with patch('cloud_run_worker.pubsub_handler.PubSubHandler.parse_message') as mock_parse, \
             patch('cloud_run_worker.candidate_processor.CandidateProcessor.fetch_candidate_data') as mock_fetch, \
             patch('cloud_run_worker.candidate_processor.CandidateProcessor.process_with_together_ai') as mock_process, \
             patch('cloud_run_worker.candidate_processor.CandidateProcessor.store_processing_result') as mock_store:
            
            # Setup mocks
            mock_parse.return_value = Mock(candidate_id="test_candidate_123", action="enrich_profile")
            mock_fetch.return_value = sample_candidate_data
            mock_process.return_value = mock_together_ai_response
            mock_store.return_value = True
            
            # Process message
            result = await process_candidate_message(sample_pubsub_message)
            
            # Verify complete workflow
            assert result["status"] == "completed"
            assert result["candidate_id"] == "test_candidate_123"
            mock_parse.assert_called_once()
            mock_fetch.assert_called_once_with("test_candidate_123")
            mock_process.assert_called_once()
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_processing_scenario(self):
        """Test processing multiple candidates in batch"""
        processor = CandidateProcessor()
        
        candidate_ids = ["cand_1", "cand_2", "cand_3"]
        
        with patch.object(processor, 'process_single_candidate') as mock_process:
            mock_process.return_value = {"status": "completed"}
            
            results = await processor.process_batch(candidate_ids)
            
            assert len(results) == 3
            assert all(result["status"] == "completed" for result in results)
            assert mock_process.call_count == 3

    def test_autoscaling_simulation(self):
        """Test behavior under high load to simulate autoscaling"""
        # This would test concurrent processing capabilities
        
        import concurrent.futures
        import threading
        
        processor = CandidateProcessor()
        
        def process_message(message_id):
            # Simulate processing time
            import time
            time.sleep(0.1)
            return {"message_id": message_id, "status": "processed"}
        
        # Simulate 50 concurrent messages
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_message, f"msg_{i}") for i in range(50)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        assert len(results) == 50
        assert all(result["status"] == "processed" for result in results)


# Test configuration and utilities
class TestConfiguration:
    """Test configuration management"""

    def test_config_loading(self):
        """Test loading configuration from environment variables"""
        import os
        
        # Set test environment variables
        os.environ["TOGETHER_AI_API_KEY"] = "test_key"
        os.environ["PROJECT_ID"] = "test-project"
        
        config = Config(testing=True)
        
        assert config.together_ai_api_key == "test_key"
        assert config.project_id == "test-project"
        assert config.pubsub_topic == "candidate-process-requests"  # default

    def test_config_validation(self):
        """Test configuration validation for required fields"""
        import os
        
        # Remove required environment variable
        if "TOGETHER_AI_API_KEY" in os.environ:
            del os.environ["TOGETHER_AI_API_KEY"]
        
        with pytest.raises(ValueError, match="TOGETHER_AI_API_KEY is required"):
            Config()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])