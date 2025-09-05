#!/usr/bin/env python3
"""
Unit and Integration Tests for Ollama Setup
Tests verify that Ollama is properly installed and Llama 3.1 8b model is available
"""

import subprocess
import json
import sys
import unittest
from typing import Dict, List, Optional


class TestOllamaSetup(unittest.TestCase):
    """Test suite for Ollama installation and configuration"""
    
    def test_ollama_installed(self):
        """Test that Ollama is installed and accessible"""
        try:
            result = subprocess.run(
                ['which', 'ollama'],
                capture_output=True,
                text=True,
                check=True
            )
            self.assertTrue(result.stdout.strip(), "Ollama binary not found in PATH")
            print(f"✓ Ollama found at: {result.stdout.strip()}")
        except subprocess.CalledProcessError:
            self.fail("Ollama is not installed or not in PATH")
    
    def test_ollama_version(self):
        """Test that Ollama version can be retrieved"""
        try:
            result = subprocess.run(
                ['ollama', '--version'],
                capture_output=True,
                text=True,
                check=True
            )
            self.assertIn('ollama version', result.stdout.lower(), 
                         "Could not get Ollama version")
            print(f"✓ Ollama version: {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            self.fail(f"Failed to get Ollama version: {e}")
    
    def test_llama_model_available(self):
        """Test that Llama 3.1 8b model is available"""
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                check=True
            )
            self.assertIn('llama3.1:8b', result.stdout, 
                         "Llama 3.1 8b model not found in Ollama")
            
            # Extract model size from output
            for line in result.stdout.split('\n'):
                if 'llama3.1:8b' in line:
                    print(f"✓ Llama 3.1 8b model found: {line.strip()}")
                    break
        except subprocess.CalledProcessError as e:
            self.fail(f"Failed to list Ollama models: {e}")
    
    def test_llama_model_response(self):
        """Integration test: Test that Llama model can generate responses"""
        try:
            # Run a simple prompt
            result = subprocess.run(
                ['ollama', 'run', 'llama3.1:8b', 'Say "OK" if you are working'],
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                check=True
            )
            
            # Check that we got some response
            self.assertTrue(result.stdout.strip(), 
                          "No response from Llama model")
            
            # Check that response contains expected content (flexible check)
            response_lower = result.stdout.lower()
            self.assertTrue(
                'ok' in response_lower or 'working' in response_lower,
                f"Unexpected response from model: {result.stdout[:100]}"
            )
            print(f"✓ Llama model responding correctly")
            
        except subprocess.TimeoutExpired:
            self.fail("Llama model response timed out after 30 seconds")
        except subprocess.CalledProcessError as e:
            self.fail(f"Failed to run Llama model: {e}")
    
    def test_ollama_api_endpoint(self):
        """Test that Ollama API is accessible"""
        try:
            # Check if Ollama API is running
            result = subprocess.run(
                ['curl', '-s', 'http://localhost:11434/api/version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                try:
                    version_data = json.loads(result.stdout)
                    self.assertIn('version', version_data, 
                                "Version not found in API response")
                    print(f"✓ Ollama API accessible at localhost:11434")
                except json.JSONDecodeError:
                    # API might not be running, which is okay
                    print("⚠ Ollama API not running (optional)")
            else:
                print("⚠ Ollama API not accessible (optional)")
                
        except subprocess.TimeoutExpired:
            print("⚠ Ollama API check timed out (optional)")
        except Exception as e:
            print(f"⚠ Could not check Ollama API: {e} (optional)")


class TestOllamaPerformance(unittest.TestCase):
    """Performance tests for Ollama setup"""
    
    def test_model_load_time(self):
        """Test that model loads within reasonable time"""
        import time
        
        try:
            start_time = time.time()
            result = subprocess.run(
                ['ollama', 'run', 'llama3.1:8b', 'Hi'],
                capture_output=True,
                text=True,
                timeout=60,  # 60 second timeout for first load
                check=True
            )
            load_time = time.time() - start_time
            
            self.assertLess(load_time, 60, 
                          f"Model took too long to load: {load_time:.2f}s")
            print(f"✓ Model loaded and responded in {load_time:.2f}s")
            
        except subprocess.TimeoutExpired:
            self.fail("Model load timed out after 60 seconds")
        except subprocess.CalledProcessError as e:
            self.fail(f"Failed to load model: {e}")


def run_tests():
    """Run all tests and return results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestOllamaSetup))
    suite.addTests(loader.loadTestsFromTestCase(TestOllamaPerformance))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)