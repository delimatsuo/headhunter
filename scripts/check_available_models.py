#!/usr/bin/env python3
"""
Check available models on Together AI
"""

import asyncio
import aiohttp
import os
import sys

# Add cloud_run_worker to path
sys.path.append('cloud_run_worker')

from config import Config

async def check_available_models():
    """Check what models are available on Together AI"""
    try:
        config = Config()
        
        headers = {
            'Authorization': f'Bearer {config.together_ai_api_key}',
            'Content-Type': 'application/json'
        }
        
        print("🔄 Fetching available models from Together AI...")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{config.together_ai_base_url}/models",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    models = await response.json()
                    
                    print(f"✅ Found {len(models.get('data', []))} models")
                    
                    # Look for Llama models
                    llama_models = [
                        model for model in models.get('data', [])
                        if 'llama' in model.get('id', '').lower()
                    ]
                    
                    print("\n🦙 Available Llama models:")
                    for model in llama_models[:10]:  # Show first 10
                        print(f"   - {model['id']}")
                    
                    # Look for the specific model we want
                    target_models = [
                        model for model in models.get('data', [])
                        if 'meta-llama/llama-3.1-8b-instruct' in model.get('id', '').lower()
                    ]
                    
                    if target_models:
                        print("\n🎯 Found matching Llama 3.1 8B models:")
                        for model in target_models:
                            print(f"   - {model['id']}")
                            
                        # Test with the first one
                        test_model = target_models[0]['id']
                        print(f"\n🧪 Testing with model: {test_model}")
                        
                        await test_model_completion(config, test_model)
                    else:
                        print("\n❌ No Llama 3.1 8B models found")
                        
                else:
                    error_text = await response.text()
                    print(f"❌ Failed to fetch models: {response.status} - {error_text}")
                    
    except Exception as e:
        print(f"❌ Error checking models: {e}")

async def test_model_completion(config, model_id):
    """Test a specific model"""
    try:
        headers = {
            'Authorization': f'Bearer {config.together_ai_api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': model_id,
            'messages': [{'role': 'user', 'content': 'Say hello in one word.'}],
            'max_tokens': 10,
            'temperature': 0.1
        }
        
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
                    print("✅ Model test successful!")
                    print(f"   - Response: {message.strip()}")
                    print(f"   - Recommended model: {model_id}")
                else:
                    error_text = await response.text()
                    print(f"❌ Model test failed: {response.status} - {error_text}")
                    
    except Exception as e:
        print(f"❌ Model test error: {e}")

async def main():
    """Run the model check"""
    print("🔍 Together AI Available Models Check")
    print("=" * 50)
    
    # Set environment variables
    os.environ['GOOGLE_CLOUD_PROJECT'] = 'headhunter-ai-0088'
    
    await check_available_models()

if __name__ == "__main__":
    asyncio.run(main())