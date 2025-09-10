import re
from scripts.prompt_builder import PromptBuilder


def test_resume_analysis_prompt_includes_core_sections():
    builder = PromptBuilder()
    candidate = {
        "name": "Alice Example",
        "experience": "Senior Software Engineer at ExampleCorp working on ML",
        "education": "BSc Computer Science",
    }
    prompt = builder.build_resume_analysis_prompt(candidate)

    assert "Alice Example" in prompt
    # Must instruct JSON-only output
    assert "JSON" in prompt.upper()
    # Core sections expected in schema
    for section in (
        "explicit_skills",
        "inferred_skills",
        "role_based_competencies",
        "company_context_skills",
        "career_trajectory_analysis",
        "market_positioning",
        "recruiter_insights",
    ):
        assert section in prompt


def test_other_prompts_contain_required_headers():
    builder = PromptBuilder()
    candidate = {"name": "Bob"}
    p1 = builder.build_recruiter_comments_prompt(candidate)
    p2 = builder.build_market_insights_prompt(candidate)
    p3 = builder.build_cultural_assessment_prompt(candidate)
    p4 = builder.build_executive_summary_prompt(candidate)

    assert "Bob" in p1 and "Bob" in p2 and "Bob" in p3 and "Bob" in p4
    # Ensure each contains an instruction to return JSON
    for p in (p1, p2, p3, p4):
        assert re.search(r"\bJSON\b", p, re.IGNORECASE)

