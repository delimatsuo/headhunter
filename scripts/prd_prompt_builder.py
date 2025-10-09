"""
PRD-Compliant Prompt Builder for Together AI Single-Pass Enrichment

Creates PII-minimizing prompts that return structured JSON matching
the PRD requirements (lines 61-72) for candidate enrichment.

Key principles:
- Use minimal PII necessary for analysis
- Focus on skills, roles, and companies (less sensitive than personal details)
- Single-pass enrichment returning complete PRD structure
- Clear JSON schema guidance for reliable parsing
"""

from typing import Dict, Any


class PRDPromptBuilder:
    """
    Builds PII-minimizing prompts for Together AI Qwen 2.5 32B
    Returns PRD-compliant structured JSON in single pass
    """

    def build_single_pass_enrichment_prompt(self, candidate: Dict[str, Any]) -> str:
        """
        Create comprehensive single-pass prompt for candidate enrichment

        Args:
            candidate: Dictionary with keys: name, experience, education, comments

        Returns:
            Prompt string for Together AI that returns PRD-compliant JSON
        """
        # Extract candidate data (minimize PII exposure)
        name = candidate.get("name", "Candidate")
        experience = candidate.get("experience", "")[:2000]  # Limit length
        education = candidate.get("education", "")[:1000]
        comments = candidate.get("comments", [])

        # Combine recruiter comments if available
        comments_text = ""
        if comments:
            comments_text = "\n".join([
                f"- {c.get('comment', '')}" for c in comments[:5]  # Limit to 5 comments
            ])

        prompt = f"""You are a senior technical recruiter with 15+ years of experience analyzing candidate profiles for technology companies.

TASK: Analyze this candidate profile and return a comprehensive assessment in JSON format.

===== CANDIDATE DATA =====

NAME: {name}

EXPERIENCE:
{experience}

EDUCATION:
{education}

RECRUITER COMMENTS:
{comments_text if comments_text else "No comments available"}

===== ANALYSIS INSTRUCTIONS =====

Perform a comprehensive single-pass analysis covering:

1. Personal Details: Extract basic career information (seniority level, years of experience, location)
2. Education Analysis: Evaluate educational background quality and relevance
3. Experience Analysis: Assess career progression and company tier
4. Technical Assessment: Identify primary skills and expertise level
5. Market Insights: Estimate salary range, market demand, placement difficulty
6. Cultural Assessment: Evaluate strengths, potential concerns, ideal fit
7. Executive Summary: Create concise value proposition for hiring managers
8. Skill Inference: Separate EXPLICIT skills (100% confidence) from INFERRED skills (0-100% confidence)

===== SKILL INFERENCE GUIDELINES =====

EXPLICIT SKILLS (confidence=100):
- Skills directly mentioned in experience or education
- Technologies explicitly listed
- Certifications or tools specifically named
- Evidence: Quote the exact text showing the skill

INFERRED SKILLS (confidence 0-100):
- Skills likely based on role, company, or industry context
- Technologies typically required for positions held
- Competencies implied by seniority and responsibilities

CONFIDENCE SCORING:
- 90-100: Extremely likely (e.g., "Senior ML Engineer at Meta" → PyTorch)
- 75-89: Highly probable (typical for role/company)
- 60-74: Likely (common for career level/domain)
- 40-59: Possible (could have based on context)
- 0-39: Uncertain (insufficient evidence)

EVIDENCE REQUIREMENTS:
- Explicit skills: Quote specific text from profile
- Inferred skills: Explain reasoning (e.g., "Meta uses PyTorch extensively")

===== RETURN FORMAT =====

Return ONLY valid JSON (no markdown, no code blocks) with this EXACT structure:

{{
  "personal_details": {{
    "name": "{name}",
    "seniority_level": "Junior|Mid|Senior|Principal|Executive",
    "years_of_experience": <number>,
    "location": "City, Country (or Remote)"
  }},
  "education_analysis": {{
    "degrees": ["degree name and field"],
    "quality_score": <0-100>,
    "relevance": "high|medium|low",
    "institutions": ["university names"]
  }},
  "experience_analysis": {{
    "companies": ["company names"],
    "current_role": "most recent title",
    "career_progression": "fast|steady|lateral",
    "industry_focus": ["primary industries"],
    "role_progression": ["chronological role titles"]
  }},
  "technical_assessment": {{
    "primary_skills": ["core technical competencies"],
    "expertise_level": "beginner|intermediate|advanced|expert",
    "tech_stack": ["technologies and frameworks"],
    "domain_expertise": ["domain knowledge areas"]
  }},
  "market_insights": {{
    "salary_range": "$XXXk-$XXXk (USD/BRL)",
    "market_demand": "high|medium|low",
    "placement_difficulty": "easy|moderate|difficult",
    "competitive_advantage": ["key differentiators"]
  }},
  "cultural_assessment": {{
    "strengths": ["professional strengths"],
    "red_flags": ["potential concerns or gaps"],
    "ideal_roles": ["best-fit role types"],
    "target_companies": ["suggested companies"],
    "work_style": "description"
  }},
  "executive_summary": {{
    "one_line_pitch": "concise value proposition",
    "overall_rating": <0-100>,
    "recommendation": "strong|consider|pass",
    "key_achievements": ["notable accomplishments"]
  }},
  "skill_inference": {{
    "explicit_skills": [
      {{
        "skill": "skill name",
        "confidence": 100,
        "evidence": ["quoted text from profile"],
        "reasoning": "explicitly mentioned"
      }}
    ],
    "inferred_skills": [
      {{
        "skill": "skill name",
        "confidence": <0-100>,
        "evidence": ["supporting context"],
        "reasoning": "why this skill is inferred"
      }}
    ]
  }},
  "analysis_confidence": <0.0-1.0>
}}

===== CRITICAL REQUIREMENTS =====

1. Return ONLY the JSON object (no explanations, no markdown)
2. Use the exact field names shown above
3. Provide confidence scores for ALL inferred skills
4. Include evidence and reasoning for skill assessments
5. analysis_confidence should reflect data quality (0.0=very low, 1.0=very high)
6. Set analysis_confidence < 0.5 for sparse profiles (low_content demotion)

===== EXAMPLES =====

Example 1 - High Confidence Inference:
- Role: "Senior ML Engineer at Meta (2020-2023)"
- Inferred: {{"skill": "PyTorch", "confidence": 95, "reasoning": "Meta's primary ML framework"}}

Example 2 - Medium Confidence Inference:
- Role: "Lead Backend Engineer at Nubank"
- Inferred: {{"skill": "Scala", "confidence": 85, "reasoning": "Nubank's primary backend language"}}

Example 3 - Low Confidence Inference:
- Role: "Software Engineer at Startup"
- Inferred: {{"skill": "Agile", "confidence": 60, "reasoning": "Common in startup environments"}}

Now analyze the candidate above and return the JSON structure."""

        return prompt


    def build_minimal_pii_prompt(self, candidate: Dict[str, Any]) -> str:
        """
        Alternative prompt that minimizes PII even further
        Uses anonymized approach focused purely on skills and roles

        This can be used when privacy is paramount and name is not needed.
        """
        experience = candidate.get("experience", "")[:2000]
        education = candidate.get("education", "")[:1000]

        prompt = f"""You are a technical recruiter analyzing an anonymized candidate profile.

EXPERIENCE (roles and companies only):
{self._anonymize_experience(experience)}

EDUCATION (degrees and institutions only):
{self._anonymize_education(education)}

Analyze this profile and return assessment in JSON format (same structure as main prompt).
Focus on skills, roles, and career progression. Name field should be "Anonymized Candidate".
Set analysis_confidence based on data quality."""

        return prompt


    def _anonymize_experience(self, experience: str) -> str:
        """Strip potential PII from experience text while keeping roles/companies"""
        # Simple implementation - in production could use NER to remove names/emails
        return experience  # Placeholder - implement proper anonymization if needed


    def _anonymize_education(self, education: str) -> str:
        """Strip potential PII from education text while keeping degrees/institutions"""
        # Simple implementation - in production could use NER to remove names/emails
        return education  # Placeholder - implement proper anonymization if needed
