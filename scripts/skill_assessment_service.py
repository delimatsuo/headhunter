#!/usr/bin/env python3
"""
Skill Assessment Service for Headhunter AI
Provides skill probability assessment, confidence scoring, and skill-aware analytics
"""

import json
from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime
import logging
from collections import defaultdict, Counter

from schemas import (
    IntelligentAnalysis
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class SkillConfidenceMetrics:
    """Metrics for skill confidence assessment"""
    total_skills: int = 0
    high_confidence_skills: int = 0  # 90-100%
    medium_confidence_skills: int = 0  # 70-89%
    low_confidence_skills: int = 0  # 50-69%
    average_confidence: float = 0.0
    skill_diversity_score: float = 0.0

@dataclass
class SkillMarketAnalysis:
    """Market analysis for skills"""
    high_demand_skills: List[str]
    emerging_skills: List[str]
    declining_skills: List[str]
    skill_gap_score: float
    market_alignment_score: float

class SkillAssessmentService:
    """Service for comprehensive skill assessment and analytics"""
    
    def __init__(self):
        self.skill_market_data = self._load_skill_market_data()
        self.skill_synonyms = self._load_skill_synonyms()
        
    def _load_skill_market_data(self) -> Dict[str, Dict[str, Any]]:
        """Load market demand data for skills"""
        # Mock data - in production this would come from market APIs
        return {
            "python": {"demand": "high", "growth": "stable", "salary_impact": 1.2},
            "javascript": {"demand": "high", "growth": "stable", "salary_impact": 1.15},
            "react": {"demand": "high", "growth": "growing", "salary_impact": 1.18},
            "aws": {"demand": "high", "growth": "growing", "salary_impact": 1.25},
            "kubernetes": {"demand": "high", "growth": "growing", "salary_impact": 1.3},
            "machine learning": {"demand": "high", "growth": "growing", "salary_impact": 1.4},
            "docker": {"demand": "medium", "growth": "stable", "salary_impact": 1.1},
            "sql": {"demand": "medium", "growth": "stable", "salary_impact": 1.05},
            "leadership": {"demand": "high", "growth": "stable", "salary_impact": 1.5},
            "project management": {"demand": "medium", "growth": "stable", "salary_impact": 1.2}
        }
    
    def _load_skill_synonyms(self) -> Dict[str, List[str]]:
        """Load skill synonyms for normalization"""
        return {
            "javascript": ["js", "ecmascript", "node.js", "nodejs"],
            "python": ["py", "python3"],
            "machine learning": ["ml", "ai", "artificial intelligence"],
            "kubernetes": ["k8s"],
            "docker": ["containerization", "containers"],
            "leadership": ["team lead", "people management", "team management"],
            "project management": ["pm", "scrum master", "agile"]
        }
    
    def normalize_skill(self, skill: str) -> str:
        """Normalize skill name to canonical form"""
        skill_lower = skill.lower().strip()
        
        # Check for exact matches first
        if skill_lower in self.skill_market_data:
            return skill_lower
            
        # Check synonyms
        for canonical, synonyms in self.skill_synonyms.items():
            if skill_lower in synonyms:
                return canonical
                
        return skill_lower
    
    def assess_skill_confidence(self, skill_data: Dict[str, Any]) -> int:
        """Assess confidence level for a skill based on evidence"""
        confidence = 50  # Base confidence
        
        evidence = skill_data.get('evidence', [])
        skill_name = skill_data.get('skill', '').lower()
        
        # Evidence-based confidence adjustment
        for evidence_item in evidence:
            evidence_lower = evidence_item.lower()
            
            # High confidence indicators
            if any(indicator in evidence_lower for indicator in 
                   ['explicitly listed', 'certified', 'years of experience', 'led team']):
                confidence += 20
            
            # Medium confidence indicators  
            elif any(indicator in evidence_lower for indicator in 
                     ['mentioned in experience', 'used in project', 'demonstrated']):
                confidence += 15
                
            # Lower confidence indicators
            elif any(indicator in evidence_lower for indicator in 
                     ['inferred from role', 'typical for position']):
                confidence += 10
        
        # Skill specificity adjustment
        if len(skill_name.split()) > 2:  # More specific skills get higher confidence
            confidence += 5
            
        # Market demand adjustment
        market_data = self.skill_market_data.get(self.normalize_skill(skill_name), {})
        if market_data.get('demand') == 'high':
            confidence += 5
            
        return min(confidence, 100)  # Cap at 100
    
    def categorize_skill(self, skill: str, context: str = "") -> str:
        """Categorize skill into technical, soft, domain, or leadership"""
        skill_lower = skill.lower()
        context_lower = context.lower()
        
        # Technical skills keywords
        technical_keywords = [
            'python', 'java', 'javascript', 'react', 'angular', 'vue', 'aws', 'azure',
            'docker', 'kubernetes', 'sql', 'nosql', 'mongodb', 'postgresql', 'git',
            'linux', 'windows', 'machine learning', 'ai', 'data science', 'api'
        ]
        
        # Leadership skills keywords
        leadership_keywords = [
            'leadership', 'management', 'team lead', 'mentoring', 'strategic',
            'decision making', 'vision', 'coaching', 'delegation'
        ]
        
        # Soft skills keywords
        soft_keywords = [
            'communication', 'collaboration', 'problem solving', 'adaptability',
            'creativity', 'analytical', 'attention to detail', 'time management'
        ]
        
        # Domain skills keywords (industry-specific)
        domain_keywords = [
            'fintech', 'healthcare', 'e-commerce', 'blockchain', 'compliance',
            'regulations', 'business analysis', 'market research', 'sales'
        ]
        
        if any(keyword in skill_lower for keyword in technical_keywords):
            return "technical"
        elif any(keyword in skill_lower for keyword in leadership_keywords):
            return "leadership"
        elif any(keyword in skill_lower for keyword in soft_keywords):
            return "soft"
        elif any(keyword in skill_lower for keyword in domain_keywords):
            return "domain"
        else:
            # Default categorization based on context
            if any(word in context_lower for word in ['manager', 'lead', 'director']):
                return "leadership"
            elif any(word in context_lower for word in ['developer', 'engineer', 'architect']):
                return "technical"
            else:
                return "technical"  # Default fallback
    
    def calculate_skill_metrics(self, analysis: IntelligentAnalysis) -> SkillConfidenceMetrics:
        """Calculate comprehensive skill confidence metrics"""
        all_skills = []
        
        # Collect explicit skills
        explicit = analysis.explicit_skills
        for skill_list in [explicit.technical_skills, explicit.tools_technologies, 
                          explicit.soft_skills, explicit.certifications, explicit.languages]:
            all_skills.extend([skill.confidence for skill in skill_list])
        
        # Collect inferred skills
        inferred = analysis.inferred_skills
        for skill_list in [inferred.highly_probable_skills, inferred.probable_skills,
                          inferred.likely_skills, inferred.possible_skills]:
            all_skills.extend([skill.confidence for skill in skill_list])
        
        if not all_skills:
            return SkillConfidenceMetrics()
        
        # Calculate metrics
        total_skills = len(all_skills)
        high_confidence = sum(1 for conf in all_skills if conf >= 90)
        medium_confidence = sum(1 for conf in all_skills if 70 <= conf < 90)
        low_confidence = sum(1 for conf in all_skills if 50 <= conf < 70)
        avg_confidence = sum(all_skills) / total_skills
        
        # Calculate diversity score (variety of skill types)
        skill_categories = set()
        for skill_list in [explicit.technical_skills, explicit.tools_technologies, 
                          explicit.soft_skills, explicit.certifications]:
            for skill in skill_list:
                category = self.categorize_skill(skill.skill)
                skill_categories.add(category)
        
        diversity_score = len(skill_categories) / 4.0 * 100  # Normalize to 0-100
        
        return SkillConfidenceMetrics(
            total_skills=total_skills,
            high_confidence_skills=high_confidence,
            medium_confidence_skills=medium_confidence,
            low_confidence_skills=low_confidence,
            average_confidence=avg_confidence,
            skill_diversity_score=diversity_score
        )
    
    def analyze_skill_gaps(self, analysis: IntelligentAnalysis, target_role: str = "") -> List[str]:
        """Identify skill gaps for career advancement"""
        current_skills = set()
        
        # Collect all current skills
        explicit = analysis.explicit_skills
        for skill_list in [explicit.technical_skills, explicit.tools_technologies, 
                          explicit.soft_skills, explicit.certifications]:
            current_skills.update([skill.skill.lower() for skill in skill_list])
        
        # High-demand skills for common tech roles
        role_skill_requirements = {
            "senior engineer": ["system design", "architecture", "mentoring", "code review"],
            "tech lead": ["leadership", "project management", "technical vision", "team coordination"],
            "engineering manager": ["people management", "strategic planning", "budgeting", "hiring"],
            "architect": ["system architecture", "scalability", "security", "technology evaluation"],
            "data scientist": ["statistics", "machine learning", "data visualization", "experimentation"]
        }
        
        target_role_lower = target_role.lower()
        required_skills = []
        
        for role, skills in role_skill_requirements.items():
            if role in target_role_lower:
                required_skills = skills
                break
        
        if not required_skills:
            # Default high-value skills
            required_skills = ["leadership", "system design", "mentoring", "project management"]
        
        # Find gaps
        skill_gaps = []
        for skill in required_skills:
            if skill not in current_skills:
                skill_gaps.append(skill)
        
        return skill_gaps
    
    def generate_skill_recommendations(self, analysis: IntelligentAnalysis) -> Dict[str, List[str]]:
        """Generate skill development recommendations"""
        current_skills = []
        
        # Collect all skills with categories
        explicit = analysis.explicit_skills
        for skill_list in [explicit.technical_skills, explicit.tools_technologies, 
                          explicit.soft_skills, explicit.certifications]:
            for skill in skill_list:
                category = self.categorize_skill(skill.skill)
                current_skills.append((skill.skill.lower(), category))
        
        recommendations = {
            "next_level_skills": [],
            "complementary_skills": [],
            "emerging_skills": [],
            "leadership_skills": []
        }
        
        skill_counts = Counter([category for _, category in current_skills])
        current_skill_names = set([skill for skill, _ in current_skills])
        
        # Next level skills (advanced versions of current skills)
        if "python" in current_skill_names:
            recommendations["next_level_skills"].extend(["advanced python", "python architecture"])
        if "javascript" in current_skill_names:
            recommendations["next_level_skills"].extend(["advanced javascript", "node.js"])
        
        # Complementary skills
        if skill_counts.get("technical", 0) > 3:
            recommendations["complementary_skills"].extend(["system design", "architecture"])
        if "aws" in current_skill_names:
            recommendations["complementary_skills"].extend(["terraform", "kubernetes"])
        
        # Emerging skills
        recommendations["emerging_skills"] = ["ai/ml", "blockchain", "edge computing", "serverless"]
        
        # Leadership skills
        if skill_counts.get("technical", 0) > 5:
            recommendations["leadership_skills"] = ["mentoring", "technical leadership", "team coordination"]
        
        return recommendations
    
    def create_skill_search_profile(self, analysis: IntelligentAnalysis) -> Dict[str, Any]:
        """Create optimized search profile for skill-based matching"""
        profile = {
            "primary_skills": [],
            "secondary_skills": [],
            "skill_confidence_scores": {},
            "skill_categories": defaultdict(list),
            "search_keywords": [],
            "skill_depth_indicators": {}
        }
        
        all_skills = []
        
        # Process explicit skills
        explicit = analysis.explicit_skills
        for skill_category, skill_list in [
            ("technical", explicit.technical_skills),
            ("tools", explicit.tools_technologies),
            ("soft", explicit.soft_skills),
            ("certifications", explicit.certifications),
            ("languages", explicit.languages)
        ]:
            for skill in skill_list:
                normalized_skill = self.normalize_skill(skill.skill)
                confidence = skill.confidence
                category = self.categorize_skill(skill.skill)
                
                all_skills.append((normalized_skill, confidence, category))
                profile["skill_confidence_scores"][normalized_skill] = confidence
                profile["skill_categories"][category].append(normalized_skill)
                
                # High confidence skills become primary
                if confidence >= 85:
                    profile["primary_skills"].append(normalized_skill)
                elif confidence >= 70:
                    profile["secondary_skills"].append(normalized_skill)
        
        # Process inferred skills
        inferred = analysis.inferred_skills
        for skill_list in [inferred.highly_probable_skills, inferred.probable_skills]:
            for skill in skill_list:
                normalized_skill = self.normalize_skill(skill.skill)
                confidence = skill.confidence
                category = getattr(skill, 'skill_category', 'technical')
                
                if normalized_skill not in profile["skill_confidence_scores"]:
                    profile["skill_confidence_scores"][normalized_skill] = confidence
                    profile["skill_categories"][category].append(normalized_skill)
                    
                    if confidence >= 80:
                        profile["secondary_skills"].append(normalized_skill)
        
        # Generate search keywords
        profile["search_keywords"] = (
            profile["primary_skills"][:10] + 
            profile["secondary_skills"][:10]
        )
        
        # Add skill depth indicators
        for skill, confidence, category in all_skills:
            if confidence >= 90:
                profile["skill_depth_indicators"][skill] = "expert"
            elif confidence >= 80:
                profile["skill_depth_indicators"][skill] = "advanced"
            elif confidence >= 70:
                profile["skill_depth_indicators"][skill] = "intermediate"
            else:
                profile["skill_depth_indicators"][skill] = "beginner"
        
        return dict(profile)  # Convert defaultdict to regular dict
    
    def calculate_skill_match_score(self, candidate_profile: Dict[str, Any], 
                                  job_requirements: List[str]) -> float:
        """Calculate skill match score between candidate and job requirements"""
        if not job_requirements:
            return 0.0
        
        candidate_skills = candidate_profile.get("skill_confidence_scores", {})
        total_score = 0.0
        max_score = 0.0
        
        for required_skill in job_requirements:
            normalized_required = self.normalize_skill(required_skill)
            max_score += 100  # Each skill can contribute max 100 points
            
            # Direct match
            if normalized_required in candidate_skills:
                confidence = candidate_skills[normalized_required]
                total_score += confidence
            else:
                # Check for related skills (synonyms)
                for candidate_skill, confidence in candidate_skills.items():
                    if self._skills_related(normalized_required, candidate_skill):
                        total_score += confidence * 0.7  # Partial match
                        break
        
        return (total_score / max_score) * 100 if max_score > 0 else 0.0
    
    def _skills_related(self, skill1: str, skill2: str) -> bool:
        """Check if two skills are related"""
        # Simple relatedness check - in production this could use embeddings
        skill1_words = set(skill1.lower().split())
        skill2_words = set(skill2.lower().split())
        
        # Check for word overlap
        if skill1_words & skill2_words:
            return True
        
        # Check skill families
        skill_families = [
            {"python", "django", "flask", "fastapi"},
            {"javascript", "react", "angular", "vue", "node.js"},
            {"aws", "azure", "gcp", "cloud"},
            {"docker", "kubernetes", "containerization"},
            {"leadership", "management", "mentoring"}
        ]
        
        for family in skill_families:
            if skill1 in family and skill2 in family:
                return True
        
        return False

    def export_skill_assessment(self, analysis: IntelligentAnalysis, 
                              output_file: str = None) -> Dict[str, Any]:
        """Export comprehensive skill assessment report"""
        metrics = self.calculate_skill_metrics(analysis)
        search_profile = self.create_skill_search_profile(analysis)
        skill_gaps = self.analyze_skill_gaps(analysis)
        recommendations = self.generate_skill_recommendations(analysis)
        
        report = {
            "assessment_timestamp": datetime.now().isoformat(),
            "confidence_metrics": {
                "total_skills": metrics.total_skills,
                "high_confidence_skills": metrics.high_confidence_skills,
                "medium_confidence_skills": metrics.medium_confidence_skills,
                "low_confidence_skills": metrics.low_confidence_skills,
                "average_confidence": round(metrics.average_confidence, 2),
                "skill_diversity_score": round(metrics.skill_diversity_score, 2)
            },
            "skill_profile": search_profile,
            "skill_gaps": skill_gaps,
            "recommendations": recommendations,
            "market_insights": self._generate_market_insights(search_profile)
        }
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"Skill assessment report saved to {output_file}")
        
        return report
    
    def _generate_market_insights(self, skill_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Generate market insights based on skill profile"""
        primary_skills = skill_profile.get("primary_skills", [])
        
        high_demand_count = 0
        total_salary_impact = 0.0
        
        for skill in primary_skills:
            market_data = self.skill_market_data.get(skill, {})
            if market_data.get("demand") == "high":
                high_demand_count += 1
            total_salary_impact += market_data.get("salary_impact", 1.0)
        
        avg_salary_impact = total_salary_impact / len(primary_skills) if primary_skills else 1.0
        
        return {
            "high_demand_skills_count": high_demand_count,
            "market_demand_percentage": round((high_demand_count / len(primary_skills)) * 100, 1) if primary_skills else 0,
            "estimated_salary_multiplier": round(avg_salary_impact, 2),
            "market_positioning": "strong" if high_demand_count >= 3 else "moderate" if high_demand_count >= 1 else "developing"
        }