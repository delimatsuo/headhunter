from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SkillItem(BaseModel):
    skill: str
    confidence: Optional[float] = Field(default=None, ge=0, le=100)
    reasoning: Optional[str] = None
    evidence: Optional[List[str]] = None
    category: Optional[str] = None


class ExplicitSkills(BaseModel):
    technical_skills: Optional[List[str]] = None
    tools_technologies: Optional[List[str]] = None
    soft_skills: Optional[List[str]] = None


class InferredSkills(BaseModel):
    highly_probable_skills: Optional[List[SkillItem]] = None
    probable_skills: Optional[List[SkillItem]] = None
    likely_skills: Optional[List[SkillItem]] = None
    possible_skills: Optional[List[SkillItem]] = None


class CareerTrajectory(BaseModel):
    current_level: Optional[str] = None
    years_experience: Optional[float] = None
    promotion_velocity: Optional[str] = None


class MarketPositioning(BaseModel):
    skill_market_value: Optional[str] = None
    skill_rarity: Optional[str] = None


class RecruiterInsights(BaseModel):
    overall_rating: Optional[str] = None
    recommendation: Optional[str] = None


class CompositeSkillProfile(BaseModel):
    primary_expertise: Optional[List[str]] = None
    secondary_expertise: Optional[List[str]] = None


class IntelligentAnalysis(BaseModel):
    explicit_skills: Optional[ExplicitSkills] = None
    inferred_skills: Optional[InferredSkills] = None
    career_trajectory_analysis: Optional[CareerTrajectory] = None
    market_positioning: Optional[MarketPositioning] = None
    recruiter_insights: Optional[RecruiterInsights] = None
    composite_skill_profile: Optional[CompositeSkillProfile] = None

    # Allow additional fields from the LLM that we do not strictly validate yet
    model_config = {"extra": "allow"}

