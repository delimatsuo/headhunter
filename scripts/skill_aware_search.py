#!/usr/bin/env python3
"""
Skill-Aware Search Ranking Algorithm for Headhunter AI
Combines vector similarity with skill probability assessment for intelligent candidate ranking
"""

from typing import Dict, List, Any
from dataclasses import dataclass
import logging
import json

from skill_assessment_service import SkillAssessmentService
from schemas import IntelligentAnalysis

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class SearchQuery:
    """Structured search query with skill requirements"""
    text_query: str
    required_skills: List[str] = None
    preferred_skills: List[str] = None
    minimum_confidence: int = 70
    skill_categories: List[str] = None  # technical, soft, leadership, domain
    experience_level: str = None  # entry, mid, senior, executive
    location_preference: str = None

@dataclass
class CandidateScore:
    """Comprehensive candidate scoring"""
    candidate_id: str
    overall_score: float
    skill_match_score: float
    confidence_score: float
    vector_similarity_score: float
    experience_match_score: float
    skill_breakdown: Dict[str, float]
    ranking_factors: Dict[str, Any]

@dataclass
class SearchResult:
    """Search result with detailed scoring"""
    candidates: List[CandidateScore]
    query_analysis: Dict[str, Any]
    search_metadata: Dict[str, Any]

class SkillAwareSearchRanker:
    """Advanced search ranking with skill probability assessment"""
    
    def __init__(self):
        self.skill_service = SkillAssessmentService()
        self.weight_config = {
            "skill_match": 0.4,      # 40% - Primary importance
            "confidence": 0.25,      # 25% - Skill confidence 
            "vector_similarity": 0.2, # 20% - Semantic similarity
            "experience_level": 0.15  # 15% - Experience matching
        }
        
    def parse_search_query(self, query_text: str) -> SearchQuery:
        """Parse natural language search query into structured format"""
        query_lower = query_text.lower()
        
        # Extract skills from query
        technical_keywords = [
            'python', 'java', 'javascript', 'react', 'angular', 'vue', 'aws', 'azure',
            'docker', 'kubernetes', 'sql', 'nosql', 'machine learning', 'ai', 'ml'
        ]
        
        leadership_keywords = [
            'leader', 'manager', 'lead', 'director', 'vp', 'cto', 'ceo', 'team lead'
        ]
        
        experience_keywords = {
            'entry': ['junior', 'entry', 'graduate', 'new grad'],
            'mid': ['mid', 'intermediate', '3-5 years', 'mid-level'],
            'senior': ['senior', 'sr', '5+ years', 'experienced'],
            'executive': ['executive', 'director', 'vp', 'c-level', 'head of']
        }
        
        # Identify required skills
        required_skills = []
        preferred_skills = []
        skill_categories = []
        experience_level = None
        
        for keyword in technical_keywords:
            if keyword in query_lower:
                required_skills.append(keyword)
                if 'technical' not in skill_categories:
                    skill_categories.append('technical')
        
        for keyword in leadership_keywords:
            if keyword in query_lower:
                required_skills.append('leadership')
                if 'leadership' not in skill_categories:
                    skill_categories.append('leadership')
        
        # Determine experience level
        for level, keywords in experience_keywords.items():
            if any(kw in query_lower for kw in keywords):
                experience_level = level
                break
        
        # Extract minimum confidence if mentioned
        minimum_confidence = 70
        if 'expert' in query_lower or 'advanced' in query_lower:
            minimum_confidence = 85
        elif 'experienced' in query_lower:
            minimum_confidence = 80
        
        return SearchQuery(
            text_query=query_text,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            minimum_confidence=minimum_confidence,
            skill_categories=skill_categories,
            experience_level=experience_level
        )
    
    def score_candidate(self, candidate_data: Dict[str, Any], 
                       search_query: SearchQuery,
                       vector_similarity: float = 0.0) -> CandidateScore:
        """Score a candidate against search query"""
        
        candidate_id = candidate_data.get('candidate_id', 'unknown')
        analysis = candidate_data.get('recruiter_analysis', {})
        
        # Create skill profile
        if isinstance(analysis, dict):
            # Convert dict to IntelligentAnalysis if needed
            try:
                analysis_obj = IntelligentAnalysis.model_validate(analysis)
            except Exception as e:
                logger.warning(f"Failed to parse analysis for {candidate_id}: {e}")
                return self._create_default_score(candidate_id, vector_similarity)
        else:
            analysis_obj = analysis
        
        skill_profile = self.skill_service.create_skill_search_profile(analysis_obj)
        
        # Calculate component scores
        skill_match_score = self._calculate_skill_match(skill_profile, search_query)
        confidence_score = self._calculate_confidence_score(skill_profile, search_query)
        experience_score = self._calculate_experience_match(analysis_obj, search_query)
        
        # Calculate skill breakdown
        skill_breakdown = self._analyze_skill_breakdown(skill_profile, search_query)
        
        # Calculate overall score
        overall_score = (
            skill_match_score * self.weight_config["skill_match"] +
            confidence_score * self.weight_config["confidence"] +
            vector_similarity * self.weight_config["vector_similarity"] +
            experience_score * self.weight_config["experience_level"]
        )
        
        # Create ranking factors for transparency
        ranking_factors = {
            "skill_match_details": skill_breakdown,
            "confidence_analysis": self._analyze_confidence_distribution(skill_profile),
            "experience_match": experience_score,
            "vector_similarity": vector_similarity,
            "weight_config": self.weight_config
        }
        
        return CandidateScore(
            candidate_id=candidate_id,
            overall_score=overall_score,
            skill_match_score=skill_match_score,
            confidence_score=confidence_score,
            vector_similarity_score=vector_similarity,
            experience_match_score=experience_score,
            skill_breakdown=skill_breakdown,
            ranking_factors=ranking_factors
        )
    
    def _calculate_skill_match(self, skill_profile: Dict[str, Any], 
                              search_query: SearchQuery) -> float:
        """Calculate skill match score"""
        if not search_query.required_skills:
            return 80.0  # Default score when no specific skills required
        
        # Use SkillAssessmentService for detailed matching
        return self.skill_service.calculate_skill_match_score(
            skill_profile, search_query.required_skills
        )
    
    def _calculate_confidence_score(self, skill_profile: Dict[str, Any], 
                                   search_query: SearchQuery) -> float:
        """Calculate average confidence score for relevant skills"""
        skill_scores = skill_profile.get("skill_confidence_scores", {})
        
        if not search_query.required_skills:
            # Use all skills for general confidence assessment
            if skill_scores:
                return sum(skill_scores.values()) / len(skill_scores)
            return 50.0
        
        # Focus on required skills
        relevant_scores = []
        for skill in search_query.required_skills:
            normalized_skill = self.skill_service.normalize_skill(skill)
            if normalized_skill in skill_scores:
                score = skill_scores[normalized_skill]
                if score >= search_query.minimum_confidence:
                    relevant_scores.append(score)
                else:
                    relevant_scores.append(score * 0.5)  # Penalty for below threshold
        
        if relevant_scores:
            return sum(relevant_scores) / len(relevant_scores)
        
        return 30.0  # Low score if no matching skills found
    
    def _calculate_experience_match(self, analysis: IntelligentAnalysis, 
                                   search_query: SearchQuery) -> float:
        """Calculate experience level match score"""
        if not search_query.experience_level:
            return 75.0  # Neutral score when no experience requirement
        
        # Extract years of experience
        years_exp = getattr(analysis.career_trajectory_analysis, 'years_experience', 0)
        current_level = getattr(analysis.career_trajectory_analysis, 'current_level', '').lower()
        
        # Map experience levels to year ranges
        experience_mapping = {
            'entry': (0, 3),
            'mid': (3, 7),
            'senior': (7, 12),
            'executive': (12, 50)
        }
        
        target_range = experience_mapping.get(search_query.experience_level, (0, 50))
        
        # Calculate score based on experience match
        if target_range[0] <= years_exp <= target_range[1]:
            return 100.0
        elif years_exp < target_range[0]:
            # Under-experienced
            gap = target_range[0] - years_exp
            return max(50.0, 100.0 - (gap * 10))
        else:
            # Over-experienced (less penalty)
            excess = years_exp - target_range[1]
            return max(70.0, 100.0 - (excess * 5))
    
    def _analyze_skill_breakdown(self, skill_profile: Dict[str, Any], 
                                search_query: SearchQuery) -> Dict[str, float]:
        """Analyze individual skill matches"""
        breakdown = {}
        skill_scores = skill_profile.get("skill_confidence_scores", {})
        
        if not search_query.required_skills:
            return breakdown
        
        for skill in search_query.required_skills:
            normalized_skill = self.skill_service.normalize_skill(skill)
            
            if normalized_skill in skill_scores:
                confidence = skill_scores[normalized_skill]
                match_score = min(100.0, confidence * 1.1)  # Slight boost for direct matches
            else:
                # Check for related skills
                related_score = 0.0
                for candidate_skill, confidence in skill_scores.items():
                    if self.skill_service._skills_related(normalized_skill, candidate_skill):
                        related_score = max(related_score, confidence * 0.7)
                
                match_score = related_score
            
            breakdown[skill] = match_score
        
        return breakdown
    
    def _analyze_confidence_distribution(self, skill_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze confidence score distribution"""
        skill_scores = skill_profile.get("skill_confidence_scores", {})
        
        if not skill_scores:
            return {"error": "No skill scores available"}
        
        scores = list(skill_scores.values())
        
        return {
            "total_skills": len(scores),
            "average_confidence": sum(scores) / len(scores),
            "high_confidence_count": sum(1 for s in scores if s >= 85),
            "medium_confidence_count": sum(1 for s in scores if 70 <= s < 85),
            "low_confidence_count": sum(1 for s in scores if s < 70),
            "confidence_range": f"{min(scores)}-{max(scores)}"
        }
    
    def _create_default_score(self, candidate_id: str, vector_similarity: float) -> CandidateScore:
        """Create default score when analysis fails"""
        return CandidateScore(
            candidate_id=candidate_id,
            overall_score=vector_similarity * 0.6,  # Reduced weight due to missing skill data
            skill_match_score=0.0,
            confidence_score=0.0,
            vector_similarity_score=vector_similarity,
            experience_match_score=0.0,
            skill_breakdown={},
            ranking_factors={"error": "Failed to parse candidate analysis"}
        )
    
    def rank_candidates(self, candidates: List[Dict[str, Any]], 
                       search_query: SearchQuery,
                       vector_similarities: List[float] = None) -> SearchResult:
        """Rank candidates based on skill-aware scoring"""
        
        if vector_similarities is None:
            vector_similarities = [0.0] * len(candidates)
        
        # Score all candidates
        candidate_scores = []
        for i, candidate in enumerate(candidates):
            vector_sim = vector_similarities[i] if i < len(vector_similarities) else 0.0
            score = self.score_candidate(candidate, search_query, vector_sim)
            candidate_scores.append(score)
        
        # Sort by overall score
        candidate_scores.sort(key=lambda x: x.overall_score, reverse=True)
        
        # Generate query analysis
        query_analysis = {
            "parsed_requirements": {
                "required_skills": search_query.required_skills,
                "skill_categories": search_query.skill_categories,
                "experience_level": search_query.experience_level,
                "minimum_confidence": search_query.minimum_confidence
            },
            "search_strategy": self._analyze_search_strategy(search_query),
            "ranking_weights": self.weight_config
        }
        
        # Generate search metadata
        search_metadata = {
            "total_candidates": len(candidates),
            "candidates_scored": len(candidate_scores),
            "average_scores": self._calculate_average_scores(candidate_scores),
            "score_distribution": self._analyze_score_distribution(candidate_scores)
        }
        
        return SearchResult(
            candidates=candidate_scores,
            query_analysis=query_analysis,
            search_metadata=search_metadata
        )
    
    def _analyze_search_strategy(self, search_query: SearchQuery) -> Dict[str, str]:
        """Analyze and explain search strategy"""
        strategy = {}
        
        if search_query.required_skills:
            strategy["skill_focus"] = f"Prioritizing candidates with {', '.join(search_query.required_skills)}"
        else:
            strategy["skill_focus"] = "General skill assessment without specific requirements"
        
        if search_query.experience_level:
            strategy["experience_focus"] = f"Targeting {search_query.experience_level} level candidates"
        else:
            strategy["experience_focus"] = "No specific experience level requirement"
        
        strategy["confidence_threshold"] = f"Minimum confidence: {search_query.minimum_confidence}%"
        
        return strategy
    
    def _calculate_average_scores(self, candidate_scores: List[CandidateScore]) -> Dict[str, float]:
        """Calculate average scores across all candidates"""
        if not candidate_scores:
            return {}
        
        return {
            "overall_score": sum(cs.overall_score for cs in candidate_scores) / len(candidate_scores),
            "skill_match_score": sum(cs.skill_match_score for cs in candidate_scores) / len(candidate_scores),
            "confidence_score": sum(cs.confidence_score for cs in candidate_scores) / len(candidate_scores),
            "vector_similarity_score": sum(cs.vector_similarity_score for cs in candidate_scores) / len(candidate_scores),
            "experience_match_score": sum(cs.experience_match_score for cs in candidate_scores) / len(candidate_scores)
        }
    
    def _analyze_score_distribution(self, candidate_scores: List[CandidateScore]) -> Dict[str, int]:
        """Analyze score distribution for insights"""
        if not candidate_scores:
            return {}
        
        overall_scores = [cs.overall_score for cs in candidate_scores]
        
        return {
            "excellent_matches": sum(1 for score in overall_scores if score >= 85),
            "good_matches": sum(1 for score in overall_scores if 70 <= score < 85),
            "fair_matches": sum(1 for score in overall_scores if 50 <= score < 70),
            "poor_matches": sum(1 for score in overall_scores if score < 50)
        }
    
    def get_ranking_explanation(self, candidate_score: CandidateScore) -> Dict[str, str]:
        """Generate human-readable explanation of ranking"""
        explanation = {
            "overall_assessment": "",
            "skill_strength": "",
            "confidence_level": "",
            "experience_match": "",
            "recommendations": []
        }
        
        # Overall assessment
        if candidate_score.overall_score >= 85:
            explanation["overall_assessment"] = "Excellent match with strong alignment to requirements"
        elif candidate_score.overall_score >= 70:
            explanation["overall_assessment"] = "Good match with solid qualifications"
        elif candidate_score.overall_score >= 50:
            explanation["overall_assessment"] = "Fair match with some relevant experience"
        else:
            explanation["overall_assessment"] = "Limited match to current requirements"
        
        # Skill strength
        if candidate_score.skill_match_score >= 80:
            explanation["skill_strength"] = "Strong skill alignment with excellent technical fit"
        elif candidate_score.skill_match_score >= 60:
            explanation["skill_strength"] = "Good skill match with relevant experience"
        else:
            explanation["skill_strength"] = "Limited skill match requiring development"
        
        # Confidence level
        if candidate_score.confidence_score >= 85:
            explanation["confidence_level"] = "High confidence in demonstrated skills"
        elif candidate_score.confidence_score >= 70:
            explanation["confidence_level"] = "Moderate confidence with good evidence"
        else:
            explanation["confidence_level"] = "Lower confidence requiring verification"
        
        # Experience match
        if candidate_score.experience_match_score >= 85:
            explanation["experience_match"] = "Ideal experience level for the role"
        elif candidate_score.experience_match_score >= 70:
            explanation["experience_match"] = "Appropriate experience with minor gaps"
        else:
            explanation["experience_match"] = "Experience level may not align perfectly"
        
        # Recommendations
        if candidate_score.skill_match_score < 70:
            explanation["recommendations"].append("Consider skill assessment or training opportunities")
        if candidate_score.confidence_score < 70:
            explanation["recommendations"].append("Conduct detailed technical interview for verification")
        if candidate_score.vector_similarity_score > candidate_score.skill_match_score:
            explanation["recommendations"].append("Strong cultural/contextual fit despite skill gaps")
        
        return explanation
    
    def export_search_results(self, search_result: SearchResult, 
                            output_file: str = None) -> Dict[str, Any]:
        """Export detailed search results with explanations"""
        
        export_data = {
            "search_summary": {
                "total_candidates": len(search_result.candidates),
                "query_analysis": search_result.query_analysis,
                "search_metadata": search_result.search_metadata
            },
            "top_candidates": [],
            "detailed_analysis": []
        }
        
        # Export top 10 candidates with explanations
        for i, candidate in enumerate(search_result.candidates[:10]):
            explanation = self.get_ranking_explanation(candidate)
            
            candidate_data = {
                "rank": i + 1,
                "candidate_id": candidate.candidate_id,
                "overall_score": round(candidate.overall_score, 2),
                "component_scores": {
                    "skill_match": round(candidate.skill_match_score, 2),
                    "confidence": round(candidate.confidence_score, 2),
                    "vector_similarity": round(candidate.vector_similarity_score, 2),
                    "experience_match": round(candidate.experience_match_score, 2)
                },
                "explanation": explanation,
                "skill_breakdown": candidate.skill_breakdown
            }
            
            export_data["top_candidates"].append(candidate_data)
        
        # Add detailed analysis for all candidates
        export_data["detailed_analysis"] = [
            {
                "candidate_id": cs.candidate_id,
                "scores": {
                    "overall": round(cs.overall_score, 2),
                    "skill_match": round(cs.skill_match_score, 2),
                    "confidence": round(cs.confidence_score, 2),
                    "vector_similarity": round(cs.vector_similarity_score, 2),
                    "experience_match": round(cs.experience_match_score, 2)
                },
                "ranking_factors": cs.ranking_factors
            }
            for cs in search_result.candidates
        ]
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)
            logger.info(f"Search results exported to {output_file}")
        
        return export_data