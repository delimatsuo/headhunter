from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class SkillWithEvidence(BaseModel):
    skill: str
    confidence: int = Field(default=100, ge=0, le=100)
    evidence: List[str] = Field(default_factory=list)


class ExplicitSkills(BaseModel):
    technical_skills: List[SkillWithEvidence] = Field(default_factory=list)
    tools_technologies: List[SkillWithEvidence] = Field(default_factory=list)
    soft_skills: List[SkillWithEvidence] = Field(default_factory=list)
    certifications: List[SkillWithEvidence] = Field(default_factory=list)
    languages: List[SkillWithEvidence] = Field(default_factory=list)


class InferredSkillItem(BaseModel):
    skill: str
    confidence: int = Field(ge=0, le=100)
    reasoning: str
    skill_category: str = Field(default="technical")


class InferredSkills(BaseModel):
    highly_probable_skills: List[InferredSkillItem] = Field(default_factory=list)
    probable_skills: List[InferredSkillItem] = Field(default_factory=list)
    likely_skills: List[InferredSkillItem] = Field(default_factory=list)
    possible_skills: List[InferredSkillItem] = Field(default_factory=list)


class CurrentRoleCompetencies(BaseModel):
    role: str
    core_competencies: List[str] = Field(default_factory=list)
    typical_tools: List[str] = Field(default_factory=list)
    domain_knowledge: List[str] = Field(default_factory=list)


class RoleBasedCompetencies(BaseModel):
    current_role_competencies: CurrentRoleCompetencies
    historical_competencies: List[CurrentRoleCompetencies] = Field(default_factory=list)


class CompanySpecific(BaseModel):
    company: Optional[str] = None
    typical_stack: List[str] = Field(default_factory=list)
    methodologies: List[str] = Field(default_factory=list)
    scale_experience: Optional[str] = None


class CompanyContextSkills(BaseModel):
    company_specific: List[CompanySpecific] = Field(default_factory=list)
    industry_skills: List[str] = Field(default_factory=list)


class SkillTimelineItem(BaseModel):
    skill: str
    first_used: str = Field(default="unknown")
    last_used: str = Field(default="current")
    frequency: str = Field(default="medium")
    recency_score: int = Field(default=50, ge=0, le=100)

class SkillDepthAnalysis(BaseModel):
    beginner_skills: List[str] = Field(default_factory=list)
    intermediate_skills: List[str] = Field(default_factory=list)
    advanced_skills: List[str] = Field(default_factory=list)
    expert_skills: List[str] = Field(default_factory=list)

class SkillEvolutionAnalysis(BaseModel):
    skill_trajectory: str
    emerging_skills: List[str] = Field(default_factory=list)
    skill_gaps: List[str] = Field(default_factory=list)
    learning_velocity: str
    skill_currency: str
    skill_timeline: List[SkillTimelineItem] = Field(default_factory=list)
    skill_depth_analysis: SkillDepthAnalysis


class SkillWithMarketDemand(BaseModel):
    skill: str
    confidence: int = Field(ge=0, le=100)
    market_demand: str = Field(default="medium")

class SkillCategories(BaseModel):
    technical_skills: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    domain_skills: List[str] = Field(default_factory=list)
    leadership_skills: List[str] = Field(default_factory=list)

class TransferableSkill(BaseModel):
    skill: str
    transferability: str = Field(default="medium")
    target_industries: List[str] = Field(default_factory=list)

class CompositeSkillProfile(BaseModel):
    primary_expertise: List[SkillWithMarketDemand] = Field(default_factory=list)
    secondary_expertise: List[SkillWithMarketDemand] = Field(default_factory=list)
    domain_specialization: str
    skill_breadth: str
    unique_combination: List[str] = Field(default_factory=list)
    skill_categories: SkillCategories
    transferable_skills: List[TransferableSkill] = Field(default_factory=list)


class CareerTrajectory(BaseModel):
    current_level: str
    years_experience: int
    promotion_velocity: str
    career_progression: str
    performance_indicator: str

class LeadershipScope(BaseModel):
    has_leadership: bool = False
    team_size: Optional[int] = None
    leadership_level: Optional[str] = None
    leadership_style: Optional[List[str]] = None
    mentorship_experience: Optional[bool] = None


class CompanyPedigree(BaseModel):
    tier_level: Optional[str] = None
    company_types: Optional[List[str]] = None
    brand_recognition: Optional[str] = None
    recent_companies: Optional[List[str]] = None


class Education(BaseModel):
    highest_degree: Optional[str] = None
    institutions: Optional[List[str]] = None
    fields_of_study: Optional[List[str]] = None


class ResumeAnalysis(BaseModel):
    career_trajectory: CareerTrajectory
    leadership_scope: LeadershipScope
    company_pedigree: CompanyPedigree
    years_experience: int
    technical_skills: List[str] = Field(default_factory=list)
    soft_skills: Optional[List[str]] = None
    education: Optional[Education] = None
    cultural_signals: Optional[List[str]] = None


class MarketPositioning(BaseModel):
    skill_market_value: str
    skill_rarity: str
    competitive_advantage: List[str] = Field(default_factory=list)
    placement_difficulty: str
    ideal_next_roles: List[str] = Field(default_factory=list)
    salary_range: str


class RecruiterInsights(BaseModel):
    overall_rating: str
    recommendation: str
    confidence_in_assessment: Optional[str] = None
    verification_needed: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    selling_points: List[str] = Field(default_factory=list)
    interview_focus: List[str] = Field(default_factory=list)
    one_line_pitch: Optional[str] = None


class SkillAssessmentMetadata(BaseModel):
    total_skills: int = 0
    average_confidence: float = 0.0
    skills_by_category: dict = Field(default_factory=dict)
    confidence_distribution: dict = Field(default_factory=dict)
    assessment_quality_score: int = Field(default=0, ge=0, le=100)
    processing_timestamp: str = ""
    processor_version: str = "v1.0"


class SkillAssessment(BaseModel):
    """Comprehensive skill assessment with confidence scoring"""
    candidate_id: str
    explicit_skills: ExplicitSkills
    inferred_skills: InferredSkills
    role_based_competencies: RoleBasedCompetencies
    company_context_skills: CompanyContextSkills
    skill_evolution_analysis: SkillEvolutionAnalysis
    composite_skill_profile: CompositeSkillProfile
    metadata: SkillAssessmentMetadata
    
    def get_all_skills_with_confidence(self) -> List[dict]:
        """Get all skills from all sources with confidence scores"""
        all_skills = []
        
        # Add explicit skills (100% confidence)
        for category, skills in self.explicit_skills.dict().items():
            for skill_item in skills:
                if isinstance(skill_item, dict):
                    all_skills.append({
                        'skill': skill_item['skill'],
                        'confidence': skill_item.get('confidence', 100),
                        'source': 'explicit',
                        'category': category,
                        'evidence': skill_item.get('evidence', [])
                    })
        
        # Add inferred skills with their confidence scores
        for confidence_level, skills in self.inferred_skills.dict().items():
            for skill_item in skills:
                if isinstance(skill_item, dict):
                    all_skills.append({
                        'skill': skill_item['skill'],
                        'confidence': skill_item.get('confidence', 50),
                        'source': 'inferred',
                        'category': skill_item.get('skill_category', 'technical'),
                        'confidence_level': confidence_level,
                        'reasoning': skill_item.get('reasoning', '')
                    })
        
        return all_skills


class IntelligentAnalysis(BaseModel):
    explicit_skills: ExplicitSkills
    inferred_skills: InferredSkills
    role_based_competencies: RoleBasedCompetencies
    company_context_skills: CompanyContextSkills
    skill_evolution_analysis: SkillEvolutionAnalysis
    composite_skill_profile: CompositeSkillProfile
    career_trajectory_analysis: CareerTrajectory
    market_positioning: MarketPositioning
    recruiter_insights: RecruiterInsights
