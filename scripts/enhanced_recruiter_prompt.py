"""
Enhanced Recruiter-Grade Skill Inference Prompt
Based on 2024-2025 LLM recruitment research best practices
"""

def build_enhanced_skill_inference_prompt(candidate_data: dict) -> str:
    """
    Build recruiter-grade prompt with:
    - Chain-of-thought reasoning
    - Few-shot examples
    - Company context awareness
    - Explicit vs inferred skill separation
    """

    name = candidate_data.get("name", "Unknown")
    experience = candidate_data.get("experience", "")
    education = candidate_data.get("education", "")

    prompt = f"""You are a senior tech recruiter with 15+ years of experience. You have deep knowledge of tech stacks, company engineering cultures, and can infer likely skills based on roles and companies.

CANDIDATE: {name}

EXPERIENCE:
{experience}

EDUCATION:
{education}

YOUR TASK:
Analyze this candidate like a senior recruiter would. Separate what they EXPLICITLY mention from what you can INFER based on company context, role requirements, and industry knowledge.

EXAMPLES OF RECRUITER-GRADE INFERENCE:

Example 1:
- Explicit: "Senior ML Engineer at Meta (2020-2023)"
- Inferred Skills (high confidence 90%+):
  * PyTorch (Meta's primary ML framework)
  * Large-scale distributed systems (Meta operates at billions of users)
  * A/B testing and experimentation platforms
  * Python for ML pipelines
- Reasoning: Meta is known for PyTorch, operates massive infrastructure, culture of data-driven decisions

Example 2:
- Explicit: "Lead Data Engineer at Nubank (2021-current)"
- Inferred Skills (high confidence 90%+):
  * Scala/Clojure (Nubank's primary languages)
  * AWS (Nubank runs on AWS)
  * Microservices architecture (fintech scalability requirements)
  * PCI-DSS compliance knowledge (financial data regulations)
- Reasoning: Nubank is known for functional programming, cloud-native fintech at scale

Example 3:
- Explicit: "Machine Learning Engineer at Kunumi (2018-2020)"
- Inferred Skills (moderate confidence 75-90%):
  * Python/TensorFlow (standard ML stack for small companies)
  * Model deployment challenges (startup scale constraints)
  * Full-stack ML work (small team, wear many hats)
- Reasoning: Smaller companies typically use standard tools, engineers handle broader scope

NOW ANALYZE THE CANDIDATE ABOVE:

Return ONLY valid JSON with this EXACT structure (no markdown, no code blocks):

{{
  "explicit_skills": {{
    "technical_skills": [
      {{"skill": "Python", "confidence": 100, "evidence": ["mentioned in skills section"]}}
    ],
    "tools_technologies": [
      {{"skill": "TensorFlow", "confidence": 100, "evidence": ["used in project X"]}}
    ],
    "soft_skills": [
      {{"skill": "Leadership", "confidence": 100, "evidence": ["Led team of 5"]}}
    ]
  }},
  "inferred_skills": {{
    "highly_probable_skills": [
      {{
        "skill": "AWS",
        "confidence": 95,
        "reasoning": "Lead Engineer at Nubank (2021-current) - Nubank runs on AWS infrastructure",
        "skill_category": "technical"
      }}
    ],
    "probable_skills": [
      {{
        "skill": "Kubernetes",
        "confidence": 80,
        "reasoning": "Cloud-native fintech at scale typically uses container orchestration",
        "skill_category": "technical"
      }}
    ]
  }},
  "company_context_skills": {{
    "company_specific": [
      {{
        "company": "Nubank",
        "typical_stack": ["Scala", "Clojure", "AWS", "Microservices"],
        "confidence": 90,
        "evidence": "Well-documented tech stack for this company"
      }}
    ]
  }},
  "career_trajectory_analysis": {{
    "current_level": "Senior/Lead",
    "years_experience": 12,
    "progression_speed": "fast"
  }},
  "composite_skill_profile": {{
    "primary_expertise": [
      {{"skill": "Machine Learning", "confidence": 95, "market_demand": "high"}}
    ],
    "secondary_expertise": [
      {{"skill": "Data Engineering", "confidence": 85, "market_demand": "high"}}
    ],
    "domain_specialization": "Fintech ML/Data"
  }},
  "market_positioning": {{
    "skill_market_value": "high",
    "skill_rarity": "moderate"
  }},
  "recruiter_insights": {{
    "overall_rating": "A",
    "recommendation": "strong_hire",
    "key_selling_points": ["Fintech experience at unicorn", "ML + Data engineering breadth"]
  }}
}}

CRITICAL RULES:
1. Use your knowledge of companies (Meta, Google, Nubank, etc.) to infer tech stacks
2. Confidence scores: 100% = explicit mention, 90%+ = company well-known for this tech, 75-90% = industry standard for this role
3. Provide specific reasoning for each inferred skill
4. Separate what's stated from what's inferred
5. Return ONLY the JSON object, no other text
"""

    return prompt
