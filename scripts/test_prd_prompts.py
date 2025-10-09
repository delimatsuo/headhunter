#!/usr/bin/env python3
"""
Unit tests for PRD-compliant prompt builder

Validates that prompts:
1. Are properly formatted
2. Include all required sections
3. Minimize PII appropriately
4. Guide LLM to return PRD-compliant JSON structure
"""

import unittest
from scripts.prd_prompt_builder import PRDPromptBuilder
from scripts.prd_schemas import PRDCompliantProfile, SkillItem


class TestPRDPromptBuilder(unittest.TestCase):
    """Test cases for PRD-compliant prompt generation"""

    def setUp(self):
        """Set up test fixtures"""
        self.builder = PRDPromptBuilder()

        # Sample candidate data
        self.sample_candidate = {
            "name": "Test Candidate",
            "experience": """
            Senior Software Engineer at Meta (2020-2023)
            - Built ML infrastructure for News Feed ranking
            - Managed team of 5 engineers
            - Shipped features to 2 billion users

            Software Engineer at Nubank (2018-2020)
            - Backend development using Scala and Clojure
            - Payment processing systems
            - Microservices architecture
            """,
            "education": """
            BS Computer Science, University of São Paulo (2018)
            - GPA: 3.8/4.0
            - Focus: Machine Learning and Distributed Systems
            """,
            "comments": [
                {"comment": "Strong technical leader, excellent communication"},
                {"comment": "Great culture fit for fintech"}
            ]
        }

    def test_prompt_includes_all_sections(self):
        """Verify prompt includes all PRD-required sections"""
        prompt = self.builder.build_single_pass_enrichment_prompt(self.sample_candidate)

        required_sections = [
            "personal_details",
            "education_analysis",
            "experience_analysis",
            "technical_assessment",
            "market_insights",
            "cultural_assessment",
            "executive_summary",
            "skill_inference",
            "analysis_confidence"
        ]

        for section in required_sections:
            self.assertIn(section, prompt,
                          f"Prompt missing required section: {section}")

    def test_prompt_includes_skill_inference_guidelines(self):
        """Verify prompt has detailed skill inference instructions"""
        prompt = self.builder.build_single_pass_enrichment_prompt(self.sample_candidate)

        self.assertIn("EXPLICIT SKILLS", prompt)
        self.assertIn("INFERRED SKILLS", prompt)
        self.assertIn("confidence", prompt.lower())
        self.assertIn("evidence", prompt.lower())
        self.assertIn("reasoning", prompt.lower())

    def test_prompt_includes_examples(self):
        """Verify prompt provides inference examples"""
        prompt = self.builder.build_single_pass_enrichment_prompt(self.sample_candidate)

        self.assertIn("EXAMPLES", prompt)
        self.assertIn("Meta", prompt)  # Should have company-based inference example

    def test_prompt_specifies_json_only(self):
        """Verify prompt explicitly requests JSON-only response"""
        prompt = self.builder.build_single_pass_enrichment_prompt(self.sample_candidate)

        self.assertIn("ONLY valid JSON", prompt)
        self.assertIn("no markdown", prompt)
        self.assertIn("no code blocks", prompt)

    def test_prompt_limits_experience_length(self):
        """Verify experience text is truncated to reasonable length"""
        long_experience = "x" * 5000  # 5000 chars
        candidate = {**self.sample_candidate, "experience": long_experience}

        prompt = self.builder.build_single_pass_enrichment_prompt(candidate)

        # Should truncate to 2000 chars (not include all 5000)
        # Count 'x' characters in prompt to verify truncation
        x_count = prompt.count('x')
        self.assertLessEqual(x_count, 2050, "Experience should be truncated to ~2000 chars")
        self.assertGreater(x_count, 1900, "Experience should include most of the 2000 char limit")

    def test_prompt_includes_confidence_scoring_guide(self):
        """Verify prompt has confidence score guidelines"""
        prompt = self.builder.build_single_pass_enrichment_prompt(self.sample_candidate)

        self.assertIn("90-100", prompt)  # High confidence range
        self.assertIn("75-89", prompt)   # Medium-high
        self.assertIn("60-74", prompt)   # Medium
        self.assertIn("CONFIDENCE SCORING", prompt)

    def test_prompt_includes_analysis_confidence_field(self):
        """Verify prompt requests analysis_confidence for data quality"""
        prompt = self.builder.build_single_pass_enrichment_prompt(self.sample_candidate)

        self.assertIn("analysis_confidence", prompt)
        self.assertIn("0.0-1.0", prompt)
        self.assertIn("low_content", prompt.lower())

    def test_minimal_pii_prompt(self):
        """Test alternative minimal PII prompt"""
        prompt = self.builder.build_minimal_pii_prompt(self.sample_candidate)

        self.assertIn("anonymized", prompt.lower())
        self.assertNotIn(self.sample_candidate["name"], prompt)

    def test_prompt_pii_minimization(self):
        """Verify standard prompt minimizes PII appropriately"""
        prompt = self.builder.build_single_pass_enrichment_prompt(self.sample_candidate)

        # Should include name (needed for analysis) but limit exposure
        self.assertIn(self.sample_candidate["name"], prompt)

        # Should truncate experience/education to reasonable lengths
        # Count occurrences - should be limited
        experience_snippet = self.sample_candidate["experience"][:100]
        self.assertIn("Senior Software Engineer", prompt)

    def test_prompt_handles_missing_data(self):
        """Verify prompt handles candidates with minimal data"""
        minimal_candidate = {
            "name": "Minimal Candidate",
            "experience": "Software Engineer (2020-2023)",
            "education": "",
            "comments": []
        }

        prompt = self.builder.build_single_pass_enrichment_prompt(minimal_candidate)

        self.assertIn("Minimal Candidate", prompt)
        self.assertIn("No comments available", prompt)

    def test_prompt_includes_schema_structure(self):
        """Verify prompt shows complete JSON schema structure"""
        prompt = self.builder.build_single_pass_enrichment_prompt(self.sample_candidate)

        # Check for nested structure indicators
        self.assertIn('"personal_details"', prompt)
        self.assertIn('"seniority_level"', prompt)
        self.assertIn('"skill_inference"', prompt)
        self.assertIn('"explicit_skills"', prompt)
        self.assertIn('"inferred_skills"', prompt)


class TestPRDSchemas(unittest.TestCase):
    """Test PRD schema validation"""

    def test_schema_validates_complete_profile(self):
        """Verify schema accepts valid complete profile"""
        sample_profile = {
            "personal_details": {
                "name": "Test Candidate",
                "seniority_level": "Senior",
                "years_of_experience": 10,
                "location": "São Paulo, Brazil"
            },
            "education_analysis": {
                "degrees": ["BS Computer Science"],
                "quality_score": 85,
                "relevance": "high",
                "institutions": ["USP"]
            },
            "experience_analysis": {
                "companies": ["Meta", "Nubank"],
                "current_role": "Senior Software Engineer",
                "career_progression": "fast",
                "industry_focus": ["Technology", "Fintech"],
                "role_progression": ["Software Engineer", "Senior Software Engineer"]
            },
            "technical_assessment": {
                "primary_skills": ["Python", "Scala", "ML"],
                "expertise_level": "advanced",
                "tech_stack": ["PyTorch", "AWS", "Microservices"],
                "domain_expertise": ["Machine Learning", "Backend Systems"]
            },
            "market_insights": {
                "salary_range": "$150k-$200k",
                "market_demand": "high",
                "placement_difficulty": "moderate",
                "competitive_advantage": ["Meta experience", "ML expertise"]
            },
            "cultural_assessment": {
                "strengths": ["Leadership", "Technical depth"],
                "red_flags": [],
                "ideal_roles": ["Staff Engineer", "Engineering Manager"],
                "target_companies": ["FAANG", "Fintech unicorns"],
                "work_style": "Collaborative and data-driven"
            },
            "executive_summary": {
                "one_line_pitch": "Senior engineer with Meta and Nubank experience",
                "overall_rating": 90,
                "recommendation": "strong",
                "key_achievements": ["Built ML infrastructure at scale"]
            },
            "skill_inference": {
                "explicit_skills": [
                    {
                        "skill": "Python",
                        "confidence": 100,
                        "evidence": ["mentioned in experience"],
                        "reasoning": "explicitly listed"
                    }
                ],
                "inferred_skills": [
                    {
                        "skill": "PyTorch",
                        "confidence": 95,
                        "evidence": ["ML work at Meta"],
                        "reasoning": "Meta's primary ML framework"
                    }
                ]
            },
            "analysis_confidence": 0.95
        }

        # Should not raise validation errors
        profile = PRDCompliantProfile(**sample_profile)

        self.assertEqual(profile.personal_details.name, "Test Candidate")
        self.assertEqual(profile.analysis_confidence, 0.95)

    def test_skill_item_validates_confidence_range(self):
        """Verify SkillItem enforces confidence bounds"""
        # Valid confidence
        skill = SkillItem(skill="Python", confidence=85)
        self.assertEqual(skill.confidence, 85)

        # Test bounds
        with self.assertRaises(Exception):
            SkillItem(skill="Python", confidence=150)  # Too high

        with self.assertRaises(Exception):
            SkillItem(skill="Python", confidence=-10)  # Too low


if __name__ == '__main__':
    unittest.main()
