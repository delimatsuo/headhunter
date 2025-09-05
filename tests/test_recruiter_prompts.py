#!/usr/bin/env python3
"""
Unit and Integration Tests for Recruiter Comment Analysis
Tests the prompt functions and validates insight extraction
"""

import sys
import json
import unittest
from typing import Dict, Any
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.recruiter_prompts import (
    RecruiterCommentAnalyzer,
    RecruiterInsights,
    FeedbackSentiment,
    CandidateReadiness,
    create_feedback_summary
)
from tests.sample_recruiter_comments import get_all_feedback_samples


class TestRecruiterCommentAnalyzer(unittest.TestCase):
    """Test suite for Recruiter Comment Analyzer"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize analyzer once for all tests"""
        try:
            cls.analyzer = RecruiterCommentAnalyzer()
            cls.samples = get_all_feedback_samples()
            print("\n✓ Recruiter analyzer initialized successfully")
        except Exception as e:
            raise unittest.SkipTest(f"Cannot initialize analyzer: {e}")
    
    def test_analyzer_initialization(self):
        """Test that analyzer initializes correctly"""
        self.assertIsNotNone(self.analyzer)
        self.assertEqual(self.analyzer.model, "llama3.1:8b")
        print("✓ Analyzer initialization test passed")
    
    def test_sentiment_analysis(self):
        """Test sentiment analysis for different feedback types"""
        test_cases = [
            ("highly_positive", ["highly_positive", "positive"]),
            ("negative", ["negative", "mixed"]),
            ("mixed", ["mixed", "neutral", "positive"])
        ]
        
        for sample_key, expected_sentiments in test_cases:
            sample = self.samples[sample_key][:1000]  # Use first 1000 chars
            result = self.analyzer.analyze_sentiment(sample)
            
            # Check structure
            self.assertIn("overall_sentiment", result)
            self.assertIn("confidence_level", result)
            self.assertIn("enthusiasm_level", result)
            
            # Validate sentiment is reasonable
            sentiment = result["overall_sentiment"]
            self.assertIn(sentiment, ["highly_positive", "positive", "neutral", "negative", "mixed"],
                         f"Invalid sentiment value: {sentiment}")
            
            print(f"✓ Sentiment analysis for {sample_key}: {sentiment}")
    
    def test_strengths_and_concerns_extraction(self):
        """Test extraction of strengths and concerns"""
        # Test with positive feedback
        sample = self.samples["positive_with_concerns"][:1500]
        result = self.analyzer.extract_strengths_and_concerns(sample)
        
        # Check structure
        self.assertIn("strengths", result)
        self.assertIn("concerns", result)
        self.assertIn("red_flags", result)
        
        # Validate types
        self.assertIsInstance(result["strengths"], list)
        self.assertIsInstance(result["concerns"], list)
        self.assertIsInstance(result["red_flags"], list)
        
        # Should find both strengths and concerns in this sample
        self.assertGreater(len(result["strengths"]), 0, 
                          "Should identify strengths in positive feedback")
        self.assertGreater(len(result["concerns"]), 0,
                          "Should identify concerns in mixed feedback")
        
        print(f"✓ Extracted {len(result['strengths'])} strengths, {len(result['concerns'])} concerns")
    
    def test_leadership_insights(self):
        """Test leadership insight extraction"""
        # Test with leadership-focused feedback
        sample = self.samples["leadership_focused"][:1500]
        result = self.analyzer.identify_leadership_insights(sample)
        
        # Check structure
        required_fields = ["has_leadership_experience", "leadership_style", 
                          "leadership_strengths", "leadership_gaps"]
        for field in required_fields:
            self.assertIn(field, result, f"Missing field: {field}")
        
        # For leadership-focused sample, should detect leadership
        self.assertTrue(result["has_leadership_experience"],
                       "Should detect leadership experience in leadership-focused feedback")
        
        # Should identify some leadership strengths
        self.assertIsInstance(result["leadership_strengths"], list)
        self.assertGreater(len(result["leadership_strengths"]), 0,
                          "Should identify leadership strengths")
        
        print(f"✓ Leadership insights: {result['leadership_style']} style detected")
    
    def test_cultural_fit_assessment(self):
        """Test cultural fit assessment"""
        sample = self.samples["culture_fit"][:1500]
        result = self.analyzer.assess_cultural_fit(sample)
        
        # Check structure
        self.assertIn("cultural_alignment", result)
        self.assertIn("work_style", result)
        self.assertIn("team_fit", result)
        
        # Validate cultural alignment value
        self.assertIn(result["cultural_alignment"], 
                     ["strong", "moderate", "weak", "unclear"])
        
        # Work style should be a list
        self.assertIsInstance(result["work_style"], list)
        
        # Culture-focused sample should show strong alignment
        self.assertIn(result["cultural_alignment"], ["strong", "moderate"],
                     "Culture-fit sample should show positive alignment")
        
        print(f"✓ Cultural fit: {result['cultural_alignment']} alignment")
    
    def test_key_themes_extraction(self):
        """Test extraction of recurring themes"""
        sample = self.samples["mixed"][:1500]
        result = self.analyzer.extract_key_themes(sample)
        
        # Should return a list of themes
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0, "Should identify at least one theme")
        self.assertLessEqual(len(result), 7, "Should not exceed 7 themes")
        
        # Each theme should be a string
        for theme in result:
            self.assertIsInstance(theme, str)
            self.assertGreater(len(theme), 0, "Theme should not be empty")
        
        print(f"✓ Identified {len(result)} key themes")
    
    def test_readiness_assessment(self):
        """Test candidate readiness assessment"""
        sample = self.samples["junior"][:1500]
        result = self.analyzer.assess_readiness(sample, "Junior Developer")
        
        # Check structure
        self.assertIn("readiness_level", result)
        self.assertIn("confidence_score", result)
        self.assertIn("development_needs", result)
        
        # Validate readiness level
        self.assertIn(result["readiness_level"],
                     ["ready_now", "needs_development", "not_ready", "overqualified"])
        
        # Confidence should be between 0 and 1
        self.assertGreaterEqual(result["confidence_score"], 0.0)
        self.assertLessEqual(result["confidence_score"], 1.0)
        
        print(f"✓ Readiness: {result['readiness_level']} (confidence: {result['confidence_score']:.2f})")
    
    def test_competitive_advantages(self):
        """Test identification of competitive advantages"""
        sample = self.samples["highly_positive"][:1500]
        result = self.analyzer.identify_competitive_advantages(sample)
        
        # Should return a list
        self.assertIsInstance(result, list)
        
        # Highly positive feedback should have advantages
        self.assertGreater(len(result), 0,
                          "Should identify advantages in highly positive feedback")
        
        print(f"✓ Found {len(result)} competitive advantages")
    
    def test_recommendation_generation(self):
        """Test hiring recommendation generation"""
        test_cases = [
            ("highly_positive", ["strong_hire", "hire"]),
            ("negative", ["no_hire", "maybe"]),
            ("mixed", ["maybe", "hire", "no_hire"])
        ]
        
        for sample_key, expected_recommendations in test_cases:
            sample = self.samples[sample_key][:1500]
            result = self.analyzer.generate_recommendation(sample)
            
            # Check structure
            self.assertIn("recommendation", result)
            self.assertIn("confidence", result)
            self.assertIn("rationale", result)
            
            # Validate recommendation
            self.assertIn(result["recommendation"],
                         ["strong_hire", "hire", "maybe", "no_hire"])
            
            print(f"✓ Recommendation for {sample_key}: {result['recommendation']}")
    
    def test_json_output_validation(self):
        """Test that all outputs are valid JSON"""
        sample = self.samples["mixed"][:1000]
        
        # Test each analysis function returns valid JSON-serializable data
        functions = [
            self.analyzer.analyze_sentiment,
            self.analyzer.extract_strengths_and_concerns,
            self.analyzer.identify_leadership_insights,
            self.analyzer.assess_cultural_fit,
            self.analyzer.extract_key_themes,
            lambda s: self.analyzer.assess_readiness(s, "Senior"),
            self.analyzer.identify_competitive_advantages,
            self.analyzer.generate_recommendation
        ]
        
        for func in functions:
            result = func(sample)
            # Should be able to serialize to JSON
            json_str = json.dumps(result)
            self.assertIsInstance(json_str, str)
            # Should be able to parse back
            parsed = json.loads(json_str)
            self.assertIsNotNone(parsed)
        
        print("✓ All functions return valid JSON")


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for complete feedback analysis workflow"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize analyzer for integration tests"""
        try:
            cls.analyzer = RecruiterCommentAnalyzer()
            cls.samples = get_all_feedback_samples()
        except Exception as e:
            raise unittest.SkipTest(f"Cannot initialize analyzer: {e}")
    
    def test_full_feedback_analysis(self):
        """Test complete feedback analysis workflow"""
        sample = self.samples["positive_with_concerns"][:2000]
        
        try:
            insights = self.analyzer.analyze_full_feedback(sample, "Senior Engineer")
            
            # Verify RecruiterInsights structure
            self.assertIsInstance(insights, RecruiterInsights)
            self.assertIsInstance(insights.sentiment, str)
            self.assertIsInstance(insights.strengths, list)
            self.assertIsInstance(insights.concerns, list)
            self.assertIsInstance(insights.recommendation, str)
            
            # Should have extracted meaningful insights
            self.assertGreater(len(insights.strengths), 0)
            self.assertGreater(len(insights.key_themes), 0)
            
            print(f"✓ Full analysis completed - Recommendation: {insights.recommendation}")
            
        except Exception as e:
            self.fail(f"Full analysis failed: {e}")
    
    def test_feedback_summary_generation(self):
        """Test human-readable summary generation"""
        sample = self.samples["leadership_focused"][:2000]
        
        insights = self.analyzer.analyze_full_feedback(sample)
        summary = create_feedback_summary(insights)
        
        # Summary should be a non-empty string
        self.assertIsInstance(summary, str)
        self.assertGreater(len(summary), 50, "Summary should be substantive")
        
        # Should contain key elements
        self.assertIn("Sentiment:", summary)
        self.assertIn("Recommendation:", summary)
        
        print("✓ Generated human-readable summary")
    
    def test_different_feedback_types(self):
        """Test analyzer handles different feedback types appropriately"""
        test_cases = [
            ("highly_positive", "positive", ["strong_hire", "hire"]),
            ("negative", "negative", ["no_hire", "maybe"]),
            ("junior", ["positive", "neutral"], ["hire", "maybe"])
        ]
        
        for sample_key, expected_sentiment, expected_recommendations in test_cases:
            sample = self.samples[sample_key][:1500]
            insights = self.analyzer.analyze_full_feedback(sample)
            
            # Check sentiment alignment
            if isinstance(expected_sentiment, list):
                self.assertIn(insights.sentiment, expected_sentiment)
            else:
                self.assertIn(expected_sentiment, insights.sentiment)
            
            # Check recommendation alignment
            self.assertIn(insights.recommendation, expected_recommendations)
            
            print(f"✓ {sample_key} analyzed correctly")


def run_all_tests():
    """Run all test suites and report results"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRecruiterCommentAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationScenarios))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*50)
    print("RECRUITER PROMPTS TEST SUMMARY")
    print("="*50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)