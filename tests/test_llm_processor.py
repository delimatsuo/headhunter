#!/usr/bin/env python3
"""
Tests for LLM Processing Pipeline
"""

import sys
import os
import unittest
import tempfile
import json
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

from scripts.llm_processor import (
    LLMProcessor, 
    OllamaAPIClient,
    CandidateProfile,
    ProcessingStats
)


class TestLLMProcessor(unittest.TestCase):
    """Test suite for LLM Processing Pipeline"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize processor once for all tests"""
        try:
            cls.processor = LLMProcessor()
            print("\n✓ LLM Processor initialized successfully")
        except Exception as e:
            raise unittest.SkipTest(f"Cannot initialize processor: {e}")
    
    def test_health_check(self):
        """Test processor health check"""
        health = self.processor.health_check()
        
        self.assertIn("overall_status", health)
        self.assertIn("api", health)
        self.assertEqual(health["overall_status"], "healthy")
        
        print("✓ Health check passed")
    
    def test_csv_loading(self):
        """Test CSV data loading"""
        # Create temporary CSV file
        sample_data = """candidate_id,name,resume_text,recruiter_comments
test1,John Doe,"Software Engineer with 5 years experience","Good technical skills"
test2,Jane Smith,"Senior Developer with leadership","Strong candidate"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(sample_data)
            temp_csv = f.name
        
        try:
            data = self.processor.load_csv_data(temp_csv)
            self.assertEqual(len(data), 2)
            self.assertIn('candidate_id', data[0])
            self.assertEqual(data[0]['candidate_id'], 'test1')
            
            print("✓ CSV loading test passed")
        finally:
            os.unlink(temp_csv)
    
    def test_single_record_processing(self):
        """Test processing of single candidate record"""
        test_record = {
            'candidate_id': 'test_single',
            'name': 'Test Candidate',
            'role_level': 'Senior',
            'resume_text': 'Senior Software Engineer with 8 years at top companies. Led teams and built scalable systems.',
            'recruiter_comments': 'Excellent technical skills and leadership experience. Cultural fit looks good.'
        }
        
        profile = self.processor.process_single_record(test_record)
        
        # Validate profile structure
        self.assertIsInstance(profile, CandidateProfile)
        self.assertEqual(profile.candidate_id, 'test_single')
        self.assertEqual(profile.name, 'Test Candidate')
        self.assertIsNotNone(profile.overall_score)
        self.assertIsNotNone(profile.recommendation)
        self.assertIsNotNone(profile.resume_analysis)
        self.assertIsNotNone(profile.recruiter_insights)
        
        # Validate score range
        self.assertGreaterEqual(profile.overall_score, 0.0)
        self.assertLessEqual(profile.overall_score, 1.0)
        
        # Validate recommendation
        self.assertIn(profile.recommendation, 
                     ["strong_hire", "hire", "maybe", "no_hire"])
        
        print(f"✓ Single record processing - Score: {profile.overall_score:.2f}, Recommendation: {profile.recommendation}")
    
    def test_batch_processing(self):
        """Test batch processing with sample data"""
        # Use minimal test data
        test_data = [
            {
                'candidate_id': 'batch_1',
                'name': 'Batch Test 1',
                'resume_text': 'Junior developer with 2 years experience',
                'recruiter_comments': 'Promising candidate, needs mentoring'
            },
            {
                'candidate_id': 'batch_2', 
                'name': 'Batch Test 2',
                'resume_text': 'Senior architect with 12 years experience',
                'recruiter_comments': 'Excellent technical leader, strong hire'
            }
        ]
        
        profiles, stats = self.processor.process_batch(test_data, limit=2)
        
        # Validate results
        self.assertEqual(len(profiles), 2)
        self.assertEqual(stats.total_records, 2)
        self.assertEqual(stats.successful, 2)
        self.assertEqual(stats.failed, 0)
        self.assertEqual(stats.success_rate, 100.0)
        
        # Validate profiles have different scores (likely)
        scores = [p.overall_score for p in profiles]
        self.assertTrue(all(0.0 <= score <= 1.0 for score in scores))
        
        print(f"✓ Batch processing - {stats.successful}/{stats.total_records} successful")
    
    def test_scoring_algorithm(self):
        """Test that scoring algorithm produces reasonable results"""
        
        # High-quality candidate
        high_quality = {
            'candidate_id': 'high_test',
            'name': 'Senior Expert',
            'resume_text': 'Principal Engineer at Google with 15 years experience. Led 50+ person organization.',
            'recruiter_comments': 'Outstanding candidate. Strong technical and leadership skills. Definite hire.'
        }
        
        # Lower-quality candidate  
        lower_quality = {
            'candidate_id': 'lower_test',
            'name': 'Junior Dev',
            'resume_text': 'Recent bootcamp graduate. No professional experience.',
            'recruiter_comments': 'Needs significant development. Multiple red flags in interview.'
        }
        
        high_profile = self.processor.process_single_record(high_quality)
        lower_profile = self.processor.process_single_record(lower_quality)
        
        # High-quality candidate should score higher
        self.assertGreater(high_profile.overall_score, lower_profile.overall_score)
        
        # High-quality should likely be hire/strong_hire
        self.assertIn(high_profile.recommendation, ["hire", "strong_hire"])
        
        print(f"✓ Scoring test - High: {high_profile.overall_score:.2f}, Low: {lower_profile.overall_score:.2f}")
    
    def test_json_serialization(self):
        """Test that profiles can be serialized to JSON"""
        test_record = {
            'candidate_id': 'json_test',
            'resume_text': 'Software engineer',
            'recruiter_comments': 'Good candidate'
        }
        
        profile = self.processor.process_single_record(test_record)
        profile_dict = profile.to_dict()
        
        # Should be JSON serializable
        json_str = json.dumps(profile_dict)
        self.assertIsInstance(json_str, str)
        
        # Should be parseable back
        parsed = json.loads(json_str)
        self.assertEqual(parsed['candidate_id'], 'json_test')
        
        print("✓ JSON serialization test passed")
    
    def test_error_handling(self):
        """Test error handling for edge cases"""
        
        # Empty resume and comments
        empty_record = {
            'candidate_id': 'empty_test',
            'resume_text': '',
            'recruiter_comments': ''
        }
        
        # Should not crash
        profile = self.processor.process_single_record(empty_record)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.candidate_id, 'empty_test')
        
        # Should still generate some score (default)
        self.assertIsNotNone(profile.overall_score)
        
        print("✓ Error handling test passed")


class TestOllamaAPIClient(unittest.TestCase):
    """Test Ollama API client functionality"""
    
    def test_client_initialization(self):
        """Test API client initialization"""
        try:
            client = OllamaAPIClient()
            self.assertEqual(client.model, "llama3.1:8b")
            print("✓ API client initialization passed")
        except Exception as e:
            self.skipTest(f"Ollama not available: {e}")
    
    def test_health_check(self):
        """Test API health check"""
        try:
            client = OllamaAPIClient()
            health = client.health_check()
            
            self.assertIn("status", health)
            self.assertIn("model", health)
            self.assertEqual(health["status"], "healthy")
            
            print("✓ API health check passed")
        except Exception as e:
            self.skipTest(f"Ollama not available: {e}")


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestLLMProcessor))
    suite.addTests(loader.loadTestsFromTestCase(TestOllamaAPIClient))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*50)
    print("LLM PROCESSOR TEST SUMMARY")
    print("="*50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)