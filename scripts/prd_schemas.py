"""
PRD-Compliant Schemas for Together AI Single-Pass Enrichment

This module defines Pydantic schemas that exactly match the PRD requirements
(lines 61-72) for AI-Generated Candidate Profiles via Together AI.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PersonalDetails(BaseModel):
    """Minimal personal information extracted from profile"""
    name: Optional[str] = Field(default=None, description="Candidate name")
    seniority_level: Optional[str] = Field(default=None, description="Career level (Junior/Mid/Senior/Principal/Executive)")
    years_of_experience: Optional[int] = Field(default=None, description="Total years of professional experience")
    location: Optional[str] = Field(default=None, description="Current location (city/country level only)")


class EducationAnalysis(BaseModel):
    """Analysis of educational background"""
    degrees: Optional[List[str]] = Field(default=None, description="Degrees obtained (e.g., 'BS Computer Science')")
    quality_score: Optional[int] = Field(default=None, ge=0, le=100, description="Educational quality (0-100)")
    relevance: Optional[str] = Field(default=None, description="Relevance to technical careers (high/medium/low)")
    institutions: Optional[List[str]] = Field(default=None, description="Educational institutions attended")


class ExperienceAnalysis(BaseModel):
    """Analysis of work experience and career progression"""
    companies: Optional[List[str]] = Field(default=None, description="Companies worked at")
    current_role: Optional[str] = Field(default=None, description="Most recent role title")
    career_progression: Optional[str] = Field(default=None, description="Career trajectory (fast/steady/lateral)")
    industry_focus: Optional[List[str]] = Field(default=None, description="Primary industries")
    role_progression: Optional[List[str]] = Field(default=None, description="Chronological role titles")


class TechnicalAssessment(BaseModel):
    """Technical skills and expertise evaluation"""
    primary_skills: Optional[List[str]] = Field(default=None, description="Core technical competencies")
    expertise_level: Optional[str] = Field(default=None, description="Overall technical level (beginner/intermediate/advanced/expert)")
    tech_stack: Optional[List[str]] = Field(default=None, description="Technologies and frameworks")
    domain_expertise: Optional[List[str]] = Field(default=None, description="Domain-specific knowledge areas")


class MarketInsights(BaseModel):
    """Market positioning and salary expectations"""
    salary_range: Optional[str] = Field(default=None, description="Expected salary range (e.g., '$120k-$180k')")
    market_demand: Optional[str] = Field(default=None, description="Market demand for profile (high/medium/low)")
    placement_difficulty: Optional[str] = Field(default=None, description="How hard to place (easy/moderate/difficult)")
    competitive_advantage: Optional[List[str]] = Field(default=None, description="Key differentiators")


class CulturalAssessment(BaseModel):
    """Cultural fit and recruiter recommendations"""
    strengths: Optional[List[str]] = Field(default=None, description="Key professional strengths")
    red_flags: Optional[List[str]] = Field(default=None, description="Potential concerns")
    ideal_roles: Optional[List[str]] = Field(default=None, description="Best-fit role types")
    target_companies: Optional[List[str]] = Field(default=None, description="Suggested target companies")
    work_style: Optional[str] = Field(default=None, description="Preferred work environment")


class ExecutiveSummary(BaseModel):
    """High-level summary for decision makers"""
    one_line_pitch: Optional[str] = Field(default=None, description="Concise value proposition")
    overall_rating: Optional[int] = Field(default=None, ge=0, le=100, description="Overall candidate score (0-100)")
    recommendation: Optional[str] = Field(default=None, description="Hiring recommendation (strong/consider/pass)")
    key_achievements: Optional[List[str]] = Field(default=None, description="Notable accomplishments")


class SkillItem(BaseModel):
    """Individual skill with confidence and evidence"""
    skill: str
    confidence: float = Field(ge=0, le=100, description="Confidence score (0-100)")
    evidence: Optional[List[str]] = Field(default=None, description="Supporting evidence from profile")
    reasoning: Optional[str] = Field(default=None, description="Why this skill was inferred")


class SkillInference(BaseModel):
    """Explicit and inferred skills with confidence scoring"""
    explicit_skills: Optional[List[SkillItem]] = Field(
        default=None,
        description="Skills explicitly mentioned (confidence=100)"
    )
    inferred_skills: Optional[List[SkillItem]] = Field(
        default=None,
        description="Skills inferred from context (confidence 0-100)"
    )


class PRDCompliantProfile(BaseModel):
    """
    Complete candidate profile matching PRD requirements (lines 61-72)

    Used for single-pass Together AI enrichment with Qwen 2.5 32B Instruct.
    """
    personal_details: PersonalDetails
    education_analysis: EducationAnalysis
    experience_analysis: ExperienceAnalysis
    technical_assessment: TechnicalAssessment
    market_insights: MarketInsights
    cultural_assessment: CulturalAssessment
    executive_summary: ExecutiveSummary
    skill_inference: SkillInference
    analysis_confidence: float = Field(
        ge=0,
        le=1,
        description="Overall confidence in analysis (0-1), low_content gets demotion"
    )

    # processing_metadata added separately by processor (not from LLM)

    model_config = {"extra": "allow"}  # Allow additional fields from LLM
