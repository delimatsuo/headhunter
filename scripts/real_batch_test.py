#!/usr/bin/env python3
"""
Real 50-candidate batch test using actual Together AI API
"""

import asyncio
import aiohttp
import json
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any

# Add cloud_run_worker to path
sys.path.append('cloud_run_worker')
from config import Config

async def test_single_candidate(config: Config, candidate_data: Dict[str, Any]) -> Dict[str, Any]:
    """Test processing a single candidate with Together AI"""
    try:
        headers = {
            'Authorization': f'Bearer {config.together_ai_api_key}',
            'Content-Type': 'application/json'
        }
        
        # Create a realistic prompt for candidate processing
        prompt = f"""
Analyze this candidate profile and return JSON with career insights:

Candidate: {candidate_data['name']}
Experience: {candidate_data['experience']} years
Skills: {', '.join(candidate_data['skills'][:3])}
Previous Companies: {', '.join(candidate_data['companies'][:2])}

Return JSON with these fields:
{{
  "career_level": "junior|mid|senior|executive",
  "leadership_potential": "low|medium|high",
  "technical_depth": "basic|intermediate|advanced|expert",
  "cultural_fit_score": 0.0-1.0,
  "key_strengths": ["strength1", "strength2"],
  "overall_rating": 1-100
}}
"""
        
        payload = {
            'model': config.together_ai_model,
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 300,
            'temperature': 0.1
        }
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{config.together_ai_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                processing_time = time.time() - start_time
                
                if response.status == 200:
                    result = await response.json()
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    
                    return {
                        'candidate_id': candidate_data['id'],
                        'success': True,
                        'processing_time': processing_time,
                        'response': content[:200] + "..." if len(content) > 200 else content,
                        'status_code': response.status,
                        'tokens_used': result.get('usage', {}).get('total_tokens', 0)
                    }
                else:
                    error_text = await response.text()
                    return {
                        'candidate_id': candidate_data['id'],
                        'success': False,
                        'processing_time': processing_time,
                        'error': f"HTTP {response.status}: {error_text[:100]}",
                        'status_code': response.status
                    }
                    
    except Exception as e:
        return {
            'candidate_id': candidate_data['id'],
            'success': False,
            'processing_time': time.time() - start_time if 'start_time' in locals() else 0,
            'error': str(e)[:100],
            'status_code': 0
        }

def generate_test_candidates(num_candidates: int = 50) -> List[Dict[str, Any]]:
    """Generate realistic test candidate data"""
    skills_pool = [
        "Python", "JavaScript", "Java", "C++", "React", "Node.js", "AWS", "Docker",
        "Kubernetes", "Machine Learning", "Data Science", "SQL", "MongoDB", "Redis",
        "GraphQL", "TypeScript", "Vue.js", "Angular", "Spring Boot", "Django"
    ]
    
    companies_pool = [
        "Google", "Microsoft", "Amazon", "Meta", "Apple", "Netflix", "Uber", "Airbnb",
        "Spotify", "Slack", "Dropbox", "GitHub", "Atlassian", "Salesforce", "Oracle",
        "IBM", "Intel", "NVIDIA", "Tesla", "SpaceX"
    ]
    
    candidates = []
    for i in range(num_candidates):
        candidates.append({
            'id': f'candidate_{i+1:03d}',
            'name': f'Test Candidate {i+1}',
            'experience': (i % 15) + 1,  # 1-15 years experience
            'skills': skills_pool[i*3:(i*3)+5] if i*3 < len(skills_pool) else skills_pool[:5],
            'companies': companies_pool[i*2:(i*2)+3] if i*2 < len(companies_pool) else companies_pool[:3]
        })
    
    return candidates

async def run_batch_test(num_candidates: int = 50) -> Dict[str, Any]:
    """Run the actual 50-candidate batch test"""
    print("🚀 Starting REAL 50-Candidate Batch Test with Together AI")
    print("=" * 60)
    
    # Set up configuration
    os.environ['GOOGLE_CLOUD_PROJECT'] = 'headhunter-ai-0088'
    config = Config()
    
    print("✅ Configuration loaded:")
    print(f"   - Model: {config.together_ai_model}")
    print(f"   - API Key: {'*' * 60}{config.together_ai_api_key[-4:]}")
    print(f"   - Base URL: {config.together_ai_base_url}")
    
    # Generate test candidates
    candidates = generate_test_candidates(num_candidates)
    print(f"✅ Generated {len(candidates)} test candidates")
    
    # Process candidates
    print("🔄 Processing candidates...")
    start_time = time.time()
    
    results = []
    for i, candidate in enumerate(candidates):
        print(f"   Processing candidate {i+1}/{len(candidates)}... ", end="", flush=True)
        
        result = await test_single_candidate(config, candidate)
        results.append(result)
        
        if result['success']:
            print(f"✅ {result['processing_time']:.2f}s")
        else:
            print(f"❌ {result['error'][:30]}")
        
        # Small delay to be respectful to the API
        await asyncio.sleep(0.1)
    
    total_time = time.time() - start_time
    
    # Analyze results
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    success_rate = len(successful) / len(results) * 100
    avg_processing_time = sum(r['processing_time'] for r in successful) / len(successful) if successful else 0
    total_tokens = sum(r.get('tokens_used', 0) for r in successful)
    
    # Estimate cost (Together AI pricing)
    estimated_cost = total_tokens * 0.00001  # Rough estimate
    
    summary = {
        'test_info': {
            'timestamp': datetime.now().isoformat(),
            'total_candidates': len(candidates),
            'model': config.together_ai_model
        },
        'performance': {
            'success_rate': success_rate,
            'successful_candidates': len(successful),
            'failed_candidates': len(failed),
            'avg_processing_time': avg_processing_time,
            'total_processing_time': total_time,
            'throughput_per_minute': len(successful) / (total_time / 60) if total_time > 0 else 0
        },
        'cost': {
            'total_tokens': total_tokens,
            'estimated_cost': estimated_cost,
            'cost_per_candidate': estimated_cost / len(successful) if successful else 0
        },
        'detailed_results': results
    }
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 BATCH TEST RESULTS")
    print("=" * 60)
    print(f"✅ Success Rate: {success_rate:.1f}% ({len(successful)}/{len(results)})")
    print(f"⏱️  Average Processing Time: {avg_processing_time:.2f}s")
    print(f"🚀 Throughput: {summary['performance']['throughput_per_minute']:.1f} candidates/minute")
    print(f"💰 Total Cost: ${estimated_cost:.4f}")
    print(f"💰 Cost per Candidate: ${summary['cost']['cost_per_candidate']:.4f}")
    print(f"🔤 Total Tokens Used: {total_tokens:,}")
    
    if failed:
        print(f"\n❌ Failed Candidates: {len(failed)}")
        for failure in failed[:3]:  # Show first 3 failures
            print(f"   - {failure['candidate_id']}: {failure['error'][:50]}")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"scripts/real_batch_test_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n💾 Results saved to: {results_file}")
    
    return summary

async def main():
    """Main execution function"""
    try:
        results = await run_batch_test(50)
        
        # Success criteria
        if results['performance']['success_rate'] >= 95:
            print("\n🎉 BATCH TEST PASSED - System ready for production!")
            return 0
        else:
            print("\n⚠️  BATCH TEST WARNING - Success rate below 95%")
            return 1
            
    except Exception as e:
        print(f"\n💥 BATCH TEST FAILED: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)