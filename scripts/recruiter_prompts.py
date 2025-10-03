#!/usr/bin/env python3
"""
LLM Prompts for Recruiter Comments Analysis
Extract insights and patterns from recruiter feedback using Llama 3.1 8b
"""

import json
import subprocess
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import re


class FeedbackSentiment(Enum):
    """Overall feedback sentiment classification"""
    HIGHLY_POSITIVE = "highly_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class CandidateReadiness(Enum):
    """Candidate readiness assessment"""
    READY_NOW = "ready_now"
    NEEDS_DEVELOPMENT = "needs_development"
    NOT_READY = "not_ready"
    OVERQUALIFIED = "overqualified"


@dataclass
class RecruiterInsights:
    """Structured insights from recruiter comments"""
    sentiment: str
    strengths: List[str]
    concerns: List[str]
    red_flags: List[str]
    leadership_indicators: List[str]
    cultural_fit: Dict[str, Any]
    recommendation: str
    readiness_level: str
    key_themes: List[str]
    development_areas: List[str]
    competitive_advantages: List[str]


class RecruiterCommentAnalyzer:
    """Analyze recruiter comments and feedback using Llama 3.1 8b"""
    
    def __init__(self, model: str = "llama3.1:8b"):
        self.model = model
        self._verify_model()
    
    def _verify_model(self):
        """Verify that the model is available"""
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                check=True
            )
            if self.model not in result.stdout:
                raise ValueError(f"Model {self.model} not found. Please run: ollama pull {self.model}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to verify Ollama installation: {e}")
    
    def _run_prompt(self, prompt: str, timeout: int = 60) -> str:
        """Execute a prompt using Ollama"""
        try:
            result = subprocess.run(
                ['ollama', 'run', self.model, prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Model response timed out after {timeout} seconds")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to run prompt: {e}")
    
    def _extract_json(self, response: str) -> Any:
        """Extract JSON from model response"""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            json_match = re.search(r'[\{\[].*[\}\]]', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    # Try to fix common JSON issues
                    fixed = json_match.group()
                    # Replace single quotes with double quotes
                    fixed = re.sub(r"'([^']*)'", r'"\1"', fixed)
                    # Remove trailing commas
                    fixed = re.sub(r',\s*}', '}', fixed)
                    fixed = re.sub(r',\s*]', ']', fixed)
                    try:
                        return json.loads(fixed)
                    except:
                        pass
            # If all else fails, return a safe default based on context
            if '[' in response:
                return []  # Empty list for array responses
            return {}  # Empty dict for object responses
    
    def analyze_sentiment(self, comments: str) -> Dict[str, Any]:
        """Analyze overall sentiment and tone of recruiter comments"""
        prompt = f"""Analyze the sentiment and tone of these recruiter comments:

Comments:
{comments}

Provide a JSON response:
{{
    "overall_sentiment": "highly_positive|positive|neutral|negative|mixed",
    "confidence_level": <0.0-1.0>,
    "enthusiasm_level": "high|medium|low",
    "tone_descriptors": ["professional", "enthusiastic", "cautious", etc.],
    "recommendation_strength": "strong|moderate|weak|none",
    "urgency_level": "high|medium|low"
}}

Respond ONLY with valid JSON, no additional text."""
        
        response = self._run_prompt(prompt)
        return self._extract_json(response)
    
    def extract_strengths_and_concerns(self, comments: str) -> Dict[str, List[str]]:
        """Extract candidate strengths and concerns from comments"""
        prompt = f"""Extract strengths and concerns from these recruiter comments:

Comments:
{comments}

Provide a JSON response:
{{
    "strengths": [
        "Specific strength mentioned...",
        "Another strength..."
    ],
    "concerns": [
        "Concern or area for improvement...",
        "Another concern..."
    ],
    "red_flags": [
        "Any serious concerns or dealbreakers...",
        "Another red flag if any..."
    ],
    "yellow_flags": [
        "Minor concerns that need monitoring...",
        "Another yellow flag if any..."
    ]
}}

Be specific and quote or paraphrase actual feedback when possible.
If no items exist for a category, use an empty array.

Respond ONLY with valid JSON, no additional text."""
        
        response = self._run_prompt(prompt)
        return self._extract_json(response)
    
    def identify_leadership_insights(self, comments: str) -> Dict[str, Any]:
        """Extract leadership-related insights from comments"""
        prompt = f"""Analyze these recruiter comments for leadership insights:

Comments:
{comments}

Provide a JSON response:
{{
    "has_leadership_experience": true|false,
    "leadership_style": "collaborative|directive|transformational|situational|unknown",
    "leadership_strengths": ["strength1", "strength2", ...],
    "leadership_gaps": ["gap1", "gap2", ...],
    "executive_presence": "strong|developing|lacking|unknown",
    "influence_indicators": ["indicator1", "indicator2", ...],
    "team_impact": "positive|neutral|negative|unknown",
    "scale_of_leadership": "individual|team|department|organization|unknown"
}}

Respond ONLY with valid JSON, no additional text."""
        
        response = self._run_prompt(prompt)
        return self._extract_json(response)
    
    def assess_cultural_fit(self, comments: str) -> Dict[str, Any]:
        """Assess cultural fit indicators from comments"""
        prompt = f"""Analyze cultural fit indicators from these recruiter comments:

Comments:
{comments}

Provide a JSON response:
{{
    "cultural_alignment": "strong|moderate|weak|unclear",
    "work_style": ["collaborative", "independent", "flexible", etc.],
    "values_alignment": ["innovation", "stability", "growth", etc.],
    "team_fit": "excellent|good|uncertain|poor",
    "communication_style": "direct|diplomatic|analytical|expressive|mixed",
    "adaptability": "high|medium|low|unknown",
    "cultural_add": ["unique perspective", "diverse background", etc.]
}}

Respond ONLY with valid JSON, no additional text."""
        
        response = self._run_prompt(prompt)
        return self._extract_json(response)
    
    def extract_key_themes(self, comments: str) -> List[str]:
        """Identify recurring themes in the feedback"""
        prompt = f"""Identify the key recurring themes in these recruiter comments:

Comments:
{comments}

List 3-7 main themes that appear in the feedback.
Focus on patterns, repeated topics, or emphasized points.

Provide a JSON array of themes:
["theme1", "theme2", "theme3", ...]

Respond ONLY with valid JSON array, no additional text."""
        
        response = self._run_prompt(prompt)
        return self._extract_json(response)
    
    def assess_readiness(self, comments: str, role_level: Optional[str] = None) -> Dict[str, Any]:
        """Assess candidate readiness for the role"""
        role_context = f"for a {role_level} role" if role_level else ""
        
        prompt = f"""Assess this candidate's readiness {role_context} based on recruiter comments:

Comments:
{comments}

Provide a JSON response:
{{
    "readiness_level": "ready_now|needs_development|not_ready|overqualified",
    "confidence_score": <0.0-1.0>,
    "time_to_ready": "immediate|3_months|6_months|12_months|longer",
    "development_needs": ["need1", "need2", ...],
    "readiness_factors": {{
        "technical": "strong|adequate|developing|weak",
        "leadership": "strong|adequate|developing|weak",
        "cultural": "strong|adequate|developing|weak",
        "experience": "strong|adequate|developing|weak"
    }},
    "risk_level": "low|medium|high"
}}

Respond ONLY with valid JSON, no additional text."""
        
        response = self._run_prompt(prompt, timeout=90)
        return self._extract_json(response)
    
    def identify_competitive_advantages(self, comments: str) -> List[str]:
        """Identify what makes this candidate stand out"""
        prompt = f"""Identify the candidate's competitive advantages from these comments:

Comments:
{comments}

What makes this candidate unique or particularly valuable?
List specific differentiators, unique experiences, or standout qualities.

Provide a JSON array of competitive advantages:
["advantage1", "advantage2", "advantage3", ...]

If no clear advantages are mentioned, return an empty array.

Respond ONLY with valid JSON array, no additional text."""
        
        response = self._run_prompt(prompt)
        return self._extract_json(response)
    
    def generate_recommendation(self, comments: str) -> Dict[str, Any]:
        """Generate a hiring recommendation based on comments"""
        prompt = f"""Based on these recruiter comments, generate a hiring recommendation:

Comments:
{comments}

Provide a JSON response:
{{
    "recommendation": "strong_hire|hire|maybe|no_hire",
    "confidence": <0.0-1.0>,
    "rationale": "Brief explanation of recommendation",
    "conditions": ["any conditions or caveats", ...],
    "next_steps": ["suggested next step", "another step", ...],
    "interview_focus": ["areas to probe in interviews", ...],
    "comparison": "top_tier|strong|average|below_average"
}}

Respond ONLY with valid JSON, no additional text."""
        
        response = self._run_prompt(prompt, timeout=90)
        return self._extract_json(response)
    
    def analyze_full_feedback(self, comments: str, role_level: Optional[str] = None) -> RecruiterInsights:
        """Perform complete analysis of recruiter feedback"""
        
        # Run all analyses
        sentiment = self.analyze_sentiment(comments)
        strengths_concerns = self.extract_strengths_and_concerns(comments)
        leadership = self.identify_leadership_insights(comments)
        cultural = self.assess_cultural_fit(comments)
        themes = self.extract_key_themes(comments)
        readiness = self.assess_readiness(comments, role_level)
        advantages = self.identify_competitive_advantages(comments)
        recommendation = self.generate_recommendation(comments)
        
        return RecruiterInsights(
            sentiment=sentiment.get("overall_sentiment", "neutral"),
            strengths=strengths_concerns.get("strengths", []),
            concerns=strengths_concerns.get("concerns", []),
            red_flags=strengths_concerns.get("red_flags", []),
            leadership_indicators=leadership.get("leadership_strengths", []),
            cultural_fit=cultural,
            recommendation=recommendation.get("recommendation", "maybe"),
            readiness_level=readiness.get("readiness_level", "needs_development"),
            key_themes=themes,
            development_areas=readiness.get("development_needs", []),
            competitive_advantages=advantages
        )


def create_feedback_summary(insights: RecruiterInsights) -> str:
    """Create a human-readable summary from insights"""
    summary_parts = []
    
    # Overall assessment
    summary_parts.append(f"Overall Sentiment: {insights.sentiment.upper()}")
    summary_parts.append(f"Recommendation: {insights.recommendation.replace('_', ' ').title()}")
    summary_parts.append(f"Readiness: {insights.readiness_level.replace('_', ' ').title()}")
    
    # Strengths
    if insights.strengths:
        summary_parts.append(f"\nKey Strengths: {', '.join(insights.strengths[:3])}")
    
    # Concerns
    if insights.concerns:
        summary_parts.append(f"Main Concerns: {', '.join(insights.concerns[:3])}")
    
    # Red flags
    if insights.red_flags:
        summary_parts.append(f"⚠️ Red Flags: {', '.join(insights.red_flags)}")
    
    # Competitive advantages
    if insights.competitive_advantages:
        summary_parts.append(f"Differentiators: {', '.join(insights.competitive_advantages[:3])}")
    
    return "\n".join(summary_parts)


if __name__ == "__main__":
    # Example usage with sample data
    sample_comments = """
    Had a great conversation with the candidate. Very impressive technical background 
    with 10+ years at top-tier companies. Strong communication skills and clearly 
    passionate about the role. Some concerns about cultural fit - seems used to more 
    structured environments and our startup culture might be an adjustment. 
    
    Leadership experience is solid, managed teams of 20+ engineers. However, 
    noticed some rigidity in thinking about process. Would benefit from exposure 
    to more agile methodologies. 
    
    Overall a strong candidate but would want to dig deeper into adaptability 
    and comfort with ambiguity in follow-up interviews.
    """
    
    print("Testing Recruiter Comment Analyzer...")
    print("=" * 50)
    
    try:
        analyzer = RecruiterCommentAnalyzer()
        print("✓ Analyzer initialized")
        
        # Test sentiment analysis
        print("\nTesting sentiment analysis...")
        sentiment = analyzer.analyze_sentiment(sample_comments)
        print(f"Sentiment: {sentiment.get('overall_sentiment', 'unknown')}")
        
        # Test strengths extraction
        print("\nTesting strengths and concerns extraction...")
        strengths_concerns = analyzer.extract_strengths_and_concerns(sample_comments)
        print(f"Strengths found: {len(strengths_concerns.get('strengths', []))}")
        print(f"Concerns found: {len(strengths_concerns.get('concerns', []))}")
        
        print("\n✓ All recruiter comment analysis functions working")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()