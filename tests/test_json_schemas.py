import pytest
from pydantic import BaseModel, ValidationError, Field
from typing import List, Optional
from scripts.schemas import (
    ExplicitSkills,
    InferredSkillItem,
    InferredSkills,
    CareerTrajectory,
    ResumeAnalysis,
    RecruiterInsights,
    IntelligentAnalysis,
)


def test_valid_intelligent_analysis_schema_accepts_well_formed_data():
    data = {
        "explicit_skills": {
            "technical_skills": ["Python", "SQL"],
            "tools_technologies": ["Airflow"],
            "soft_skills": ["Leadership"],
            "certifications": [],
            "confidence": "100%",
        },
        "inferred_skills": {
            "highly_probable_skills": [
                {"skill": "System design", "confidence": 95, "reasoning": "Senior role"}
            ],
            "probable_skills": [],
            "likely_skills": [],
            "possible_skills": [],
        },
        "role_based_competencies": {
            "current_role_competencies": {
                "role": "Senior Engineer",
                "core_competencies": ["Backend"],
                "typical_tools": ["Postgres"],
                "domain_knowledge": ["Fintech"],
            },
            "historical_competencies": [],
        },
        "company_context_skills": {
            "company_specific": [],
            "industry_skills": ["SaaS"],
        },
        "skill_evolution_analysis": {
            "skill_trajectory": "expanding",
            "emerging_skills": ["LLM"],
            "skill_gaps": ["Systems"],
            "learning_velocity": "fast",
            "skill_currency": "current",
        },
        "composite_skill_profile": {
            "primary_expertise": ["Python"],
            "secondary_expertise": ["SQL"],
            "domain_specialization": "Data",
            "skill_breadth": "t-shaped",
            "unique_combination": ["ML + Product"],
        },
        "career_trajectory_analysis": {
            "current_level": "senior",
            "years_experience": 8,
            "promotion_velocity": "fast",
            "career_progression": "accelerated",
            "performance_indicator": "above-average",
        },
        "market_positioning": {
            "skill_market_value": "high",
            "skill_rarity": "uncommon",
            "competitive_advantage": ["Breadth"],
            "placement_difficulty": "moderate",
            "ideal_next_roles": ["Staff Engineer"],
            "salary_range": "$180,000 - $230,000",
        },
        "recruiter_insights": {
            "overall_rating": "A",
            "recommendation": "highly-recommend",
            "confidence_in_assessment": "high",
            "verification_needed": [],
            "red_flags": [],
            "selling_points": ["Leadership"],
            "interview_focus": ["System design"],
            "one_line_pitch": "Senior backend leader",
        },
    }

    model = IntelligentAnalysis.model_validate(data)
    assert model.career_trajectory_analysis.years_experience == 8


def test_schema_rejects_wrong_types():
    bad = {
        "explicit_skills": {"technical_skills": "Python"},  # should be list
        "inferred_skills": {
            "highly_probable_skills": [{"skill": "X", "confidence": "95", "reasoning": "r"}],
        },
    }
    with pytest.raises(ValidationError):
        IntelligentAnalysis.model_validate(bad)

