#!/usr/bin/env python3
"""
Comprehensive tests for the Skill Probability Assessment System

Tests all components of the skill confidence scoring and assessment pipeline:
- PromptBuilder skill enhancement
- Pydantic schema validation
- SkillAssessmentService processing
- Skill-aware search ranking
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# Add scripts directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from schemas import (
    SkillWithEvidence, ExplicitSkills, InferredSkillItem, InferredSkills,
    SkillAssessment, SkillAssessmentMetadata, IntelligentAnalysis
)
from prompt_builder import PromptBuilder
from skill_assessment_service import SkillAssessmentService


class TestSkillProbabilitySchemas:
    """Test Pydantic schemas for skill probability assessment"""
    
    def test_skill_with_evidence_creation(self):
        """Test SkillWithEvidence model validation"""
        # Valid skill with evidence
        skill = SkillWithEvidence(
            skill="Python",
            confidence=95,
            evidence=["Listed in skills section", "Used in 3 projects", "5+ years experience"]
        )
        
        assert skill.skill == "Python"
        assert skill.confidence == 95
        assert len(skill.evidence) == 3
        assert skill.evidence[0] == "Listed in skills section"
    
    def test_skill_with_evidence_defaults(self):
        """Test default values in SkillWithEvidence"""
        skill = SkillWithEvidence(skill="JavaScript")
        
        assert skill.confidence == 100  # Default confidence
        assert skill.evidence == []      # Default empty evidence
    
    def test_skill_confidence_validation(self):
        """Test confidence score validation bounds"""
        # Valid confidence ranges
        SkillWithEvidence(skill="Python", confidence=0)
        SkillWithEvidence(skill="Python", confidence=50)
        SkillWithEvidence(skill="Python", confidence=100)
        
        # Invalid confidence ranges should raise validation error
        try:
            SkillWithEvidence(skill="Python", confidence=-1)
            assert False, "Should have raised ValueError for confidence < 0"
        except ValueError:
            pass  # Expected
        
        try:
            SkillWithEvidence(skill="Python", confidence=101)
            assert False, "Should have raised ValueError for confidence > 100"
        except ValueError:
            pass  # Expected
    
    def test_explicit_skills_structure(self):
        """Test ExplicitSkills schema structure"""
        skills = ExplicitSkills(
            technical_skills=[
                SkillWithEvidence(skill="Python", confidence=95),
                SkillWithEvidence(skill="JavaScript", confidence=90)
            ],
            soft_skills=[
                SkillWithEvidence(skill="Leadership", confidence=85)
            ],
            languages=[
                SkillWithEvidence(skill="English", confidence=100)
            ]
        )
        
        assert len(skills.technical_skills) == 2
        assert len(skills.soft_skills) == 1
        assert len(skills.languages) == 1
        assert len(skills.tools_technologies) == 0  # Default empty list
    
    def test_inferred_skill_item(self):
        """Test InferredSkillItem schema"""
        inferred_skill = InferredSkillItem(
            skill="Machine Learning",
            confidence=75,
            reasoning="Inferred from data science projects and Python usage",
            skill_category="technical"
        )
        
        assert inferred_skill.skill == "Machine Learning"
        assert inferred_skill.confidence == 75
        assert "data science" in inferred_skill.reasoning
        assert inferred_skill.skill_category == "technical"
    
    def test_inferred_skills_structure(self):
        """Test InferredSkills schema with confidence levels"""
        inferred = InferredSkills(
            highly_probable_skills=[
                InferredSkillItem(skill="Docker", confidence=85, reasoning="DevOps background")
            ],
            probable_skills=[
                InferredSkillItem(skill="Kubernetes", confidence=75, reasoning="Cloud experience")
            ],
            likely_skills=[
                InferredSkillItem(skill="AWS", confidence=65, reasoning="Cloud mentions")
            ],
            possible_skills=[
                InferredSkillItem(skill="React", confidence=55, reasoning="Frontend context")
            ]
        )
        
        assert len(inferred.highly_probable_skills) == 1
        assert len(inferred.probable_skills) == 1
        assert len(inferred.likely_skills) == 1
        assert len(inferred.possible_skills) == 1
        
        # Verify confidence levels descend appropriately
        assert inferred.highly_probable_skills[0].confidence > inferred.probable_skills[0].confidence
        assert inferred.probable_skills[0].confidence > inferred.likely_skills[0].confidence
    
    def test_skill_assessment_metadata(self):
        """Test SkillAssessmentMetadata calculations"""
        metadata = SkillAssessmentMetadata(
            total_skills=15,
            average_confidence=82.5,
            skills_by_category={"technical": 8, "soft": 4, "leadership": 3},
            confidence_distribution={"high": 5, "medium": 7, "low": 3},
            assessment_quality_score=88
        )
        
        assert metadata.total_skills == 15
        assert metadata.average_confidence == 82.5
        assert metadata.skills_by_category["technical"] == 8
        assert metadata.confidence_distribution["high"] == 5
        assert metadata.assessment_quality_score == 88
    
    def test_skill_assessment_complete(self):
        """Test complete SkillAssessment model"""
        explicit_skills = ExplicitSkills(
            technical_skills=[SkillWithEvidence(skill="Python", confidence=95)]
        )
        inferred_skills = InferredSkills(
            highly_probable_skills=[InferredSkillItem(skill="Django", confidence=85, reasoning="Python web dev")]
        )
        metadata = SkillAssessmentMetadata(total_skills=2, average_confidence=90.0)
        
        assessment = SkillAssessment(
            candidate_id="test-123",
            explicit_skills=explicit_skills,
            inferred_skills=inferred_skills,
            role_based_competencies={},
            company_context_skills={},
            skill_evolution_analysis={},
            composite_skill_profile={},
            metadata=metadata
        )
        
        assert assessment.candidate_id == "test-123"
        assert len(assessment.explicit_skills.technical_skills) == 1
        assert len(assessment.inferred_skills.highly_probable_skills) == 1
        assert assessment.metadata.total_skills == 2


class TestPromptBuilderEnhancement:
    """Test PromptBuilder skill confidence enhancements"""
    
    def setUp(self):
        """Set up test environment"""
        self.prompt_builder = PromptBuilder()
    
    def test_prompt_builder_initialization(self):
        """Test PromptBuilder initializes correctly"""
        builder = PromptBuilder()
        assert builder is not None
        assert hasattr(builder, 'get_skill_confidence_prompt')
    
    def test_skill_confidence_prompt_structure(self):
        """Test skill confidence prompt generation"""
        builder = PromptBuilder()
        
        # Test with sample resume text
        resume_text = """
        Senior Software Engineer with 5+ years Python experience.
        Built web applications using Django and Flask.
        Experience with AWS, Docker, and CI/CD pipelines.
        Led a team of 3 developers on microservices architecture.
        """
        
        prompt = builder.get_skill_confidence_prompt(resume_text)
        
        # Verify prompt contains key skill assessment instructions
        assert "explicit_skills" in prompt
        assert "inferred_skills" in prompt
        assert "confidence" in prompt.lower()
        assert "technical_skills" in prompt
        assert "evidence" in prompt.lower()
    
    def test_skill_categorization_instructions(self):
        """Test that prompt includes proper skill categorization"""
        builder = PromptBuilder()
        prompt = builder.get_skill_confidence_prompt("Sample resume text")
        
        # Check for skill category instructions
        assert "technical" in prompt.lower()
        assert "soft" in prompt.lower() or "interpersonal" in prompt.lower()
        assert "leadership" in prompt.lower()
        assert "domain" in prompt.lower()
    
    def test_confidence_scoring_guidance(self):
        """Test confidence scoring guidelines in prompt"""
        builder = PromptBuilder()
        prompt = builder.get_skill_confidence_prompt("Sample resume")
        
        # Check for confidence level guidance
        assert "90-100" in prompt or "high confidence" in prompt.lower()
        assert "70-89" in prompt or "medium confidence" in prompt.lower()
        assert "50-69" in prompt or "low confidence" in prompt.lower()


class TestSkillAssessmentService:
    """Test SkillAssessmentService functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.service = SkillAssessmentService()
        self.sample_intelligent_analysis = {
            "explicit_skills": {
                "technical_skills": [
                    {"skill": "Python", "confidence": 95, "evidence": ["Listed in resume", "5+ years exp"]},
                    {"skill": "JavaScript", "confidence": 90, "evidence": ["Project work", "Frontend dev"]}
                ],
                "soft_skills": [
                    {"skill": "Leadership", "confidence": 85, "evidence": ["Led team of 3", "Mentoring"]}
                ]
            },
            "inferred_skills": {
                "highly_probable_skills": [
                    {"skill": "Django", "confidence": 85, "reasoning": "Python web development background"}
                ],
                "probable_skills": [
                    {"skill": "AWS", "confidence": 75, "reasoning": "Cloud deployment mentions"}
                ]
            }
        }
    
    def test_service_initialization(self):
        """Test SkillAssessmentService initialization"""
        service = SkillAssessmentService()
        assert service is not None
        assert hasattr(service, 'confidence_thresholds')
        assert service.confidence_thresholds['high'] == 90
        assert service.confidence_thresholds['medium'] == 70
        assert service.confidence_thresholds['low'] == 50
    
    def test_process_intelligent_analysis(self):
        """Test processing intelligent analysis data"""
        service = SkillAssessmentService()
        candidate_id = "test-candidate-123"
        
        assessment = service.process_intelligent_analysis(
            self.sample_intelligent_analysis, 
            candidate_id
        )
        
        assert assessment.candidate_id == candidate_id
        assert len(assessment.explicit_skills.technical_skills) == 2
        assert len(assessment.explicit_skills.soft_skills) == 1
        assert len(assessment.inferred_skills.highly_probable_skills) == 1
        assert assessment.metadata.total_skills > 0
        assert assessment.metadata.average_confidence > 0
    
    def test_skill_confidence_calculation(self):
        """Test skill confidence scoring"""
        service = SkillAssessmentService()
        
        # Test with different evidence types
        high_evidence_skill = {
            "skill": "Python",
            "evidence": ["explicitly listed", "certified", "5 years experience", "led team"]
        }
        
        medium_evidence_skill = {
            "skill": "JavaScript", 
            "evidence": ["mentioned in experience", "used in project"]
        }
        
        low_evidence_skill = {
            "skill": "Docker",
            "evidence": ["inferred from role"]
        }
        
        high_confidence = service.assess_skill_confidence(high_evidence_skill)
        medium_confidence = service.assess_skill_confidence(medium_evidence_skill)
        low_confidence = service.assess_skill_confidence(low_evidence_skill)
        
        assert high_confidence > medium_confidence > low_confidence
        assert high_confidence >= 90  # Should be high confidence
        assert medium_confidence >= 70  # Should be medium confidence
    
    def test_skill_categorization(self):
        """Test automatic skill categorization"""
        service = SkillAssessmentService()
        
        # Test technical skill categorization
        assert service.categorize_skill("Python") == "technical"
        assert service.categorize_skill("JavaScript") == "technical"
        assert service.categorize_skill("AWS") == "technical"
        
        # Test leadership skill categorization
        assert service.categorize_skill("leadership") == "leadership"
        assert service.categorize_skill("management") == "leadership"
        assert service.categorize_skill("mentoring") == "leadership"
        
        # Test soft skill categorization
        assert service.categorize_skill("communication") == "soft"
        assert service.categorize_skill("collaboration") == "soft"
        assert service.categorize_skill("problem solving") == "soft"
        
        # Test domain skill categorization
        assert service.categorize_skill("fintech") == "domain"
        assert service.categorize_skill("healthcare") == "domain"
    
    def test_quality_score_calculation(self):
        """Test assessment quality score calculation"""
        service = SkillAssessmentService()
        
        # High quality assessment (many skills, high confidence, diverse categories)
        high_quality_score = service._calculate_quality_score(
            total_skills=20,
            average_confidence=85.0,
            skills_by_category={"technical": 8, "soft": 4, "leadership": 3, "domain": 5},
            confidence_distribution={"high": 12, "medium": 6, "low": 2, "very_low": 0}
        )
        
        # Low quality assessment (few skills, low confidence, limited diversity)
        low_quality_score = service._calculate_quality_score(
            total_skills=5,
            average_confidence=45.0,
            skills_by_category={"technical": 5},
            confidence_distribution={"high": 1, "medium": 1, "low": 2, "very_low": 1}
        )
        
        assert high_quality_score > low_quality_score
        assert high_quality_score >= 80  # Should be high quality
        assert low_quality_score <= 60   # Should be lower quality
    
    def test_skill_match_scoring(self):
        """Test skill matching and scoring"""
        service = SkillAssessmentService()
        
        # Create sample assessment
        assessment = service.process_intelligent_analysis(
            self.sample_intelligent_analysis,
            "test-candidate"
        )
        
        # Test exact skill matches
        required_skills = ["Python", "JavaScript", "Leadership"]
        match_score, breakdown = service.calculate_skill_match_score(
            assessment, 
            required_skills
        )
        
        assert match_score > 0
        assert "Python" in breakdown["matched_skills"][0]["required_skill"]
        assert breakdown["total_required"] == 3
        assert breakdown["total_matched"] > 0
    
    def test_skills_by_confidence_filtering(self):
        """Test filtering skills by confidence level"""
        service = SkillAssessmentService()
        assessment = service.process_intelligent_analysis(
            self.sample_intelligent_analysis,
            "test-candidate"
        )
        
        # Get high confidence skills only
        high_confidence_skills = service.get_skills_by_confidence(assessment, 90)
        
        # All returned skills should have confidence >= 90
        for skill in high_confidence_skills:
            assert skill['confidence'] >= 90
    
    def test_skills_by_category_filtering(self):
        """Test filtering skills by category"""
        service = SkillAssessmentService()
        assessment = service.process_intelligent_analysis(
            self.sample_intelligent_analysis,
            "test-candidate"
        )
        
        # Get technical skills only
        technical_skills = service.get_skills_by_category(assessment, "technical")
        
        # All returned skills should be technical
        for skill in technical_skills:
            assert skill.get('category') == 'technical' or skill.get('source') == 'explicit'


class TestSkillAwareSearchIntegration:
    """Test skill-aware search integration"""
    
    def test_skill_assessment_integration(self):
        """Test integration with skill assessment service"""
        # Create a real service for integration testing
        service = SkillAssessmentService()
        
        # Test with sample data
        sample_analysis = {
            "explicit_skills": {
                "technical_skills": [
                    {"skill": "Python", "confidence": 95, "evidence": ["Listed in resume"]}
                ]
            },
            "inferred_skills": {
                "highly_probable_skills": [
                    {"skill": "Django", "confidence": 85, "reasoning": "Python web dev", "skill_category": "technical"}
                ]
            }
        }
        
        result = service.process_intelligent_analysis(sample_analysis, "test-id")
        
        assert result is not None
        assert result.candidate_id == "test-id"
        assert len(result.explicit_skills.technical_skills) == 1
        assert len(result.inferred_skills.highly_probable_skills) == 1
        
        # Test get_all_skills_with_confidence method
        skills = result.get_all_skills_with_confidence()
        assert len(skills) >= 2  # At least Python and Django
        
        # Find Python skill
        python_skill = next((s for s in skills if s['skill'] == 'Python'), None)
        assert python_skill is not None
        assert python_skill['confidence'] == 95
        assert python_skill['source'] == 'explicit'


class TestSkillProbabilitySystemIntegration:
    """Integration tests for the complete skill probability system"""
    
    def test_end_to_end_skill_assessment(self):
        """Test complete end-to-end skill assessment pipeline"""
        # Sample data representing output from Together AI
        together_ai_output = {
            "explicit_skills": {
                "technical_skills": [
                    {
                        "skill": "Python",
                        "confidence": 100,
                        "evidence": [
                            "Listed in skills section",
                            "5+ years professional experience",
                            "Led Python-based projects"
                        ]
                    },
                    {
                        "skill": "Django",
                        "confidence": 95,
                        "evidence": [
                            "Web framework expertise mentioned",
                            "Built REST APIs with Django"
                        ]
                    }
                ],
                "soft_skills": [
                    {
                        "skill": "Leadership",
                        "confidence": 90,
                        "evidence": [
                            "Led team of 5 developers",
                            "Mentoring experience documented"
                        ]
                    }
                ]
            },
            "inferred_skills": {
                "highly_probable_skills": [
                    {
                        "skill": "PostgreSQL",
                        "confidence": 85,
                        "reasoning": "Django typically uses PostgreSQL, web backend experience",
                        "skill_category": "technical"
                    }
                ],
                "probable_skills": [
                    {
                        "skill": "Docker",
                        "confidence": 75,
                        "reasoning": "Modern web development typically involves containerization",
                        "skill_category": "technical"
                    }
                ]
            }
        }
        
        # Process through SkillAssessmentService
        service = SkillAssessmentService()
        assessment = service.process_intelligent_analysis(
            together_ai_output, 
            "candidate-456"
        )
        
        # Verify assessment structure
        assert assessment.candidate_id == "candidate-456"
        assert assessment.metadata.total_skills == 5  # 3 explicit + 2 inferred
        assert assessment.metadata.average_confidence > 80  # Should be high overall
        assert assessment.metadata.assessment_quality_score > 70  # Good quality
        
        # Verify explicit skills processing
        assert len(assessment.explicit_skills.technical_skills) == 2
        assert len(assessment.explicit_skills.soft_skills) == 1
        
        python_skill = assessment.explicit_skills.technical_skills[0]
        assert python_skill.skill == "Python"
        assert python_skill.confidence == 100
        assert len(python_skill.evidence) == 3
        
        # Verify inferred skills processing
        assert len(assessment.inferred_skills.highly_probable_skills) == 1
        assert len(assessment.inferred_skills.probable_skills) == 1
        
        postgresql_skill = assessment.inferred_skills.highly_probable_skills[0]
        assert postgresql_skill.skill == "PostgreSQL"
        assert postgresql_skill.confidence == 85
        assert postgresql_skill.skill_category == "technical"
        
        # Test skill matching functionality
        required_skills = ["Python", "Django", "PostgreSQL", "AWS"]  # Include a missing skill
        match_score, breakdown = service.calculate_skill_match_score(
            assessment, 
            required_skills
        )
        
        # Should have good match score for 3/4 skills
        assert match_score > 60  # Should be good match for most skills
        assert breakdown["total_required"] == 4
        assert breakdown["total_matched"] == 3  # Python, Django, PostgreSQL should match
        assert breakdown["match_percentage"] == 75  # 3 out of 4 = 75%
        
        # Verify detailed match breakdown
        matched_skills = breakdown["matched_skills"]
        skill_names = [match["required_skill"] for match in matched_skills]
        assert "Python" in skill_names
        assert "Django" in skill_names
        assert "PostgreSQL" in skill_names
        
        # Verify missing skills
        missing_skills = breakdown["missing_skills"]
        assert len(missing_skills) == 1
        assert missing_skills[0]["required_skill"] == "AWS"
    
    def test_skill_confidence_levels(self):
        """Test different skill confidence levels and their processing"""
        test_cases = [
            # High confidence explicit skill
            {
                "skill": "Python",
                "confidence": 100,
                "evidence": ["explicitly listed", "certified", "years of experience"],
                "expected_category": "technical",
                "expected_threshold": "high"
            },
            # Medium confidence inferred skill
            {
                "skill": "Docker",
                "confidence": 75,
                "reasoning": "DevOps background suggests containerization knowledge",
                "skill_category": "technical",
                "expected_threshold": "medium"
            },
            # Low confidence inferred skill
            {
                "skill": "Kubernetes",
                "confidence": 55,
                "reasoning": "Possible given container orchestration needs",
                "skill_category": "technical",
                "expected_threshold": "low"
            }
        ]
        
        service = SkillAssessmentService()
        
        for case in test_cases:
            if "evidence" in case:
                # Test explicit skill confidence assessment
                confidence = service.assess_skill_confidence(case)
                if case["expected_threshold"] == "high":
                    assert confidence >= 90
                elif case["expected_threshold"] == "medium":
                    assert 70 <= confidence < 90
                else:  # low
                    assert 50 <= confidence < 70
            
            # Test categorization
            category = service.categorize_skill(case["skill"])
            assert category == case["expected_category"]
    
    def test_assessment_metadata_accuracy(self):
        """Test that assessment metadata is calculated accurately"""
        # Create assessment with known skill distribution
        explicit_skills = ExplicitSkills(
            technical_skills=[
                SkillWithEvidence(skill="Python", confidence=95),
                SkillWithEvidence(skill="JavaScript", confidence=90),
            ],
            soft_skills=[
                SkillWithEvidence(skill="Leadership", confidence=85),
            ]
        )
        
        inferred_skills = InferredSkills(
            highly_probable_skills=[
                InferredSkillItem(skill="Docker", confidence=80, reasoning="DevOps", skill_category="technical")
            ],
            probable_skills=[
                InferredSkillItem(skill="AWS", confidence=70, reasoning="Cloud", skill_category="technical")
            ]
        )
        
        # Manually calculate expected values
        expected_total = 5  # 2 + 1 + 1 + 1
        expected_avg_confidence = (95 + 90 + 85 + 80 + 70) / 5  # 84.0
        
        # Create metadata (normally done by service)
        service = SkillAssessmentService()
        metadata = service._calculate_assessment_metadata(
            explicit_skills,
            inferred_skills,
            "test-candidate"
        )
        
        assert metadata.total_skills == expected_total
        assert abs(metadata.average_confidence - expected_avg_confidence) < 0.1
        assert metadata.skills_by_category["technical"] == 4  # Python, JS, Docker, AWS
        assert metadata.skills_by_category["soft"] == 1      # Leadership


def run_comprehensive_tests():
    """Run all skill probability system tests"""
    print("🧪 Running Comprehensive Skill Probability System Tests")
    print("=" * 60)
    
    test_classes = [
        TestSkillProbabilitySchemas,
        TestPromptBuilderEnhancement, 
        TestSkillAssessmentService,
        TestSkillAwareSearchIntegration,
        TestSkillProbabilitySystemIntegration
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for test_class in test_classes:
        print(f"\n📋 Running {test_class.__name__}")
        print("-" * 40)
        
        # Get all test methods
        test_methods = [method for method in dir(test_class) if method.startswith('test_')]
        
        for method_name in test_methods:
            total_tests += 1
            try:
                # Create instance and run test
                test_instance = test_class()
                
                # Run setUp if it exists
                if hasattr(test_instance, 'setUp'):
                    test_instance.setUp()
                
                # Run the test method
                test_method = getattr(test_instance, method_name)
                test_method()
                
                print(f"  ✅ {method_name}")
                passed_tests += 1
                
            except Exception as e:
                print(f"  ❌ {method_name}: {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Skill probability system is working correctly.")
        return True
    else:
        print(f"⚠️  {total_tests - passed_tests} tests failed. Review implementation.")
        return False


if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)