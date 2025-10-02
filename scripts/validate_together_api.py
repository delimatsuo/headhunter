#!/usr/bin/env python3
"""
Validate Together API connectivity and configuration.
Tests API key, model availability, and basic completion requests.
"""

import os
import sys
import json
import time
from typing import Dict, Any, Optional

try:
    import requests
except ImportError:
    print("Error: requests library not installed")
    print("Install with: pip install requests")
    sys.exit(1)


def test_together_api(api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Test Together API connectivity and functionality.

    Args:
        api_key: Together API key (uses env var if not provided)

    Returns:
        Dict with test results
    """
    results = {
        "api_key_present": False,
        "api_reachable": False,
        "model_available": False,
        "completion_works": False,
        "latency_ms": None,
        "error": None
    }

    # Check API key
    if not api_key:
        api_key = os.environ.get("TOGETHER_API_KEY", "")

    if not api_key:
        results["error"] = "No API key found. Set TOGETHER_API_KEY environment variable."
        return results

    results["api_key_present"] = True

    # Test API endpoint
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Check model availability
    model = "meta-llama/Llama-3.1-8B-Instruct-Turbo"

    try:
        # Test with a simple completion
        url = "https://api.together.xyz/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a recruitment assistant. Reply with exactly: OK"
                },
                {
                    "role": "user",
                    "content": "Test message"
                }
            ],
            "max_tokens": 10,
            "temperature": 0.1
        }

        start_time = time.time()
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        latency = (time.time() - start_time) * 1000
        results["latency_ms"] = round(latency, 2)

        if response.status_code == 200:
            results["api_reachable"] = True
            results["model_available"] = True
            results["completion_works"] = True

            # Parse response
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                if "OK" not in content.upper():
                    results["error"] = f"Unexpected response: {content}"
        elif response.status_code == 401:
            results["api_reachable"] = True
            results["error"] = "Invalid API key"
        elif response.status_code == 404:
            results["api_reachable"] = True
            results["error"] = f"Model {model} not found"
        else:
            results["api_reachable"] = True
            results["error"] = f"API error: {response.status_code} - {response.text}"

    except requests.exceptions.Timeout:
        results["error"] = "Request timeout (30s)"
    except requests.exceptions.ConnectionError:
        results["error"] = "Cannot connect to Together API"
    except Exception as e:
        results["error"] = str(e)

    return results


def test_recruiter_prompt(api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Test a realistic recruiter-style prompt for profile analysis.

    Args:
        api_key: Together API key

    Returns:
        Dict with test results
    """
    results = {
        "profile_analysis_works": False,
        "response_time_ms": None,
        "response_quality": None,
        "error": None
    }

    if not api_key:
        api_key = os.environ.get("TOGETHER_API_KEY", "")

    if not api_key:
        results["error"] = "No API key"
        return results

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Realistic recruiter prompt
    prompt = """Analyze this candidate profile and return JSON:

    Candidate: Senior Software Engineer
    Experience: 10 years in fintech, led teams of 5-8 engineers
    Skills: Python, AWS, microservices, ML
    Education: MS Computer Science from Stanford

    Return JSON with: role_fit (string), years_experience (int), leadership_level (string)"""

    payload = {
        "model": "meta-llama/Llama-3.1-8B-Instruct-Turbo",
        "messages": [
            {"role": "system", "content": "You are a recruitment AI. Always respond with valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 200,
        "temperature": 0.3
    }

    try:
        start_time = time.time()
        response = requests.post(
            "https://api.together.xyz/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response_time = (time.time() - start_time) * 1000
        results["response_time_ms"] = round(response_time, 2)

        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]

                # Try to parse as JSON
                try:
                    # Extract JSON from response (might have markdown)
                    if "```json" in content:
                        json_str = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        json_str = content.split("```")[1].split("```")[0].strip()
                    else:
                        json_str = content.strip()

                    parsed = json.loads(json_str)

                    # Check expected fields
                    if all(k in parsed for k in ["role_fit", "years_experience", "leadership_level"]):
                        results["profile_analysis_works"] = True
                        results["response_quality"] = "good"
                    else:
                        results["response_quality"] = "missing_fields"
                        results["error"] = f"Missing expected fields: {list(parsed.keys())}"
                except json.JSONDecodeError:
                    results["response_quality"] = "invalid_json"
                    results["error"] = f"Invalid JSON response: {content[:200]}"
        else:
            results["error"] = f"API error: {response.status_code}"

    except Exception as e:
        results["error"] = str(e)

    return results


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("Together API Validation Test")
    print("=" * 60)
    print()

    # Get API key from environment or command line
    api_key = os.environ.get("TOGETHER_API_KEY")

    if len(sys.argv) > 1 and sys.argv[1].startswith("--api-key="):
        api_key = sys.argv[1].split("=", 1)[1]

    # Run basic connectivity test
    print("1. Testing API Connectivity...")
    print("-" * 30)

    basic_results = test_together_api(api_key)

    for key, value in basic_results.items():
        if key != "error" or value:
            status = "✅" if value and key != "error" else "❌"
            if key == "latency_ms" and value:
                print(f"   {key}: {value}ms")
            elif key != "error":
                print(f"   {status} {key}: {value}")

    if basic_results.get("error"):
        print(f"   ❌ Error: {basic_results['error']}")
        print()
        print("Fix the issue above before proceeding.")
        sys.exit(1)

    print()

    # Run recruiter prompt test
    print("2. Testing Recruiter-Style Prompt...")
    print("-" * 30)

    prompt_results = test_recruiter_prompt(api_key)

    for key, value in prompt_results.items():
        if key != "error" or value:
            if key == "response_time_ms" and value:
                print(f"   Response time: {value}ms")
            elif key == "response_quality":
                status = "✅" if value == "good" else "⚠️"
                print(f"   {status} Response quality: {value}")
            elif key == "profile_analysis_works":
                status = "✅" if value else "❌"
                print(f"   {status} Profile analysis: {'working' if value else 'failed'}")

    if prompt_results.get("error"):
        print(f"   ⚠️  Issue: {prompt_results['error']}")

    print()
    print("=" * 60)

    # Summary
    all_passed = (
        basic_results["completion_works"] and
        prompt_results["profile_analysis_works"]
    )

    if all_passed:
        print("✅ All tests passed! Together API is ready for use.")
        print()
        print("Configuration:")
        print(f"  Model: meta-llama/Llama-3.1-8B-Instruct-Turbo")
        print(f"  Latency: {basic_results['latency_ms']}ms")
        print(f"  Profile Analysis: {prompt_results['response_time_ms']}ms")
    else:
        print("❌ Some tests failed. Review the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()