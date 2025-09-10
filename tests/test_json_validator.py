import pytest
import json
import tempfile
import os
from scripts.json_validator import JSONValidator, ValidationResult
from scripts.schemas import IntelligentAnalysis


def test_validator_accepts_valid_json():
    """Test that valid JSON passes validation"""
    validator = JSONValidator()
    
    valid_data = {
        "explicit_skills": {
            "technical_skills": ["Python"],
            "tools_technologies": [],
            "soft_skills": [],
            "certifications": [],
            "confidence": "100%"
        },
        "inferred_skills": {
            "highly_probable_skills": [],
            "probable_skills": [],
            "likely_skills": [],
            "possible_skills": []
        },
        "role_based_competencies": {
            "current_role_competencies": {
                "role": "Engineer",
                "core_competencies": [],
                "typical_tools": [],
                "domain_knowledge": []
            },
            "historical_competencies": []
        },
        "company_context_skills": {
            "company_specific": [],
            "industry_skills": []
        },
        "skill_evolution_analysis": {
            "skill_trajectory": "expanding",
            "emerging_skills": [],
            "skill_gaps": [],
            "learning_velocity": "fast",
            "skill_currency": "current"
        },
        "composite_skill_profile": {
            "primary_expertise": [],
            "secondary_expertise": [],
            "domain_specialization": "backend",
            "skill_breadth": "t-shaped",
            "unique_combination": []
        },
        "career_trajectory_analysis": {
            "current_level": "senior",
            "years_experience": 5,
            "promotion_velocity": "fast",
            "career_progression": "linear",
            "performance_indicator": "above-average"
        },
        "market_positioning": {
            "skill_market_value": "high",
            "skill_rarity": "common",
            "competitive_advantage": [],
            "placement_difficulty": "easy",
            "ideal_next_roles": [],
            "salary_range": "$100k-150k"
        },
        "recruiter_insights": {
            "overall_rating": "A",
            "recommendation": "recommend",
            "confidence_in_assessment": "high",
            "verification_needed": [],
            "red_flags": [],
            "selling_points": [],
            "interview_focus": [],
            "one_line_pitch": "Strong backend engineer"
        }
    }
    
    result = validator.validate(json.dumps(valid_data))
    assert result.is_valid
    assert result.data == valid_data
    assert result.repair_attempts == 0


def test_validator_repairs_common_issues():
    """Test that common JSON issues are repaired"""
    validator = JSONValidator()
    
    # Test code fence stripping
    fenced_json = """```json
    {"career_trajectory_analysis": {"current_level": "senior", "years_experience": 5, "promotion_velocity": "fast", "career_progression": "linear", "performance_indicator": "above-average"}}
    ```"""
    
    result = validator.validate(fenced_json)
    # Should fail schema validation but succeed at JSON parsing
    assert not result.is_valid  # Schema validation will fail due to missing fields
    assert result.data is not None  # But JSON parsing succeeded
    assert result.repair_attempts > 0


def test_validator_quarantines_unfixable():
    """Test that unfixable JSON gets quarantined"""
    validator = JSONValidator()
    
    completely_broken = "This is not JSON at all {{{ [[[[ ....invalid"
    
    result = validator.validate(completely_broken)
    assert not result.is_valid
    assert result.data is None
    assert result.quarantined
    assert result.repair_attempts == 3  # Maximum attempts


def test_validation_metrics_tracking():
    """Test that validation metrics are tracked"""
    validator = JSONValidator()
    
    # Valid case
    valid_json = '{"test": "value"}'
    validator.validate(valid_json)
    
    # Invalid case that gets repaired
    fenced_json = '```json\n{"test": "value"}\n```'
    validator.validate(fenced_json)
    
    # Completely broken case
    broken_json = "not json at all"
    validator.validate(broken_json)
    
    metrics = validator.get_metrics()
    assert metrics['total_validations'] == 3
    assert metrics['successful_validations'] >= 1
    assert metrics['repair_attempts'] >= 1
    assert metrics['quarantined_count'] >= 1


def test_schema_versioning():
    """Test that schema versioning works"""
    validator = JSONValidator()
    
    # Should use default schema version
    assert validator.schema_version == "1.0"
    
    # Should be able to set different version
    validator_v2 = JSONValidator(schema_version="2.0")
    assert validator_v2.schema_version == "2.0"