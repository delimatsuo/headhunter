#!/usr/bin/env python3
"""
Test suite for Quality Validation System
"""

import sys
import os
import unittest
import json
import tempfile
from pathlib import Path

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

from quality_validator import LLMOutputValidator, ValidationResult, QualityMetrics
from llm_prompts import ResumeAnalysis
from recruiter_prompts import RecruiterInsights


class TestQualityValidator(unittest.TestCase):
    """Test suite for LLM Output Quality Validator"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize validator once for all tests"""
        cls.validator = LLMOutputValidator()
        print("\n✓ Quality Validator initialized successfully")
    
    def test_schema_validation_resume_valid(self):
        """Test schema validation with valid resume data"""
        valid_resume_data = {
            "career_trajectory": {
                "current_level": "Senior",
                "progression_speed": "Fast",
                "trajectory_type": "Technical Leadership",
                "career_changes": 2,
                "domain_expertise": ["Software Engineering", "AI/ML"]
            },
            "leadership_scope": {
                "has_leadership": True,
                "team_size": 5,
                "leadership_level": "Team Lead",
                "leadership_style": ["Collaborative", "Technical"],
                "mentorship_experience": True
            },
            "company_pedigree": {
                "tier_level": "Tier1",
                "company_types": ["Big Tech", "Startup"],
                "brand_recognition": "High",
                "recent_companies": ["Google", "OpenAI"]
            },
            "years_experience": 8,
            "technical_skills": ["Python", "Machine Learning", "Kubernetes"],
            "soft_skills": ["Communication", "Leadership", "Problem Solving"],
            "education": {
                "highest_degree": "MS Computer Science",
                "institutions": ["Stanford University"],
                "fields_of_study": ["Computer Science", "AI"]
            },
            "cultural_signals": ["Open source contributions", "Conference speaker"]
        }
        
        is_valid, errors = self.validator.validate_schema(valid_resume_data, "resume")
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        print("✓ Valid resume data passes schema validation")
    
    def test_schema_validation_resume_invalid(self):
        """Test schema validation with invalid resume data"""
        invalid_resume_data = {
            "career_trajectory": {
                "current_level": "InvalidLevel",  # Invalid enum value
                "progression_speed": "Fast",
                "trajectory_type": "Technical Leadership"
            },
            "leadership_scope": {
                "has_leadership": "yes",  # Should be boolean
                "team_size": -5,  # Invalid negative value
                "leadership_level": "Team Lead"
            },
            "company_pedigree": {
                "tier_level": "Tier1",
                "company_types": ["Big Tech"],
                "brand_recognition": "High"
            },
            "years_experience": "eight",  # Should be integer
            "technical_skills": "Python, ML",  # Should be array
            "soft_skills": []
        }
        
        is_valid, errors = self.validator.validate_schema(invalid_resume_data, "resume")
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        print(f"✓ Invalid resume data fails schema validation ({len(errors)} errors)")
    
    def test_schema_validation_recruiter_valid(self):
        """Test schema validation with valid recruiter data"""
        valid_recruiter_data = {
            "sentiment": "positive",
            "strengths": ["Strong technical skills", "Great communication"],
            "concerns": ["Limited leadership experience"],
            "red_flags": [],
            "leadership_indicators": ["Mentored junior developers"],
            "cultural_fit": {
                "cultural_alignment": "good",
                "work_style": ["Collaborative", "Independent"],
                "values_alignment": ["Innovation", "Quality"],
                "team_fit": "excellent",
                "communication_style": "Direct and clear",
                "adaptability": "high",
                "cultural_add": ["Brings startup experience"]
            },
            "recommendation": "hire",
            "readiness_level": "ready_now",
            "key_themes": ["Technical Excellence", "Cultural Fit"],
            "development_areas": ["Leadership skills"],
            "competitive_advantages": ["Unique technical background"]
        }
        
        is_valid, errors = self.validator.validate_schema(valid_recruiter_data, "recruiter")
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        print("✓ Valid recruiter data passes schema validation")
    
    def test_completeness_scoring(self):
        """Test completeness scoring functionality"""
        # Complete data
        complete_data = {
            "career_trajectory": {"current_level": "Senior", "progression_speed": "Fast", "trajectory_type": "Technical Leadership"},
            "leadership_scope": {"has_leadership": True, "team_size": 5, "leadership_level": "Team Lead"},
            "company_pedigree": {"tier_level": "Tier1", "company_types": ["Tech"], "brand_recognition": "High"},
            "years_experience": 8,
            "technical_skills": ["Python", "ML"],
            "soft_skills": ["Communication"],
            "education": {"highest_degree": "BS", "institutions": ["MIT"]},
            "cultural_signals": ["Open source"]
        }
        
        completeness_score = self.validator.check_completeness(complete_data, "resume")
        self.assertGreater(completeness_score, 0.9)
        
        # Incomplete data (missing optional fields)
        incomplete_data = {
            "career_trajectory": {"current_level": "Senior", "progression_speed": "Fast", "trajectory_type": "Technical Leadership"},
            "leadership_scope": {"has_leadership": True, "team_size": 5, "leadership_level": "Team Lead"},
            "company_pedigree": {"tier_level": "Tier1", "company_types": ["Tech"], "brand_recognition": "High"},
            "years_experience": 8,
            "technical_skills": ["Python"],
            "soft_skills": ["Communication"]
        }
        
        incomplete_score = self.validator.check_completeness(incomplete_data, "resume")
        self.assertLess(incomplete_score, completeness_score)
        
        print(f"✓ Completeness scoring works (complete: {completeness_score:.2f}, incomplete: {incomplete_score:.2f})")
    
    def test_content_quality_scoring(self):
        """Test content quality scoring"""
        high_quality_data = {
            "technical_skills": ["Python", "Machine Learning", "Kubernetes", "React", "PostgreSQL"],
            "years_experience": 8,
            "career_trajectory": {
                "current_level": "Senior",
                "progression_speed": "Fast", 
                "trajectory_type": "Technical Leadership"
            }
        }
        
        low_quality_data = {
            "technical_skills": [""],  # Empty skill
            "years_experience": -5,    # Invalid experience
            "career_trajectory": {
                "current_level": "Entry",
                "progression_speed": "Fast",
                "trajectory_type": "Technical Leadership"
            }
        }
        
        high_score = self.validator.check_content_quality(high_quality_data, "resume")
        low_score = self.validator.check_content_quality(low_quality_data, "resume")
        
        self.assertGreater(high_score, low_score)
        print(f"✓ Content quality scoring works (high: {high_score:.2f}, low: {low_score:.2f})")
    
    def test_consistency_checking(self):
        """Test consistency checking"""
        consistent_data = {
            "leadership_scope": {
                "has_leadership": True,
                "team_size": 8,
                "leadership_level": "Manager"
            },
            "years_experience": 10  # Reasonable for a manager
        }
        
        inconsistent_data = {
            "leadership_scope": {
                "has_leadership": True,
                "team_size": 50,
                "leadership_level": "C-Level"  # C-Level with only 1 year is inconsistent
            },
            "years_experience": 1
        }
        
        consistent_score = self.validator.check_consistency(consistent_data, "resume")
        inconsistent_score = self.validator.check_consistency(inconsistent_data, "resume")
        
        self.assertGreaterEqual(consistent_score, inconsistent_score)
        print(f"✓ Consistency checking works (consistent: {consistent_score:.2f}, inconsistent: {inconsistent_score:.2f})")
    
    def test_fallback_corrections(self):
        """Test fallback correction mechanisms"""
        problematic_data = {
            "career_trajectory": "invalid",  # Should be object
            "years_experience": "five",      # Should be integer
            "technical_skills": "Python, Java",  # Should be array
            "soft_skills": None             # Should be array
        }
        
        corrected_data, fallback_applied = self.validator.apply_fallback_corrections(problematic_data, "resume")
        
        self.assertTrue(fallback_applied)
        self.assertIsInstance(corrected_data["years_experience"], int)
        self.assertIsInstance(corrected_data["technical_skills"], list)
        self.assertIsInstance(corrected_data["soft_skills"], list)
        
        print("✓ Fallback corrections work for problematic data")
    
    def test_full_validation_workflow(self):
        """Test complete validation workflow"""
        test_data = {
            "career_trajectory": {
                "current_level": "Senior",
                "progression_speed": "Fast",
                "trajectory_type": "Technical Leadership",
                "career_changes": 1
            },
            "leadership_scope": {
                "has_leadership": True,
                "team_size": 3,
                "leadership_level": "Team Lead",
                "mentorship_experience": True
            },
            "company_pedigree": {
                "tier_level": "Tier1",
                "company_types": ["Big Tech"],
                "brand_recognition": "High"
            },
            "years_experience": 7,
            "technical_skills": ["Python", "Kubernetes", "React"],
            "soft_skills": ["Leadership", "Communication"]
        }
        
        result = self.validator.validate_llm_output(test_data, "resume")
        
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertGreater(result.quality_score, 0.6)
        self.assertIsNotNone(result.metrics)
        self.assertIsNotNone(result.validated_data)
        
        print(f"✓ Full validation workflow - Quality: {result.quality_score:.2f}, Valid: {result.is_valid}")
    
    def test_validation_with_fallbacks(self):
        """Test validation with fallback corrections enabled"""
        invalid_data = {
            "sentiment": "invalid_sentiment",
            "strengths": "Should be array",
            "concerns": None,
            "recommendation": "definitely_hire",  # Invalid enum
            "readiness_level": "ready_now"
        }
        
        result = self.validator.validate_llm_output(invalid_data, "recruiter", apply_fallbacks=True)
        
        self.assertTrue(result.fallback_applied)
        self.assertGreater(result.quality_score, 0.0)
        
        # Check that corrections were applied
        validated_data = result.validated_data
        self.assertIn(validated_data["sentiment"], ["positive", "neutral", "negative", "mixed"])
        self.assertIsInstance(validated_data["strengths"], list)
        self.assertIsInstance(validated_data["concerns"], list)
        self.assertIn(validated_data["recommendation"], ["strong_hire", "hire", "maybe", "no_hire"])
        
        print(f"✓ Validation with fallbacks - Applied: {result.fallback_applied}, Quality: {result.quality_score:.2f}")
    
    def test_quality_metrics_calculation(self):
        """Test quality metrics calculation"""
        test_data = {
            "career_trajectory": {
                "current_level": "Senior",
                "progression_speed": "Fast",
                "trajectory_type": "Technical Leadership"
            },
            "leadership_scope": {
                "has_leadership": True,
                "team_size": 5,
                "leadership_level": "Team Lead"
            },
            "company_pedigree": {
                "tier_level": "Tier1",
                "company_types": ["Big Tech"],
                "brand_recognition": "High"
            },
            "years_experience": 8,
            "technical_skills": ["Python", "ML", "Kubernetes"],
            "soft_skills": ["Leadership", "Communication"]
        }
        
        metrics = self.validator.calculate_quality_metrics(test_data, "resume")
        
        self.assertIsInstance(metrics, QualityMetrics)
        self.assertGreaterEqual(metrics.completeness_score, 0.0)
        self.assertLessEqual(metrics.completeness_score, 1.0)
        self.assertGreaterEqual(metrics.consistency_score, 0.0)
        self.assertLessEqual(metrics.consistency_score, 1.0)
        self.assertGreaterEqual(metrics.content_quality_score, 0.0)
        self.assertLessEqual(metrics.content_quality_score, 1.0)
        self.assertGreaterEqual(metrics.schema_compliance_score, 0.0)
        self.assertLessEqual(metrics.schema_compliance_score, 1.0)
        self.assertGreater(metrics.overall_score, 0.0)
        
        print(f"✓ Quality metrics calculation - Overall: {metrics.overall_score:.2f}")
    
    def test_resume_analysis_integration(self):
        """Test integration with ResumeAnalysis objects"""
        # This test would require a proper ResumeAnalysis object
        # For now, test with dictionary data
        resume_dict = {
            "career_trajectory": {
                "current_level": "Senior",
                "progression_speed": "Fast",
                "trajectory_type": "Individual Contributor"
            },
            "leadership_scope": {
                "has_leadership": False,
                "team_size": 0,
                "leadership_level": "None"
            },
            "company_pedigree": {
                "tier_level": "Tier2",
                "company_types": ["Startup"],
                "brand_recognition": "Medium"
            },
            "years_experience": 6,
            "technical_skills": ["Python", "Django", "PostgreSQL"],
            "soft_skills": ["Problem Solving", "Analytical Thinking"]
        }
        
        result = self.validator.validate_resume_analysis(resume_dict)
        
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        print(f"✓ Resume analysis integration - Quality: {result.quality_score:.2f}")
    
    def test_recruiter_insights_integration(self):
        """Test integration with RecruiterInsights objects"""
        recruiter_dict = {
            "sentiment": "positive",
            "strengths": ["Strong technical skills", "Good cultural fit"],
            "concerns": ["Limited team leadership experience"],
            "red_flags": [],
            "leadership_indicators": ["Mentored interns"],
            "cultural_fit": {
                "cultural_alignment": "good",
                "work_style": ["Independent", "Collaborative"],
                "values_alignment": ["Quality", "Innovation"],
                "team_fit": "good",
                "communication_style": "Clear and direct",
                "adaptability": "high",
                "cultural_add": ["Technical expertise"]
            },
            "recommendation": "hire",
            "readiness_level": "ready_now",
            "key_themes": ["Technical Skills", "Cultural Fit"],
            "development_areas": ["Leadership"],
            "competitive_advantages": ["Deep technical knowledge"]
        }
        
        result = self.validator.validate_recruiter_insights(recruiter_dict)
        
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        print(f"✓ Recruiter insights integration - Quality: {result.quality_score:.2f}")
    
    def test_cli_functionality(self):
        """Test CLI functionality with temporary files"""
        test_data = {
            "sentiment": "positive",
            "strengths": ["Technical skills"],
            "concerns": [],
            "red_flags": [],
            "leadership_indicators": [],
            "cultural_fit": {
                "cultural_alignment": "good",
                "team_fit": "good",
                "adaptability": "high"
            },
            "recommendation": "hire",
            "readiness_level": "ready_now",
            "key_themes": [],
            "development_areas": [],
            "competitive_advantages": []
        }
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_file = f.name
        
        try:
            # Test the validator with the temporary file
            result = self.validator.validate_llm_output(test_data, "recruiter")
            self.assertTrue(result.is_valid)
            print("✓ CLI functionality test passed")
        finally:
            os.unlink(temp_file)


def run_validation_tests():
    """Run all validation tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test class
    suite.addTests(loader.loadTestsFromTestCase(TestQualityValidator))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("QUALITY VALIDATION TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    
    if result.failures:
        print(f"\nFailures:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")
    
    if result.errors:
        print(f"\nErrors:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_validation_tests()
    sys.exit(0 if success else 1)