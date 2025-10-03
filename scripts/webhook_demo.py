#!/usr/bin/env python3
"""
Webhook Integration Demonstration
Shows how to use the webhook integration system with example data
"""

import json
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add paths for imports
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent / 'config'))

from webhook_config import get_development_config
from cloud_integration import CloudIntegrationContext


def create_example_candidate():
    """Create example candidate data for demonstration"""
    return {
        "candidate_id": "demo_candidate_001",
        "name": "Alice Johnson",
        "resume_text": """
        Alice Johnson
        Senior Software Engineer
        
        EXPERIENCE:
        • Staff Engineer at Meta (2022-2024)
          - Led development of distributed systems handling 1M+ QPS
          - Managed team of 8 engineers across 3 time zones
          - Architected microservices migration reducing latency by 40%
          
        • Senior Engineer at Google (2019-2022)
          - Built machine learning infrastructure for recommendation systems
          - Optimized data pipelines processing 10TB+ daily
          - Mentored 5 junior engineers and interns
          
        • Software Engineer at Stripe (2017-2019)
          - Developed payment processing APIs
          - Implemented fraud detection algorithms
          - Contributed to open source payment libraries
        
        EDUCATION:
        • MS Computer Science, Stanford University (2017)
        • BS Computer Science, UC Berkeley (2015)
        
        SKILLS:
        Technical: Python, Java, Go, Kubernetes, AWS, GCP, PostgreSQL, Redis
        Leadership: Team management, mentoring, technical strategy, hiring
        
        ACHIEVEMENTS:
        • Published 5 papers on distributed systems
        • Led team that reduced infrastructure costs by 30%
        • Architected systems serving 100M+ users daily
        • Regular speaker at tech conferences
        """,
        "recruiter_comments": """
        Exceptional candidate with strong technical background at top-tier companies.
        
        STRENGTHS:
        - Proven track record of leading large-scale systems
        - Excellent technical depth in distributed systems
        - Strong leadership experience managing remote teams
        - Great communication skills demonstrated in interviews
        
        CONCERNS:
        - May be overqualified for some positions
        - Compensation expectations likely very high
        - Previous roles were at very large companies - may need adjustment to smaller scale
        
        INTERVIEW FEEDBACK:
        Technical: 9/10 - Solved complex system design problems with elegant solutions
        Cultural: 8/10 - Great collaboration, asks thoughtful questions
        Leadership: 9/10 - Clear examples of growing teams and technical impact
        
        RECOMMENDATION: Strong hire for Staff+ engineering roles
        """,
        "role_level": "staff",
        "priority": 3  # High priority
    }


async def demonstrate_webhook_system():
    """Demonstrate the webhook integration system"""
    print("🚀 Webhook Integration System Demo")
    print("=" * 50)
    
    # Load configuration
    config = get_development_config()
    print("📋 Configuration loaded:")
    print(f"   Environment: {config.environment.value}")
    print(f"   Ollama Model: {config.ollama.model}")
    print(f"   Server: {config.server.host}:{config.server.port}")
    print(f"   Worker Count: {config.queue.worker_count}")
    
    # Test cloud integration
    print("\n🌐 Testing cloud integration...")
    async with CloudIntegrationContext(config) as integration:
        try:
            # Test connectivity
            connectivity = await integration.test_cloud_connectivity()
            print(f"   Cloud Functions: {connectivity.get('cloud_functions', {}).get('status', 'unknown')}")
            print(f"   Firestore: {connectivity.get('firestore', {}).get('status', 'unknown')}")
            print(f"   Storage: {connectivity.get('storage', {}).get('status', 'unknown')}")
            
            # Show integration stats
            stats = integration.get_integration_stats()
            print(f"   Uptime: {stats['uptime_seconds']:.1f}s")
            print(f"   Success Rate: {stats['success_rate']*100:.1f}%")
            
        except Exception as e:
            print(f"   ⚠️ Cloud integration test failed: {e}")
    
    # Create example candidate
    print("\n👤 Example candidate profile:")
    candidate = create_example_candidate()
    print(f"   ID: {candidate['candidate_id']}")
    print(f"   Name: {candidate['name']}")
    print(f"   Role Level: {candidate['role_level']}")
    print(f"   Priority: {candidate['priority']}")
    print(f"   Resume Length: {len(candidate['resume_text'])} chars")
    print(f"   Comments Length: {len(candidate['recruiter_comments'])} chars")
    
    # Demonstrate webhook request format
    print("\n📡 Example webhook request:")
    webhook_request = {
        "request_id": f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "action": "process_candidate",
        "data": candidate,
        "callback_url": "https://us-central1-headhunter-ai-0088.cloudfunctions.net/receiveAnalysis",
        "timeout": 300,
        "timestamp": datetime.now().isoformat()
    }
    
    print(json.dumps(webhook_request, indent=2))
    
    # Show expected endpoints
    print("\n🔗 System endpoints:")
    local_endpoints = config.get_local_endpoints()
    for name, url in local_endpoints.items():
        print(f"   {name}: {url}")
    
    print("\n🌩️ Cloud endpoints:")
    cloud_endpoints = config.get_cloud_endpoints()
    for name, url in cloud_endpoints.items():
        print(f"   {name}: {url}")
    
    # Show processing pipeline
    print("\n⚙️ Processing pipeline:")
    print("   1. Receive webhook → Local server queue")
    print("   2. Extract text → resume_extractor.py")
    print("   3. Analyze resume → llm_prompts.py + Ollama")
    print("   4. Analyze comments → recruiter_prompts.py + Ollama") 
    print("   5. Validate results → quality_validator.py")
    print("   6. Send to cloud → Cloud Functions")
    print("   7. Store results → Firestore")
    
    # Show example result structure
    print("\n📊 Example processing result:")
    example_result = {
        "candidate_id": candidate["candidate_id"],
        "name": candidate["name"],
        "resume_analysis": {
            "career_trajectory": {
                "current_level": "staff",
                "progression_speed": "fast",
                "years_to_current": 7
            },
            "leadership_scope": {
                "has_leadership": True,
                "team_size_managed": 8,
                "global_experience": True
            },
            "technical_skills": ["Python", "Distributed Systems", "Kubernetes"],
            "years_experience": 9
        },
        "recruiter_insights": {
            "sentiment": "very_positive", 
            "recommendation": "strong_hire",
            "strengths": ["Technical excellence", "Leadership experience"],
            "concerns": ["Overqualification risk"]
        },
        "overall_score": 0.92,
        "recommendation": "strong_hire",
        "processing_timestamp": datetime.now().isoformat()
    }
    
    print(json.dumps(example_result, indent=2))
    
    print("\n✅ Demo completed successfully!")
    print("\nNext steps:")
    print("1. Start webhook server: ./scripts/start_webhook_server.sh start")
    print("2. Run tests: ./scripts/start_webhook_server.sh test")
    print("3. Deploy Cloud Functions with webhook endpoints")
    print("4. Configure Firebase to send webhooks to local server")


def show_quick_start():
    """Show quick start instructions"""
    print("🚀 Webhook Integration Quick Start")
    print("=" * 40)
    
    print("\n1. Prerequisites:")
    print("   brew install ollama")
    print("   ollama pull llama3.1:8b")
    print("   pip install -r scripts/requirements_webhook.txt")
    
    print("\n2. Start the system:")
    print("   ./scripts/start_webhook_server.sh start")
    
    print("\n3. Test the system:")
    print("   ./scripts/start_webhook_server.sh test")
    
    print("\n4. Check status:")
    print("   curl http://localhost:8080/health")
    print("   curl http://localhost:8080/metrics")
    
    print("\n5. Process a candidate:")
    print("   curl -X POST http://localhost:8080/webhook/process-candidate \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d @example_request.json")
    
    print("\nFor detailed documentation, see:")
    print("   docs/WEBHOOK_INTEGRATION.md")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Webhook Integration Demo')
    parser.add_argument('--quick', action='store_true',
                       help='Show quick start guide only')
    
    args = parser.parse_args()
    
    if args.quick:
        show_quick_start()
    else:
        try:
            asyncio.run(demonstrate_webhook_system())
        except KeyboardInterrupt:
            print("\n\n👋 Demo interrupted by user")
        except Exception as e:
            print(f"\n❌ Demo failed: {e}")
            import traceback
            traceback.print_exc()