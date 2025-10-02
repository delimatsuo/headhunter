#!/usr/bin/env python3
"""
Cloud Integration Module
Handles bidirectional communication between local webhook server and Firebase Cloud Functions
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import httpx
from pathlib import Path
import base64
import hashlib
import hmac

# Import configuration
import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / 'config'))
from webhook_config import WebhookIntegrationConfig

# Firebase/Google Cloud imports
try:
    from google.cloud import firestore
    from google.cloud import storage
    from google.auth import default
    from google.oauth2 import service_account
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("Warning: Firebase/Google Cloud libraries not available. Install with: pip install google-cloud-firestore google-cloud-storage")


class CloudAPIError(Exception):
    """Custom exception for cloud API errors"""
    pass


class RetryConfig:
    """Configuration for retry logic"""
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt using exponential backoff"""
        delay = self.base_delay * (2 ** (attempt - 1))
        return min(delay, self.max_delay)


class CloudAPIClient:
    """Client for interacting with Firebase Cloud Functions and services"""
    
    def __init__(self, config: WebhookIntegrationConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.retry_config = RetryConfig(
            max_retries=config.firebase.max_retries,
            base_delay=2.0,
            max_delay=30.0
        )
        
        # HTTP client for API calls
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.firebase.timeout),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50)
        )
        
        # Initialize Firebase clients if available
        self.firestore_client = None
        self.storage_client = None
        self._init_firebase_clients()
        
        # Cache for endpoints
        self.endpoints = config.get_cloud_endpoints()
        
        self.logger.info("CloudAPIClient initialized")
    
    def _init_firebase_clients(self):
        """Initialize Firebase clients"""
        if not FIREBASE_AVAILABLE:
            self.logger.warning("Firebase libraries not available - some features will be disabled")
            return
        
        try:
            # Load service account credentials
            service_account_path = Path(self.config.firebase.service_account_path)
            if service_account_path.exists():
                credentials = service_account.Credentials.from_service_account_file(
                    str(service_account_path)
                )
                
                # Initialize Firestore
                self.firestore_client = firestore.Client(
                    project=self.config.firebase.project_id,
                    credentials=credentials
                )
                
                # Initialize Cloud Storage
                self.storage_client = storage.Client(
                    project=self.config.firebase.project_id,
                    credentials=credentials
                )
                
                self.logger.info("Firebase clients initialized with service account")
            else:
                self.logger.warning(f"Service account file not found: {service_account_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Firebase clients: {e}")
    
    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        last_exception = None
        
        for attempt in range(1, self.retry_config.max_retries + 1):
            try:
                # Add authentication if configured
                headers = kwargs.get('headers', {})
                if self.config.security.api_key:
                    headers['Authorization'] = f'Bearer {self.config.security.api_key}'
                
                # Add webhook signature if configured
                if self.config.security.webhook_secret and 'json' in kwargs:
                    payload = json.dumps(kwargs['json']).encode('utf-8')
                    signature = hmac.new(
                        self.config.security.webhook_secret.encode('utf-8'),
                        payload,
                        hashlib.sha256
                    ).hexdigest()
                    headers['X-Webhook-Signature'] = f'sha256={signature}'
                
                headers['Content-Type'] = 'application/json'
                headers['User-Agent'] = 'Headhunter-Webhook-Client/1.0'
                kwargs['headers'] = headers
                
                # Make request
                response = await self.http_client.request(method, url, **kwargs)
                response.raise_for_status()
                
                # Parse JSON response
                if response.headers.get('content-type', '').startswith('application/json'):
                    return response.json()
                else:
                    return {'data': response.text, 'status_code': response.status_code}
                
            except httpx.HTTPStatusError as e:
                last_exception = e
                self.logger.warning(f"HTTP {e.response.status_code} on attempt {attempt}: {url}")
                
                # Don't retry on 4xx errors (client errors)
                if 400 <= e.response.status_code < 500:
                    raise CloudAPIError(f"Client error: {e.response.status_code} - {e.response.text}")
                
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_exception = e
                self.logger.warning(f"Connection error on attempt {attempt}: {e}")
            
            # Wait before retry
            if attempt < self.retry_config.max_retries:
                delay = self.retry_config.get_delay(attempt)
                self.logger.info(f"Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)
        
        # All attempts failed
        raise CloudAPIError(f"Request failed after {self.retry_config.max_retries} attempts: {last_exception}")
    
    async def register_webhook(self, webhook_url: str, webhook_secret: str) -> Dict[str, Any]:
        """Register webhook URL with cloud functions"""
        try:
            url = self.endpoints.get('webhook_register')
            if not url:
                raise CloudAPIError("Webhook register endpoint not configured")
            
            payload = {
                'webhook_url': webhook_url,
                'webhook_secret': webhook_secret,
                'timestamp': datetime.now().isoformat()
            }
            
            response = await self._make_request('POST', url, json=payload)
            self.logger.info(f"Webhook registered successfully: {webhook_url}")
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to register webhook: {e}")
            raise CloudAPIError(f"Webhook registration failed: {e}")
    
    async def send_processing_results(self, request_id: str, results: Dict[str, Any]) -> Dict[str, Any]:
        """Send processing results back to cloud"""
        try:
            url = self.endpoints.get('receive_analysis')
            if not url:
                raise CloudAPIError("Receive analysis endpoint not configured")
            
            payload = {
                'request_id': request_id,
                'results': results,
                'timestamp': datetime.now().isoformat(),
                'source': 'local_webhook_server'
            }
            
            response = await self._make_request('POST', url, json=payload)
            self.logger.info(f"Results sent for request {request_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to send results for {request_id}: {e}")
            raise CloudAPIError(f"Failed to send results: {e}")
    
    async def send_status_update(self, request_id: str, status: Dict[str, Any]) -> Dict[str, Any]:
        """Send processing status update to cloud"""
        try:
            url = self.endpoints.get('update_status')
            if not url:
                raise CloudAPIError("Update status endpoint not configured")
            
            payload = {
                'request_id': request_id,
                'status': status,
                'timestamp': datetime.now().isoformat()
            }
            
            response = await self._make_request('POST', url, json=payload)
            self.logger.debug(f"Status update sent for request {request_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to send status update for {request_id}: {e}")
            # Don't raise exception for status updates as they're not critical
            return {'error': str(e)}
    
    async def send_processing_error(self, request_id: str, error: str) -> Dict[str, Any]:
        """Send processing error to cloud"""
        try:
            url = self.endpoints.get('receive_analysis')
            if not url:
                raise CloudAPIError("Receive analysis endpoint not configured")
            
            payload = {
                'request_id': request_id,
                'error': error,
                'timestamp': datetime.now().isoformat(),
                'source': 'local_webhook_server'
            }
            
            response = await self._make_request('POST', url, json=payload)
            self.logger.info(f"Error sent for request {request_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to send error for {request_id}: {e}")
            return {'error': str(e)}
    
    async def get_candidate_data(self, candidate_id: str) -> Dict[str, Any]:
        """Fetch candidate data from cloud"""
        try:
            url = self.endpoints.get('get_candidate')
            if not url:
                raise CloudAPIError("Get candidate endpoint not configured")
            
            # Make request with candidate ID as query parameter
            full_url = f"{url}?candidate_id={candidate_id}"
            response = await self._make_request('GET', full_url)
            
            self.logger.info(f"Retrieved candidate data for {candidate_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"Failed to get candidate data for {candidate_id}: {e}")
            raise CloudAPIError(f"Failed to get candidate data: {e}")
    
    async def download_resume_file(self, file_url: str, local_path: str) -> bool:
        """Download resume file from cloud storage"""
        try:
            # If it's a Firebase Storage URL, use the storage client
            if 'firebase' in file_url and self.storage_client:
                return await self._download_from_firebase_storage(file_url, local_path)
            else:
                # Download using HTTP
                return await self._download_via_http(file_url, local_path)
                
        except Exception as e:
            self.logger.error(f"Failed to download file {file_url}: {e}")
            return False
    
    async def _download_via_http(self, url: str, local_path: str) -> bool:
        """Download file via HTTP"""
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            # Save file
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            self.logger.info(f"Downloaded file to {local_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"HTTP download failed: {e}")
            return False
    
    async def _download_from_firebase_storage(self, storage_url: str, local_path: str) -> bool:
        """Download file from Firebase Storage"""
        if not self.storage_client:
            return False
        
        try:
            # Extract bucket and blob name from URL
            # Format: https://firebasestorage.googleapis.com/v0/b/bucket/o/path%2Fto%2Ffile.pdf
            import urllib.parse
            from urllib.parse import unquote
            
            # Simple parsing - this might need adjustment based on actual URL format
            if '/o/' in storage_url:
                blob_name = storage_url.split('/o/')[1].split('?')[0]
                blob_name = unquote(blob_name)
            else:
                raise ValueError("Invalid Firebase Storage URL format")
            
            # Get bucket
            bucket = self.storage_client.bucket(self.config.firebase.storage_bucket)
            blob = bucket.blob(blob_name)
            
            # Download
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(local_path)
            
            self.logger.info(f"Downloaded file from Firebase Storage to {local_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Firebase Storage download failed: {e}")
            return False
    
    async def ping_cloud_functions(self) -> Dict[str, Any]:
        """Ping cloud functions to check connectivity"""
        try:
            url = self.endpoints.get('health_check')
            if not url:
                raise CloudAPIError("Health check endpoint not configured")
            
            start_time = time.time()
            response = await self._make_request('GET', url)
            response_time = time.time() - start_time
            
            return {
                'status': 'connected',
                'response_time': response_time,
                'cloud_status': response
            }
            
        except Exception as e:
            return {
                'status': 'disconnected',
                'error': str(e)
            }
    
    def save_candidate_to_firestore(self, candidate_id: str, profile_data: Dict[str, Any]) -> bool:
        """Save candidate profile to Firestore"""
        if not self.firestore_client:
            self.logger.warning("Firestore client not available")
            return False
        
        try:
            # Reference to candidates collection
            doc_ref = self.firestore_client.collection('candidates').document(candidate_id)
            
            # Add metadata
            profile_data['updated_at'] = datetime.now()
            profile_data['source'] = 'local_webhook_processing'
            
            # Save document
            doc_ref.set(profile_data, merge=True)
            
            self.logger.info(f"Saved candidate {candidate_id} to Firestore")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save to Firestore: {e}")
            return False
    
    def get_candidate_from_firestore(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """Get candidate data from Firestore"""
        if not self.firestore_client:
            return None
        
        try:
            doc_ref = self.firestore_client.collection('candidates').document(candidate_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get from Firestore: {e}")
            return None
    
    async def close(self):
        """Close HTTP client and cleanup resources"""
        await self.http_client.aclose()
        self.logger.info("CloudAPIClient closed")


class CloudIntegrationManager:
    """High-level manager for cloud integration"""
    
    def __init__(self, config: WebhookIntegrationConfig):
        self.config = config
        self.client = CloudAPIClient(config)
        self.logger = logging.getLogger(__name__)
        
        # Statistics
        self.stats = {
            'requests_sent': 0,
            'requests_failed': 0,
            'files_downloaded': 0,
            'results_uploaded': 0,
            'start_time': datetime.now()
        }
    
    async def process_webhook_candidate(self, request_id: str, candidate_data: Dict[str, Any]) -> Dict[str, Any]:
        """Full workflow for processing a candidate from webhook request"""
        try:
            self.logger.info(f"Processing webhook candidate {request_id}")
            
            # Step 1: Download resume file if needed
            local_resume_path = None
            if candidate_data.get('resume_file_url'):
                local_resume_path = f"temp_resumes/{request_id}_{candidate_data.get('candidate_id', 'unknown')}.pdf"
                success = await self.client.download_resume_file(
                    candidate_data['resume_file_url'],
                    local_resume_path
                )
                if success:
                    candidate_data['resume_file'] = local_resume_path
                    self.stats['files_downloaded'] += 1
                else:
                    self.logger.warning(f"Failed to download resume for {request_id}")
            
            # Step 2: Process candidate with local LLM
            # This would be handled by the webhook server's job processing
            
            # Step 3: Send results back to cloud
            # This would also be handled by the job processing
            
            return {
                'status': 'initiated',
                'request_id': request_id,
                'local_resume_path': local_resume_path
            }
            
        except Exception as e:
            self.logger.error(f"Failed to process webhook candidate {request_id}: {e}")
            self.stats['requests_failed'] += 1
            raise
    
    async def send_batch_results(self, batch_results: List[Dict[str, Any]]) -> bool:
        """Send batch processing results to cloud"""
        try:
            success_count = 0
            
            for result in batch_results:
                request_id = result.get('request_id', 'unknown')
                try:
                    await self.client.send_processing_results(request_id, result)
                    success_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to send result for {request_id}: {e}")
            
            self.stats['results_uploaded'] += success_count
            
            self.logger.info(f"Sent {success_count}/{len(batch_results)} batch results successfully")
            return success_count == len(batch_results)
            
        except Exception as e:
            self.logger.error(f"Failed to send batch results: {e}")
            return False
    
    def get_integration_stats(self) -> Dict[str, Any]:
        """Get integration statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'success_rate': (
                (self.stats['requests_sent'] - self.stats['requests_failed']) / 
                max(self.stats['requests_sent'], 1)
            )
        }
    
    async def test_cloud_connectivity(self) -> Dict[str, Any]:
        """Test connectivity to all cloud endpoints"""
        results = {}
        
        # Test Firebase/Cloud Functions ping
        results['cloud_functions'] = await self.client.ping_cloud_functions()
        
        # Test Firestore connectivity
        if self.client.firestore_client:
            try:
                # Simple read test
                test_doc = self.client.firestore_client.collection('test').document('connectivity_test')
                test_doc.set({'timestamp': datetime.now(), 'test': True})
                results['firestore'] = {'status': 'connected'}
            except Exception as e:
                results['firestore'] = {'status': 'disconnected', 'error': str(e)}
        else:
            results['firestore'] = {'status': 'not_configured'}
        
        # Test Cloud Storage
        if self.client.storage_client:
            try:
                bucket = self.client.storage_client.bucket(self.config.firebase.storage_bucket)
                blob = bucket.blob('test/connectivity_test.txt')
                blob.upload_from_string(f'Connectivity test: {datetime.now()}')
                results['storage'] = {'status': 'connected'}
            except Exception as e:
                results['storage'] = {'status': 'disconnected', 'error': str(e)}
        else:
            results['storage'] = {'status': 'not_configured'}
        
        return results
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.client.close()


# Async context manager for cloud integration
class CloudIntegrationContext:
    """Context manager for cloud integration"""
    
    def __init__(self, config: WebhookIntegrationConfig):
        self.config = config
        self.manager = None
    
    async def __aenter__(self):
        self.manager = CloudIntegrationManager(self.config)
        return self.manager
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.manager:
            await self.manager.cleanup()


async def main():
    """Test cloud integration functionality"""
    from webhook_config import get_development_config
    
    config = get_development_config()
    
    async with CloudIntegrationContext(config) as integration:
        print("Testing Cloud Integration")
        print("=" * 40)
        
        # Test connectivity
        print("\n1. Testing cloud connectivity...")
        connectivity = await integration.test_cloud_connectivity()
        for service, result in connectivity.items():
            print(f"   {service}: {result['status']}")
        
        # Test statistics
        print("\n2. Integration statistics:")
        stats = integration.get_integration_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        print("\n✓ Cloud integration test completed")


if __name__ == "__main__":
    asyncio.run(main())