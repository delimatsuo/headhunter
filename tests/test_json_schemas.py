from scripts.schemas import IntelligentAnalysis, ExplicitSkills, InferredSkills, SkillItem


def test_minimal_intelligent_analysis_schema():
    payload = {
        "explicit_skills": {
            "technical_skills": ["python", "aws"]
        },
        "inferred_skills": {
            "highly_probable_skills": [
                {"skill": "kubernetes", "confidence": 90, "reasoning": "SRE role"}
            ],
            "probable_skills": [
                {"skill": "terraform", "confidence": 80}
            ]
        },
        "career_trajectory_analysis": {"current_level": "senior", "years_experience": 8},
        "recruiter_insights": {"overall_rating": "A", "recommendation": "highly-recommend"},
        "composite_skill_profile": {"primary_expertise": ["platform engineering"]}
    }

    obj = IntelligentAnalysis.model_validate(payload)
    assert obj.explicit_skills is not None
    assert obj.inferred_skills is not None
    assert obj.career_trajectory_analysis is not None

