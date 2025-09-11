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
              "    \"technical_skills\": [{\"skill\": \"...\", \"confidence\": 100, \"evidence\": [\"mentioned in experience\", \"listed in skills\"]}],\n"
              "    \"tools_technologies\": [{\"skill\": \"...\", \"confidence\": 100, \"evidence\": [\"used in project X\"]}],\n"
              "    \"soft_skills\": [{\"skill\": \"...\", \"confidence\": 100, \"evidence\": [\"demonstrated through leadership role\"]}],\n"
              "    \"certifications\": [{\"skill\": \"...\", \"confidence\": 100, \"evidence\": [\"explicitly listed\"]}],\n"
              "    \"languages\": [{\"skill\": \"...\", \"confidence\": 100, \"evidence\": [\"native/fluent/conversational\"]}]\n  },\n"
              "  \"inferred_skills\": {\n"
              "    \"highly_probable_skills\": [{\"skill\": \"...\", \"confidence\": 95, \"reasoning\": \"strong indicators from role/company\", \"skill_category\": \"technical|soft|domain\"}],\n"
              "    \"probable_skills\": [{\"skill\": \"...\", \"confidence\": 80, \"reasoning\": \"likely based on typical requirements\", \"skill_category\": \"technical|soft|domain\"}],\n"
              "    \"likely_skills\": [{\"skill\": \"...\", \"confidence\": 65, \"reasoning\": \"common for this role/industry\", \"skill_category\": \"technical|soft|domain\"}],\n"
              "    \"possible_skills\": [{\"skill\": \"...\", \"confidence\": 50, \"reasoning\": \"potential based on context\", \"skill_category\": \"technical|soft|domain\"}]\n  },\n"
              "  \"role_based_competencies\": {\n"
              "    \"current_role_competencies\": {\n"
              "      \"role\": \"...\", \"core_competencies\": [\"...\"], \"typical_tools\": [\"...\"], \"domain_knowledge\": [\"...\"]\n    },\n"
              "    \"historical_competencies\": []\n  },\n"
              "  \"company_context_skills\": {\n"
              "    \"company_specific\": [], \"industry_skills\": [\"...\"]\n  },\n"
              "  \"skill_evolution_analysis\": {\n"
              "    \"skill_trajectory\": \"...\", \"emerging_skills\": [\"...\"], \"skill_gaps\": [\"...\"], \"learning_velocity\": \"...\", \"skill_currency\": \"...\",\n"
              "    \"skill_timeline\": [{\"skill\": \"...\", \"first_used\": \"year\", \"last_used\": \"year\", \"frequency\": \"high|medium|low\", \"recency_score\": 95}],\n"
              "    \"skill_depth_analysis\": {\"beginner_skills\": [\"...\"], \"intermediate_skills\": [\"...\"], \"advanced_skills\": [\"...\"], \"expert_skills\": [\"...\"]}\n  },\n"
              "  \"composite_skill_profile\": {\n"
              "    \"primary_expertise\": [{\"skill\": \"...\", \"confidence\": 95, \"market_demand\": \"high|medium|low\"}], \n"
              "    \"secondary_expertise\": [{\"skill\": \"...\", \"confidence\": 80, \"market_demand\": \"high|medium|low\"}], \n"
              "    \"domain_specialization\": \"...\", \"skill_breadth\": \"...\", \"unique_combination\": [\"...\"],\n"
              "    \"skill_categories\": {\"technical_skills\": [\"...\"], \"soft_skills\": [\"...\"], \"domain_skills\": [\"...\"], \"leadership_skills\": [\"...\"]},\n"
              "    \"transferable_skills\": [{\"skill\": \"...\", \"transferability\": \"high|medium|low\", \"target_industries\": [\"...\"]}]\n  },\n"
              "  \"career_trajectory_analysis\": {\n"
              "    \"current_level\": \"...\", \"years_experience\": 0, \"promotion_velocity\": \"...\", \"career_progression\": \"...\", \"performance_indicator\": \"...\"\n  },\n"
              "  \"market_positioning\": {\n"
              "    \"skill_market_value\": \"...\", \"skill_rarity\": \"...\", \"competitive_advantage\": [\"...\"], \"placement_difficulty\": \"...\", \"ideal_next_roles\": [\"...\"], \"salary_range\": \"...\"\n  },\n"
              "  \"recruiter_insights\": {\n"
              "    \"overall_rating\": \"...\", \"recommendation\": \"...\", \"confidence_in_assessment\": \"...\", \"verification_needed\": [], \"red_flags\": [], \"selling_points\": [], \"interview_focus\": [], \"one_line_pitch\": \"...\"\n  }\n}"
            + "\n\nSKILL CONFIDENCE SCORING INSTRUCTIONS:\n"
            + "- Explicit skills (100% confidence): Skills directly mentioned, listed, or demonstrated\n"
            + "- Highly probable (90-95%): Strong role/company indicators, typical for position\n"
            + "- Probable (75-89%): Likely based on industry standards and role requirements\n"
            + "- Likely (60-74%): Common skills for this career level and domain\n"
            + "- Possible (50-59%): Potential skills based on context clues\n\n"
            + "SKILL CATEGORIZATION:\n"
            + "- Technical: Programming languages, frameworks, tools, technologies\n"
            + "- Soft: Communication, leadership, problem-solving, teamwork\n"
            + "- Domain: Industry-specific knowledge, business acumen, regulatory knowledge\n"
            + "- Leadership: People management, strategic thinking, decision-making\n\n"
            + "EVIDENCE REQUIREMENTS:\n"
            + "- For explicit skills: Provide specific evidence from resume text\n"
            + "- For inferred skills: Explain reasoning based on role, company, or industry\n"
            + "- Include recency and frequency of skill usage when possible\n\n"
            + "CONTEXT:\n"
            + f"Experience: {experience[:1500]}\nEducation: {education[:750]}\n"
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

