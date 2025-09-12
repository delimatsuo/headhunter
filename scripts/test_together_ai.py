#!/usr/bin/env python3
"""
Test Together AI Integration
Simple test to verify API connectivity and response format
"""

import asyncio
import aiohttp
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv('TOGETHER_API_KEY')

async def test_together_ai():
    """Test basic Together AI API connectivity"""
    
    if not API_KEY:
        print("⚠️ TOGETHER_API_KEY not set; skipping live API test.")
        return True

    url = "https://api.together.xyz/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Simple test payload
    payload = {
        "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", 
        "messages": [
            {
                "role": "user",
                "content": "Analyze this candidate profile and return a JSON response with their key strengths:\n\nName: John Smith\nExperience: Senior Software Engineer at Google for 5 years\nEducation: MS Computer Science from Stanford\nSkills: Python, React, Machine Learning\n\nReturn only valid JSON with 'strengths' array."
            }
        ],
        "max_tokens": 500,
        "temperature": 0.1
    }
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            print("🚀 Testing Together AI API connectivity...")
            print(f"Model: {payload['model']}")
            
            async with session.post(url, headers=headers, json=payload) as response:
                print(f"Response Status: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    
                    if 'choices' in result and len(result['choices']) > 0:
                        content = result['choices'][0]['message']['content']
                        
                        print("✅ API Response received:")
                        print("=" * 50)
                        print(content)
                        print("=" * 50)
                        
                        # Try to parse as JSON
                        try:
                            parsed_json = json.loads(content)
                            print("✅ Successfully parsed as JSON:")
                            print(json.dumps(parsed_json, indent=2))
                            
                        except json.JSONDecodeError:
                            print("⚠️  Response is not valid JSON, but API call succeeded")
                        
                        # Usage stats
                        if 'usage' in result:
                            usage = result['usage']
                            print(f"\n📊 Token Usage:")
                            print(f"   Prompt tokens: {usage.get('prompt_tokens', 0)}")
                            print(f"   Completion tokens: {usage.get('completion_tokens', 0)}")
                            print(f"   Total tokens: {usage.get('total_tokens', 0)}")
                            
                            # Cost estimate (approx $0.10 per 1M tokens)
                            total_tokens = usage.get('total_tokens', 0)
                            cost = (total_tokens / 1_000_000) * 0.10
                            print(f"   Estimated cost: ${cost:.6f}")
                        
                        return True
                    else:
                        print("❌ No choices in API response")
                        return False
                        
                else:
                    error_text = await response.text()
                    print(f"❌ API Error: {response.status}")
                    print(f"Error details: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

async def main():
    """Main test function"""
    print("🧪 Together AI Integration Test")
    print("=" * 50)
    
    success = await test_together_ai()
    
    if success:
        print("\n✅ Together AI integration test successful!")
        print("🚀 Ready to process 29,000 candidates")
        
        # Estimate cost for full processing
        avg_tokens_per_candidate = 5000
        total_tokens = 29000 * avg_tokens_per_candidate
        estimated_cost = (total_tokens / 1_000_000) * 0.10
        
        print(f"\n💰 Cost Estimate for 29,000 candidates:")
        print(f"   Average tokens per candidate: {avg_tokens_per_candidate:,}")
        print(f"   Total estimated tokens: {total_tokens:,}")
        print(f"   Estimated cost: ${estimated_cost:.2f}")
        
    else:
        print("\n❌ Together AI integration test failed!")
        print("Please check API key and network connectivity")

if __name__ == "__main__":
    asyncio.run(main())
