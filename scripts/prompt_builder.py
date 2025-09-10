from typing import Dict, Any


class PromptBuilder:
    """Builds recruiter-grade prompts with explicit JSON instructions.

    These are lightweight builders intended for unit tests and for processors
    to compose structured instructions with slot substitution.
    """

    def _header(self, title: str) -> str:
        return f"You are an expert executive recruiter. {title}. Return ONLY valid JSON as specified.\n\n"

    def build_resume_analysis_prompt(self, candidate: Dict[str, Any]) -> str:
        name = candidate.get("name", "Unknown")
        experience = candidate.get("experience", "")
        education = candidate.get("education", "")

        return (
            self._header("Analyze the resume and produce structured fields")
            + f"CANDIDATE: {name}\n\n"
            + "Provide ONLY a JSON object with the following top-level keys: "
            "explicit_skills, inferred_skills, role_based_competencies, company_context_skills, "
            "skill_evolution_analysis, composite_skill_profile, career_trajectory_analysis, market_positioning, recruiter_insights.\n\n"
            + "Use this schema (names/structure only; fill values from context):\n\n"
            + "{"  # keep recognizable in tests without f-strings interfering
              "\n  \"explicit_skills\": {\n"
              "    \"technical_skills\": [\"...\"],\n"
              "    \"tools_technologies\": [\"...\"],\n"
              "    \"soft_skills\": [\"...\"],\n"
              "    \"certifications\": [\"...\"],\n"
              "    \"confidence\": \"100%\"\n  },\n"
              "  \"inferred_skills\": {\n"
              "    \"highly_probable_skills\": [{\"skill\": \"...\", \"confidence\": 95, \"reasoning\": \"...\"}],\n"
              "    \"probable_skills\": [],\n"
              "    \"likely_skills\": [],\n"
              "    \"possible_skills\": []\n  },\n"
              "  \"role_based_competencies\": {\n"
              "    \"current_role_competencies\": {\n"
              "      \"role\": \"...\", \"core_competencies\": [\"...\"], \"typical_tools\": [\"...\"], \"domain_knowledge\": [\"...\"]\n    },\n"
              "    \"historical_competencies\": []\n  },\n"
              "  \"company_context_skills\": {\n"
              "    \"company_specific\": [], \"industry_skills\": [\"...\"]\n  },\n"
              "  \"skill_evolution_analysis\": {\n"
              "    \"skill_trajectory\": \"...\", \"emerging_skills\": [\"...\"], \"skill_gaps\": [\"...\"], \"learning_velocity\": \"...\", \"skill_currency\": \"...\"\n  },\n"
              "  \"composite_skill_profile\": {\n"
              "    \"primary_expertise\": [\"...\"], \"secondary_expertise\": [\"...\"], \"domain_specialization\": \"...\", \"skill_breadth\": \"...\", \"unique_combination\": [\"...\"]\n  },\n"
              "  \"career_trajectory_analysis\": {\n"
              "    \"current_level\": \"...\", \"years_experience\": 0, \"promotion_velocity\": \"...\", \"career_progression\": \"...\", \"performance_indicator\": \"...\"\n  },\n"
              "  \"market_positioning\": {\n"
              "    \"skill_market_value\": \"...\", \"skill_rarity\": \"...\", \"competitive_advantage\": [\"...\"], \"placement_difficulty\": \"...\", \"ideal_next_roles\": [\"...\"], \"salary_range\": \"...\"\n  },\n"
              "  \"recruiter_insights\": {\n"
              "    \"overall_rating\": \"...\", \"recommendation\": \"...\", \"confidence_in_assessment\": \"...\", \"verification_needed\": [], \"red_flags\": [], \"selling_points\": [], \"interview_focus\": [], \"one_line_pitch\": \"...\"\n  }\n}"
            + "\n\nCONTEXT:\n"
            + f"Experience: {experience[:1000]}\nEducation: {education[:500]}\n"
        )

    def build_recruiter_comments_prompt(self, candidate: Dict[str, Any]) -> str:
        name = candidate.get("name", "Unknown")
        return (
            self._header("Summarize recruiter comments with actionable insights")
            + f"Candidate: {name}\n"
            + "Return JSON with keys: strengths, concerns, interview_focus, one_line_pitch."
        )

    def build_market_insights_prompt(self, candidate: Dict[str, Any]) -> str:
        name = candidate.get("name", "Unknown")
        return (
            self._header("Provide market insights for the candidate")
            + f"Candidate: {name}\n"
            + "Return JSON with keys: estimated_salary_range, market_demand, competitive_advantage, placement_difficulty, ideal_next_roles."
        )

    def build_cultural_assessment_prompt(self, candidate: Dict[str, Any]) -> str:
        name = candidate.get("name", "Unknown")
        return (
            self._header("Assess cultural fit from background signals")
            + f"Candidate: {name}\n"
            + "Return JSON with keys: work_style, company_fit, red_flags, strengths."
        )

    def build_executive_summary_prompt(self, candidate: Dict[str, Any]) -> str:
        name = candidate.get("name", "Unknown")
        return (
            self._header("Write an executive summary for hiring managers")
            + f"Candidate: {name}\n"
            + "Return JSON with keys: one_line_pitch, key_achievements, overall_rating, recommendation."
        )

