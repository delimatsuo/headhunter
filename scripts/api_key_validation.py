#!/usr/bin/env python3
"""
Simple validation test for Together AI API key configuration
"""

import asyncio
import aiohttp
import os
import sys

# Add cloud_run_worker to path
sys.path.append('cloud_run_worker')

from config import Config

async def test_together_ai_api():
    """Test Together AI API connectivity with the configured API key"""
    try:
        config = Config()
        print("✅ Configuration loaded successfully")
        print(f"   - API key length: {len(config.together_ai_api_key)}")
        print(f"   - Model: {config.together_ai_model}")
        print(f"   - Base URL: {config.together_ai_base_url}")
        
        # Test API call
        headers = {
            'Authorization': f'Bearer {config.together_ai_api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': config.together_ai_model,
            'messages': [{'role': 'user', 'content': 'Say hello in one word.'}],
            'max_tokens': 10,
            'temperature': 0.1
        }
        
        print("🔄 Testing API connectivity...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{config.together_ai_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    message = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    print("✅ API test successful!")
                    print(f"   - Response: {message.strip()}")
                    print(f"   - Status: {response.status}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ API test failed with status {response.status}")
                    print(f"   - Error: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Configuration or API test failed: {e}")
        return False

async def main():
    """Run the validation test"""
    print("🚀 Together AI API Key Validation Test")
    print("=" * 50)
    
    # Set environment variables
    os.environ['GOOGLE_CLOUD_PROJECT'] = 'headhunter-ai-0088'
    
    success = await test_together_ai_api()
    
    if success:
        print("\n🎉 All tests passed! The Cloud Run worker is ready for deployment.")
        return 0
    else:
        print("\n💥 Tests failed! Please check the API key configuration.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)