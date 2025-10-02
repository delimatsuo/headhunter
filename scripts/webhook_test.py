#!/usr/bin/env python3
"""
Webhook Integration Test Suite
Comprehensive testing for the webhook integration system
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any
import httpx
import pytest
import uuid

# Import local modules
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT / 'scripts'))
sys.path.append(str(REPO_ROOT / 'config'))

from webhook_config import get_development_config, WebhookIntegrationConfig
from cloud_integration import CloudAPIClient, CloudIntegrationManager, CloudIntegrationContext
from webhook_server import WebhookServer, CandidateData, WebhookRequest


class WebhookTester:
    """Test suite for webhook integration"""
    
    def __init__(self, config: WebhookIntegrationConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.base_url = f"http://{config.server.host}:{config.server.port}"
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    async def test_webhook_server_startup(self) -> Dict[str, Any]:
        """Test webhook server startup and health check"""
        try:
            async with httpx.AsyncClient() as client:
                # Test health endpoint
                response = await client.get(f"{self.base_url}/health", timeout=10)
                
                if response.status_code == 200:
                    health_data = response.json()
                    return {
                        'status': 'success',
                        'health_data': health_data,
                        'message': 'Webhook server is running and healthy'
                    }
                else:
                    return {
                        'status': 'failed',
                        'error': f'Health check returned {response.status_code}',
                        'response': response.text
                    }
                    
        except httpx.ConnectError:
            return {
                'status': 'failed',
                'error': 'Cannot connect to webhook server - make sure it is running'
            }
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def test_single_candidate_processing(self) -> Dict[str, Any]:
        """Test processing a single candidate via webhook"""
        try:
            # Create test candidate data
            candidate_data = {
                "candidate_id": f"test_{uuid.uuid4().hex[:8]}",
                "name": "John Doe",
                "resume_text": """
                John Doe
                Senior Software Engineer
                
                Experience:
                - Software Engineer at Google (2020-2024)
                  Developed cloud infrastructure systems
                  Led team of 5 engineers
                  
                - Junior Developer at Startup Inc (2018-2020)
                  Full-stack web development
                
                Education:
                BS Computer Science, Stanford University
                
                Skills: Python, JavaScript, AWS, Leadership
                """,
                "recruiter_comments": "Strong technical background. Good communication skills. Recommended for senior role.",
                "role_level": "senior",
                "priority": 2
            }
            
            # Create webhook request
            webhook_request = {
                "request_id": str(uuid.uuid4()),
                "action": "process_candidate",
                "data": candidate_data,
                "timeout": 300
            }
            
            # Send request to webhook server
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/webhook/process-candidate",
                    json=webhook_request,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    request_id = result.get('request_id')
                    
                    # Poll for results
                    max_polls = 60  # 5 minutes max
                    for i in range(max_polls):
                        await asyncio.sleep(5)  # Wait 5 seconds
                        
                        status_response = await client.get(
                            f"{self.base_url}/status/{request_id}",
                            timeout=10
                        )
                        
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            
                            if status_data['status'] == 'completed':
                                return {
                                    'status': 'success',
                                    'message': 'Candidate processed successfully',
                                    'request_id': request_id,
                                    'result': status_data.get('result'),
                                    'processing_time': status_data.get('processing_time')
                                }
                            elif status_data['status'] == 'failed':
                                return {
                                    'status': 'failed',
                                    'error': status_data.get('error'),
                                    'request_id': request_id
                                }
                    
                    return {
                        'status': 'timeout',
                        'error': 'Processing timed out after 5 minutes',
                        'request_id': request_id
                    }
                else:
                    return {
                        'status': 'failed',
                        'error': f'Webhook request failed: {response.status_code}',
                        'response': response.text
                    }
                    
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def test_batch_processing(self) -> Dict[str, Any]:
        """Test batch candidate processing"""
        try:
            # Create test batch data
            candidates = []
            for i in range(3):
                candidate = {
                    "candidate_id": f"batch_test_{i}_{uuid.uuid4().hex[:6]}",
                    "name": f"Test Candidate {i+1}",
                    "resume_text": f"""
                    Test Candidate {i+1}
                    Software Engineer
                    
                    Experience: {i+2} years in software development
                    Skills: Python, JavaScript, React
                    """,
                    "recruiter_comments": f"Candidate {i+1} shows promise. Technical skills are good.",
                    "priority": 1
                }
                candidates.append(candidate)
            
            webhook_request = {
                "request_id": str(uuid.uuid4()),
                "action": "process_batch",
                "data": candidates,
                "timeout": 600
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/webhook/process-batch",
                    json=webhook_request,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    request_id = result.get('request_id')
                    
                    # Poll for completion (longer timeout for batch)
                    max_polls = 120  # 10 minutes max
                    for i in range(max_polls):
                        await asyncio.sleep(5)
                        
                        status_response = await client.get(
                            f"{self.base_url}/status/{request_id}",
                            timeout=10
                        )
                        
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            
                            if status_data['status'] == 'completed':
                                batch_result = status_data.get('result', {})
                                return {
                                    'status': 'success',
                                    'message': f'Batch of {len(candidates)} candidates processed',
                                    'request_id': request_id,
                                    'profiles_processed': len(batch_result.get('profiles', [])),
                                    'processing_stats': batch_result.get('stats'),
                                    'processing_time': status_data.get('processing_time')
                                }
                            elif status_data['status'] == 'failed':
                                return {
                                    'status': 'failed',
                                    'error': status_data.get('error'),
                                    'request_id': request_id
                                }
                    
                    return {
                        'status': 'timeout',
                        'error': 'Batch processing timed out',
                        'request_id': request_id
                    }
                else:
                    return {
                        'status': 'failed',
                        'error': f'Batch request failed: {response.status_code}',
                        'response': response.text
                    }
                    
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def test_queue_management(self) -> Dict[str, Any]:
        """Test queue status and management"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/queue/status", timeout=10)
                
                if response.status_code == 200:
                    queue_stats = response.json()
                    return {
                        'status': 'success',
                        'queue_stats': queue_stats,
                        'message': 'Queue status retrieved successfully'
                    }
                else:
                    return {
                        'status': 'failed',
                        'error': f'Queue status request failed: {response.status_code}'
                    }
                    
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def test_metrics_endpoint(self) -> Dict[str, Any]:
        """Test metrics endpoint"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/metrics", timeout=10)
                
                if response.status_code == 200:
                    metrics = response.json()
                    return {
                        'status': 'success',
                        'metrics': metrics,
                        'message': 'Metrics retrieved successfully'
                    }
                else:
                    return {
                        'status': 'failed',
                        'error': f'Metrics request failed: {response.status_code}'
                    }
                    
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def test_cloud_integration(self) -> Dict[str, Any]:
        """Test cloud integration functionality"""
        try:
            async with CloudIntegrationContext(self.config) as integration:
                # Test cloud connectivity
                connectivity = await integration.test_cloud_connectivity()
                
                # Get integration stats
                stats = integration.get_integration_stats()
                
                return {
                    'status': 'success',
                    'connectivity': connectivity,
                    'stats': stats,
                    'message': 'Cloud integration test completed'
                }
                
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive test suite"""
        test_results = {}
        start_time = datetime.now()
        
        print("Starting Webhook Integration Test Suite")
        print("=" * 50)
        
        # Test 1: Server Health
        print("\n1. Testing webhook server health...")
        test_results['server_health'] = await self.test_webhook_server_startup()
        print(f"   Result: {test_results['server_health']['status']}")
        
        if test_results['server_health']['status'] != 'success':
            print("   ❌ Server not available - skipping remaining tests")
            return {
                'overall_status': 'failed',
                'error': 'Webhook server not available',
                'results': test_results
            }
        
        # Test 2: Queue Management
        print("\n2. Testing queue management...")
        test_results['queue_management'] = await self.test_queue_management()
        print(f"   Result: {test_results['queue_management']['status']}")
        
        # Test 3: Metrics
        print("\n3. Testing metrics endpoint...")
        test_results['metrics'] = await self.test_metrics_endpoint()
        print(f"   Result: {test_results['metrics']['status']}")
        
        # Test 4: Cloud Integration
        print("\n4. Testing cloud integration...")
        test_results['cloud_integration'] = await self.test_cloud_integration()
        print(f"   Result: {test_results['cloud_integration']['status']}")
        
        # Test 5: Single Candidate Processing
        print("\n5. Testing single candidate processing...")
        test_results['single_candidate'] = await self.test_single_candidate_processing()
        print(f"   Result: {test_results['single_candidate']['status']}")
        if test_results['single_candidate']['status'] == 'success':
            processing_time = test_results['single_candidate'].get('processing_time', 'N/A')
            print(f"   Processing time: {processing_time}s")
        
        # Test 6: Batch Processing
        print("\n6. Testing batch processing...")
        test_results['batch_processing'] = await self.test_batch_processing()
        print(f"   Result: {test_results['batch_processing']['status']}")
        if test_results['batch_processing']['status'] == 'success':
            profiles_processed = test_results['batch_processing'].get('profiles_processed', 0)
            processing_time = test_results['batch_processing'].get('processing_time', 'N/A')
            print(f"   Profiles processed: {profiles_processed}")
            print(f"   Processing time: {processing_time}s")
        
        # Calculate overall results
        total_time = (datetime.now() - start_time).total_seconds()
        success_count = sum(1 for result in test_results.values() if result['status'] == 'success')
        total_tests = len(test_results)
        
        overall_status = 'success' if success_count == total_tests else 'partial' if success_count > 0 else 'failed'
        
        print(f"\n" + "=" * 50)
        print(f"Test Summary:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Passed: {success_count}")
        print(f"  Failed: {total_tests - success_count}")
        print(f"  Success Rate: {success_count/total_tests*100:.1f}%")
        print(f"  Total Time: {total_time:.2f}s")
        print(f"  Overall Status: {overall_status.upper()}")
        
        return {
            'overall_status': overall_status,
            'success_rate': success_count / total_tests,
            'total_time': total_time,
            'results': test_results
        }


async def main():
    """Main test function"""
    print("Webhook Integration Test Suite")
    print("=" * 50)
    
    # Load test configuration
    config = get_development_config()
    
    # Override for testing
    config.server.port = 8080
    config.processing.log_level = "INFO"
    
    print(f"Test Configuration:")
    print(f"  Server: {config.server.host}:{config.server.port}")
    print(f"  Ollama: {config.ollama.model}")
    print(f"  Environment: {config.environment.value}")
    
    # Create tester
    tester = WebhookTester(config)
    
    # Run tests
    results = await tester.run_comprehensive_test()
    
    # Save results
    results_file = f"webhook_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📊 Test results saved to: {results_file}")
    
    # Exit with appropriate code
    exit_code = 0 if results['overall_status'] == 'success' else 1
    return exit_code


def run_single_test():
    """Run a quick single test"""
    async def quick_test():
        config = get_development_config()
        tester = WebhookTester(config)
        
        print("Running quick health check...")
        result = await tester.test_webhook_server_startup()
        print(f"Result: {result}")
        
        return result['status'] == 'success'
    
    return asyncio.run(quick_test())


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Webhook Integration Test Suite')
    parser.add_argument('--quick', action='store_true', 
                       help='Run quick health check only')
    parser.add_argument('--host', default='localhost',
                       help='Webhook server host')
    parser.add_argument('--port', type=int, default=8080,
                       help='Webhook server port')
    
    args = parser.parse_args()
    
    if args.quick:
        success = run_single_test()
        print(f"\n{'✓' if success else '✗'} Quick test {'passed' if success else 'failed'}")
        exit(0 if success else 1)
    else:
        exit_code = asyncio.run(main())
        exit(exit_code)