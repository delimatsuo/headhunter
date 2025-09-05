#!/usr/bin/env python3
"""
Unit and Integration Tests for LLM Resume Analysis Prompts
Tests the prompt functions and validates JSON output structure
"""

import sys
import json
import unittest
from typing import Dict, Any
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.llm_prompts import (
    ResumeAnalyzer, 
    ResumeAnalysis,
    CareerLevel,
    CompanyTier
)
from tests.sample_resumes import get_all_samples


class TestResumeAnalyzer(unittest.TestCase):
    """Test suite for Resume Analyzer functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize analyzer once for all tests"""
        try:
            cls.analyzer = ResumeAnalyzer()
            cls.samples = get_all_samples()
            print("\n✓ Analyzer initialized successfully")
        except Exception as e:
            raise unittest.SkipTest(f"Cannot initialize analyzer: {e}")
    
    def test_analyzer_initialization(self):
        """Test that analyzer initializes correctly"""
        self.assertIsNotNone(self.analyzer)
        self.assertEqual(self.analyzer.model, "llama3.1:8b")
        print("✓ Analyzer initialization test passed")
    
    def test_career_trajectory_analysis(self):
        """Test career trajectory analysis returns valid JSON structure"""
        # Use a shorter sample for testing
        sample = self.samples["mid_level"][:1000]  # Use first 1000 chars
        
        result = self.analyzer.analyze_career_trajectory(sample)
        
        # Check required fields exist
        self.assertIn("current_level", result)
        self.assertIn("progression_speed", result)
        self.assertIn("career_highlights", result)
        
        # Validate field types
        self.assertIsInstance(result["career_highlights"], list)
        self.assertIn(result["current_level"], 
                     ["entry", "mid", "senior", "lead", "executive"])
        
        print(f"✓ Career trajectory analysis passed - Level: {result['current_level']}")
    
    def test_leadership_scope_analysis(self):
        """Test leadership analysis returns valid structure"""
        sample = self.samples["executive"][:1500]  # Executive should have leadership
        
        result = self.analyzer.analyze_leadership_scope(sample)
        
        # Check required fields
        self.assertIn("has_leadership", result)
        self.assertIn("leadership_roles", result)
        
        # Validate types
        self.assertIsInstance(result["has_leadership"], bool)
        self.assertIsInstance(result["leadership_roles"], list)
        
        # Executive sample should have leadership
        self.assertTrue(result["has_leadership"], 
                       "Executive resume should show leadership experience")
        
        print(f"✓ Leadership analysis passed - Has leadership: {result['has_leadership']}")
    
    def test_company_pedigree_analysis(self):
        """Test company pedigree extraction"""
        sample = self.samples["executive"][:2000]
        
        result = self.analyzer.analyze_company_pedigree(sample)
        
        # Should return a list
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0, "Should identify at least one company")
        
        # Check first company structure
        if result:
            company = result[0]
            self.assertIn("company_name", company)
            self.assertIn("tier", company)
            
            # Verify tier is valid
            valid_tiers = ["startup", "growth", "enterprise", "faang", "fortune500"]
            self.assertIn(company["tier"], valid_tiers)
        
        print(f"✓ Company pedigree analysis passed - Found {len(result)} companies")
    
    def test_skills_extraction(self):
        """Test technical and soft skills extraction"""
        sample = self.samples["mid_level"][:1500]
        
        result = self.analyzer.extract_skills(sample)
        
        # Check structure
        self.assertIn("technical_skills", result)
        self.assertIn("soft_skills", result)
        
        # Validate types
        self.assertIsInstance(result["technical_skills"], list)
        self.assertIsInstance(result["soft_skills"], list)
        
        # Should find some skills
        self.assertGreater(len(result["technical_skills"]), 0, 
                          "Should identify technical skills")
        
        print(f"✓ Skills extraction passed - Found {len(result['technical_skills'])} technical skills")
    
    def test_cultural_signals_identification(self):
        """Test cultural signals identification"""
        sample = self.samples["startup_founder"][:1500]
        
        result = self.analyzer.identify_cultural_signals(sample)
        
        # Should return a list of strings
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0, "Should identify cultural signals")
        
        if result:
            self.assertIsInstance(result[0], str)
        
        print(f"✓ Cultural signals passed - Found {len(result)} signals")
    
    def test_json_output_validation(self):
        """Test that all outputs are valid JSON"""
        sample = self.samples["entry_level"][:1000]
        
        # Test each analysis function
        functions = [
            (self.analyzer.analyze_career_trajectory, dict),
            (self.analyzer.analyze_leadership_scope, dict),
            (self.analyzer.analyze_company_pedigree, list),
            (self.analyzer.extract_skills, dict),
            (self.analyzer.identify_cultural_signals, list)
        ]
        
        for func, expected_type in functions:
            result = func(sample)
            self.assertIsInstance(result, expected_type, 
                                f"{func.__name__} should return {expected_type}")
            
            # Verify it can be serialized back to JSON
            json_str = json.dumps(result)
            self.assertIsInstance(json_str, str)
        
        print("✓ All functions return valid JSON")
    
    def test_different_career_levels(self):
        """Test analyzer handles different career levels appropriately"""
        test_cases = [
            ("entry_level", ["entry", "mid"]),
            ("mid_level", ["mid", "senior"]),
            ("executive", ["lead", "executive"])
        ]
        
        for sample_key, expected_levels in test_cases:
            sample = self.samples[sample_key][:1000]
            result = self.analyzer.analyze_career_trajectory(sample)
            
            self.assertIn(result["current_level"], expected_levels,
                         f"{sample_key} should be classified as {expected_levels}")
            
            print(f"✓ {sample_key} correctly identified as {result['current_level']}")
    
    def test_error_handling(self):
        """Test analyzer handles edge cases gracefully"""
        # Test with empty resume
        empty_resume = ""
        
        # Should not crash, but return some structure
        try:
            result = self.analyzer.analyze_career_trajectory(empty_resume)
            self.assertIsInstance(result, dict)
        except Exception as e:
            # It's okay if it raises an exception for empty input
            self.assertIn("parse", str(e).lower())
        
        # Test with very short resume
        short_resume = "John Doe, Software Engineer"
        try:
            result = self.analyzer.analyze_career_trajectory(short_resume)
            self.assertIsInstance(result, dict)
            print("✓ Handles edge cases gracefully")
        except Exception as e:
            print(f"⚠ Edge case handling could be improved: {e}")


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for complete resume analysis workflow"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize analyzer for integration tests"""
        try:
            cls.analyzer = ResumeAnalyzer()
            cls.samples = get_all_samples()
        except Exception as e:
            raise unittest.SkipTest(f"Cannot initialize analyzer: {e}")
    
    def test_full_resume_analysis(self):
        """Test complete resume analysis workflow"""
        # Use a complete but shorter sample
        sample = self.samples["mid_level"][:2000]
        
        try:
            analysis = self.analyzer.analyze_full_resume(sample)
            
            # Verify ResumeAnalysis structure
            self.assertIsInstance(analysis, ResumeAnalysis)
            self.assertIsInstance(analysis.career_trajectory, dict)
            self.assertIsInstance(analysis.leadership_scope, dict)
            self.assertIsInstance(analysis.company_pedigree, list)
            self.assertIsInstance(analysis.technical_skills, list)
            self.assertIsInstance(analysis.cultural_signals, list)
            
            # Verify we got meaningful data
            self.assertGreater(len(analysis.technical_skills), 0)
            self.assertGreater(analysis.years_experience, 0)
            
            print(f"✓ Full analysis completed - {analysis.years_experience} years experience")
            
        except Exception as e:
            self.fail(f"Full analysis failed: {e}")
    
    def test_analysis_consistency(self):
        """Test that multiple analyses of same resume are consistent"""
        sample = self.samples["executive"][:1000]
        
        # Run analysis twice
        result1 = self.analyzer.analyze_career_trajectory(sample)
        result2 = self.analyzer.analyze_career_trajectory(sample)
        
        # Key fields should be the same
        self.assertEqual(result1["current_level"], result2["current_level"],
                        "Career level should be consistent across analyses")
        
        print("✓ Analysis consistency verified")


def run_all_tests():
    """Run all test suites and report results"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestResumeAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationScenarios))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*50)
    print("LLM PROMPTS TEST SUMMARY")
    print("="*50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)