#!/usr/bin/env python3
"""
EXPERT PROMPT ENGINEERING FRAMEWORK
Systematically optimized prompts for consistent, high-quality LLM performance
"""

from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class PromptEngineeringPrinciples:
    """Core principles for high-quality prompt engineering"""
    
    # Role Definition Principles
    CONSISTENT_PERSONA = "You are a senior executive recruiter with 20+ years of experience placing candidates at Fortune 500 and top-tier tech companies"
    EXPERTISE_CONTEXT = "You have deep expertise in career trajectory analysis, compensation benchmarking, and talent market intelligence"
    OUTCOME_FOCUS = "Your analysis directly impacts $200K+ placement decisions and client satisfaction"
    
    # JSON Schema Enforcement
    JSON_INSTRUCTIONS = """
CRITICAL JSON REQUIREMENTS:
- Return ONLY valid JSON - no markdown, no explanations, no extra text
- Use proper JSON formatting with quotes around all strings
- Arrays must use square brackets and proper comma separation
- For missing data, use "information unavailable" - NEVER invent information
- Ensure all required fields are present with appropriate values
"""
    
    # Quality Assurance
    NO_PLACEHOLDERS = """
ZERO PLACEHOLDER TEXT ALLOWED:
- NO generic responses like "List X items" or "Based on experience"
- NO template text like "Company Name" or "Skill 1, Skill 2"
- Provide SPECIFIC analysis or state "information unavailable"
- Calculate ACTUAL numbers from available data
- Research REAL market data for salary ranges and company tiers
"""
    
    # Context Management
    CONTEXT_OPTIMIZATION = """
INTELLIGENT CONTEXT USAGE:
- Analyze ALL available information systematically
- Identify patterns and connections across data points
- Extract actionable insights from limited information
- Acknowledge information gaps explicitly
"""

class OptimizedPromptBuilder:
    """Build systematically optimized prompts for different processing stages"""
    
    def __init__(self):
        self.principles = PromptEngineeringPrinciples()
    
    def build_stage_1_enhancement_prompt(self, candidate_data: Dict[str, Any]) -> str:
        """Stage 1: Basic profile enhancement - optimized for consistency"""
        
        name = candidate_data.get('name', 'Unknown')
        experience = self._smart_truncate(candidate_data.get('experience', ''), 4000)
        education = self._smart_truncate(candidate_data.get('education', ''), 2000)
        comments = self._format_comments(candidate_data.get('comments', []))
        
        prompt = f"""{self.principles.CONSISTENT_PERSONA}.

{self.principles.EXPERTISE_CONTEXT}. {self.principles.OUTCOME_FOCUS}.

ANALYSIS MISSION:
Perform comprehensive candidate assessment for potential $200K+ placement. Extract deep career intelligence from available data.

CANDIDATE DATA:
Name: {name}
Experience History: {experience if experience.strip() else "No experience data provided"}
Education Background: {education if education.strip() else "No education data provided"}  
Recruiter Comments: {comments if comments.strip() else "No recruiter comments available"}

SYSTEMATIC ANALYSIS FRAMEWORK:
Execute analysis in this exact sequence:

1. CAREER TRAJECTORY INTELLIGENCE
   - Calculate exact years of experience from dates
   - Identify promotion patterns and velocity indicators
   - Assess career momentum and growth trajectory
   - Determine current professional level

2. TECHNICAL MARKET POSITIONING  
   - Extract and categorize technical competencies
   - Assess skill relevance and market demand
   - Identify specialization depth vs breadth
   - Evaluate technology currency

3. COMPANY PEDIGREE ANALYSIS
   - Research and tier all companies mentioned
   - Analyze progression quality across roles
   - Assess brand value and industry reputation
   - Identify trajectory patterns

4. LEADERSHIP & SCOPE ASSESSMENT
   - Identify team size and management experience
   - Assess P&L responsibility and business impact
   - Evaluate cross-functional leadership capabilities
   - Determine leadership readiness for next level

5. CULTURAL FIT INTELLIGENCE
   - Infer work environment preferences
   - Identify values alignment indicators  
   - Assess adaptability to different cultures
   - Predict optimal organizational matches

6. EXECUTIVE RECRUITING SUMMARY
   - Generate compelling one-line candidate pitch
   - Identify top 3 competitive advantages
   - Assess placement likelihood and timeline
   - Provide overall investment rating (1-100)

{self.principles.JSON_INSTRUCTIONS}

{self.principles.NO_PLACEHOLDERS}

RETURN this EXACT JSON structure:

{{
  "candidate_id": "{candidate_data.get('id', 'unknown')}",
  "processing_quality": "EXPERT_OPTIMIZED",
  "analysis_timestamp": "{self._get_timestamp()}",
  
  "career_trajectory": {{
    "current_level": "Calculate from role titles: junior|mid|senior|staff|principal|director|vp|c-level",
    "total_years_experience": "Count actual years from experience dates", 
    "years_to_current_level": "Calculate years to reach current level",
    "promotion_velocity": "slow|average|fast|exceptional based on career progression",
    "career_momentum": "accelerating|steady|slowing|stalled based on recent progression",
    "progression_quality": "linear|accelerated|stalled|declining|lateral",
    "next_logical_level": "Predict next career level based on trajectory",
    "trajectory_confidence": "Rate 1-100 confidence in trajectory assessment"
  }},
  
  "technical_positioning": {{
    "core_competencies": ["List 5-8 ACTUAL technical skills from experience"],
    "specialization_depth": "generalist|specialist|deep_specialist|thought_leader",
    "technology_currency": "cutting_edge|current|slightly_dated|outdated",
    "skill_market_demand": "very_high|high|moderate|low for this skill combination",
    "years_in_specialization": "Calculate years in primary technical area",
    "skill_differentiation": "commodity|valuable|rare|unicorn based on combination",
    "certification_status": ["List actual certifications or 'information unavailable'"]
  }},
  
  "company_pedigree": {{
    "companies_worked": ["List ACTUAL company names from experience"],
    "company_tier_progression": "improving|stable|declining based on company quality",
    "current_company_tier": "startup|scaleup|midmarket|enterprise|fortune500|faang",
    "best_company_experience": "Name of highest-tier company worked at",
    "industry_focus": ["Primary industries based on company experience"],
    "brand_recognition": "high|medium|low based on company reputation",
    "tenure_pattern": "stable|moderate|concerning based on average tenure"
  }},
  
  "leadership_scope": {{
    "has_management_experience": "true|false based on role titles/descriptions",
    "estimated_team_size": "Calculate from leadership roles or 'information unavailable'",
    "leadership_progression": "individual_contributor|emerging|proven|executive",
    "p_and_l_responsibility": "true|false|unknown based on role descriptions", 
    "cross_functional_leadership": "true|false based on role complexity",
    "leadership_readiness": "ic_focused|team_lead_ready|manager_ready|director_ready",
    "management_style_indicators": ["collaborative|directive|coaching based on clues"]
  }},
  
  "cultural_intelligence": {{
    "company_size_pattern": "startup|scaleup|enterprise based on company history",
    "work_environment_preference": "entrepreneurial|structured|flexible|corporate",
    "innovation_vs_stability": "innovation_focused|balanced|stability_focused",
    "team_vs_individual": "team_player|balanced|independent_contributor", 
    "cultural_adaptability": "high|medium|low based on company variety",
    "red_flag_environments": ["Company types that might be poor fits"],
    "optimal_culture_match": ["Company cultures where candidate would thrive"]
  }},
  
  "market_intelligence": {{
    "placement_difficulty": "easy|moderate|challenging|very_difficult",
    "estimated_timeline": "1-2_weeks|1_month|2-3_months|3+_months",
    "salary_expectation_tier": "below_market|market_rate|above_market|premium",
    "negotiation_leverage": "low|medium|high|very_high",
    "geographic_flexibility": "local_only|regional|national|international",
    "remote_work_compatibility": "remote_preferred|hybrid|office_required|flexible",
    "availability_status": "actively_looking|open_to_opportunities|passive|unavailable"
  }},
  
  "executive_summary": {{
    "one_line_pitch": "Write compelling 15-20 word summary for hiring managers",
    "top_selling_points": ["List 3 most compelling reasons to interview this candidate"],
    "competitive_advantages": ["What differentiates this candidate from similar profiles"],
    "potential_concerns": ["Honest assessment of potential placement challenges"],
    "ideal_next_role": "Specific role title and level recommendation",
    "placement_confidence": "Rate 1-100 likelihood of successful placement",
    "overall_rating": "Rate candidate 1-100 where 90+ is exceptional talent",
    "investment_recommendation": "must_interview|strong_recommend|consider|pass"
  }}
}}

{self.principles.CONTEXT_OPTIMIZATION}

Execute systematic analysis now. Focus on extracting REAL insights from available data."""

        return prompt
    
    def build_stage_2_contextual_prompt(self, enhanced_profile: Dict[str, Any]) -> str:
        """Stage 2: Contextual skill inference - optimized for intelligence"""
        
        analysis = enhanced_profile.get('enhanced_analysis', {})
        companies = self._extract_company_list(analysis)
        role_focus = self._infer_technical_focus(analysis)
        
        prompt = f"""{self.principles.CONSISTENT_PERSONA} with specialized expertise in technology career paths and company-specific skill development patterns.

CONTEXTUAL INTELLIGENCE MISSION:
Apply deep knowledge of company cultures, engineering practices, and technology adoption patterns to infer likely skills and capabilities with confidence ratings.

ENHANCED CANDIDATE PROFILE:
{self._format_enhanced_profile(enhanced_profile)}

COMPANY INTELLIGENCE DATABASE:
Apply knowledge of these specific company patterns:

GOOGLE/ALPHABET: Distributed systems, large scale infrastructure, code quality focus, technical depth, algorithm optimization
MICROSOFT: Enterprise solutions, cloud architecture, full-stack development, business integration
AMAZON: Scale optimization, cost efficiency, customer obsession, operational excellence
META: Real-time systems, social graph algorithms, performance optimization, data pipelines  
NETFLIX: Microservices, chaos engineering, A/B testing, streaming optimization
UBER: Geospatial systems, real-time matching, marketplace dynamics, growth engineering
AIRBNB: Trust & safety, international scaling, marketplace optimization, community building
STRIPE: Payment systems, API design, developer experience, financial compliance
NUBANK: FinTech innovation, mobile-first, data-driven decisions, Brazilian market expertise

CONTEXTUAL SKILL INFERENCE FRAMEWORK:

1. EXPLICIT SKILL EXTRACTION
   - Extract directly mentioned technical skills
   - Categorize by skill type and proficiency level
   - Validate against role requirements

2. CONTEXTUAL SKILL INFERENCE  
   - Apply company knowledge to infer unstated skills
   - Consider role requirements and team dynamics
   - Account for technology adoption patterns

3. CONFIDENCE CALIBRATION
   - Rate inference confidence based on evidence strength
   - Account for role specificity and company practices
   - Acknowledge uncertainty for ambiguous cases

{self.principles.JSON_INSTRUCTIONS}

{self.principles.NO_PLACEHOLDERS}

RETURN this enhanced skill analysis:

{{
  "contextual_skill_analysis": {{
    "explicit_skills": {{
      "programming_languages": ["Languages explicitly mentioned with confidence 0.9-1.0"],
      "frameworks_tools": ["Tools/frameworks directly stated"],
      "platforms_systems": ["Platforms with direct experience evidence"],
      "methodologies": ["Methodologies explicitly mentioned"]
    }},
    
    "contextual_inferences": {{
      "highly_likely_skills": [
        {{
          "skill": "Specific skill name",
          "confidence": 0.8-0.9,
          "reasoning": "Why this skill is highly likely based on company/role context",
          "evidence_type": "company_pattern|role_requirement|industry_standard"
        }}
      ],
      "moderately_likely_skills": [
        {{
          "skill": "Specific skill name", 
          "confidence": 0.6-0.7,
          "reasoning": "Context-based reasoning for moderate confidence",
          "evidence_type": "contextual_inference_type"
        }}
      ],
      "possible_skills": [
        {{
          "skill": "Specific skill name",
          "confidence": 0.4-0.5, 
          "reasoning": "Weak contextual indicators",
          "evidence_type": "weak_inference"
        }}
      ]
    }},
    
    "skill_development_trajectory": {{
      "technical_growth_pattern": "specialist_deepening|generalist_expanding|leadership_pivoting",
      "emerging_skills": ["Skills likely being developed currently"],
      "legacy_skills": ["Skills that may be outdated"],
      "skill_gaps": ["Skills missing for next-level roles"]
    }},
    
    "market_positioning": {{
      "skill_rarity_score": "Rate 1-100 how rare this skill combination is",
      "market_demand_score": "Rate 1-100 current market demand",
      "compensation_impact": "Skills that significantly impact salary expectations",
      "competitive_differentiation": "Skills that set candidate apart from peers"
    }}
  }}
}}

Execute contextual skill inference now."""

        return prompt
    
    def _smart_truncate(self, text: str, max_length: int) -> str:
        """Intelligently truncate text preserving important information"""
        if not text or len(text) <= max_length:
            return text
            
        # Try to break at sentence boundaries
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        last_newline = truncated.rfind('\n')
        
        break_point = max(last_period, last_newline)
        if break_point > max_length * 0.8:  # If we can preserve 80%+ with clean break
            return text[:break_point + 1]
        else:
            return text[:max_length] + "..."
    
    def _format_comments(self, comments: List[Dict]) -> str:
        """Format recruiter comments for prompt inclusion"""
        if not comments:
            return ""
        
        formatted = []
        for i, comment in enumerate(comments, 1):
            text = comment.get('text', '').strip()
            if text:
                formatted.append(f"Comment {i}: {text}")
        
        return "\n".join(formatted)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp for processing metadata"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _extract_company_list(self, analysis: Dict[str, Any]) -> List[str]:
        """Extract companies from enhanced analysis"""
        company_pedigree = analysis.get('company_pedigree', {})
        return company_pedigree.get('companies_worked', [])
    
    def _infer_technical_focus(self, analysis: Dict[str, Any]) -> str:
        """Infer primary technical focus from analysis"""
        tech_positioning = analysis.get('technical_positioning', {})
        competencies = tech_positioning.get('core_competencies', [])
        
        # Simple keyword matching for technical focus
        if any('machine learning' in comp.lower() or 'ml' in comp.lower() or 'ai' in comp.lower() for comp in competencies):
            return 'machine_learning'
        elif any('data' in comp.lower() for comp in competencies):
            return 'data_engineering'
        elif any('backend' in comp.lower() or 'api' in comp.lower() for comp in competencies):
            return 'backend_engineering'
        elif any('frontend' in comp.lower() or 'react' in comp.lower() or 'ui' in comp.lower() for comp in competencies):
            return 'frontend_engineering'
        else:
            return 'software_engineering'
    
    def _format_enhanced_profile(self, enhanced_profile: Dict[str, Any]) -> str:
        """Format enhanced profile for contextual analysis"""
        name = enhanced_profile.get('name', 'Unknown')
        analysis = enhanced_profile.get('enhanced_analysis', {})
        
        # Extract key information
        career = analysis.get('career_trajectory', {})
        technical = analysis.get('technical_positioning', {})
        companies = analysis.get('company_pedigree', {})
        
        return f"""
Name: {name}
Career Level: {career.get('current_level', 'Unknown')}
Experience: {career.get('total_years_experience', 'Unknown')} years
Technical Focus: {', '.join(technical.get('core_competencies', []))}
Companies: {', '.join(companies.get('companies_worked', []))}
"""

# Usage Examples and Testing
if __name__ == "__main__":
    print("🎯 Expert Prompt Engineering Framework Loaded")
    print("✅ Optimized prompts ready for systematic LLM performance")