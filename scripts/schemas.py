from typing import List, Optional, Union
from pydantic import BaseModel, Field


class SkillItem(BaseModel):
    skill: str
    confidence: Optional[float] = Field(default=None, ge=0, le=100)
    reasoning: Optional[str] = None
    evidence: Optional[List[str]] = None
    category: Optional[str] = None


class ExplicitSkills(BaseModel):
    technical_skills: Optional[List[SkillItem]] = None
    tools_technologies: Optional[List[SkillItem]] = None
    soft_skills: Optional[List[SkillItem]] = None
    certifications: Optional[List[SkillItem]] = None
    languages: Optional[List[SkillItem]] = None


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
    overall_rating: Optional[Union[str, float, int]] = None
    recommendation: Optional[str] = None


class CompositeSkillProfile(BaseModel):
    primary_expertise: Optional[List[SkillItem]] = None
    secondary_expertise: Optional[List[SkillItem]] = None
    domain_specialization: Optional[str] = None


class IntelligentAnalysis(BaseModel):
    explicit_skills: Optional[ExplicitSkills] = None
    inferred_skills: Optional[InferredSkills] = None
    career_trajectory_analysis: Optional[CareerTrajectory] = None
    market_positioning: Optional[MarketPositioning] = None
    recruiter_insights: Optional[RecruiterInsights] = None
    composite_skill_profile: Optional[CompositeSkillProfile] = None

    # Allow additional fields from the LLM that we do not strictly validate yet
    model_config = {"extra": "allow"}

