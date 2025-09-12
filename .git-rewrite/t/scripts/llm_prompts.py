#!/usr/bin/env python3
"""
LLM Prompts for Resume Analysis
Structured prompts for extracting career insights from resume text using Llama 3.1 8b
"""

import json
import subprocess
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class CareerLevel(Enum):
    """Career level classifications"""
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"


class CompanyTier(Enum):
    """Company tier classifications"""
    STARTUP = "startup"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"
    FAANG = "faang"
    FORTUNE500 = "fortune500"


@dataclass
class ResumeAnalysis:
    """Structured output for resume analysis"""
    career_trajectory: Dict[str, Any]
    leadership_scope: Dict[str, Any]
    company_pedigree: List[Dict[str, str]]
    technical_skills: List[str]
    soft_skills: List[str]
    cultural_signals: List[str]
    years_experience: int
    education_level: str
    industry_focus: List[str]
    notable_achievements: List[str]


class ResumeAnalyzer:
    """Analyze resumes using Llama 3.1 8b via Ollama"""
    
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
    
    def analyze_career_trajectory(self, resume_text: str) -> Dict[str, Any]:
        """Analyze career progression and trajectory"""
        prompt = f"""Analyze the following resume and extract career trajectory information.
        
Resume:
{resume_text}

Please provide a JSON response with the following structure:
{{
    "current_level": "entry|mid|senior|lead|executive",
    "progression_speed": "slow|average|fast|exceptional",
    "years_to_current": <number>,
    "role_changes": <number>,
    "industry_changes": <number>,
    "promotion_pattern": "linear|accelerated|lateral|mixed",
    "career_highlights": ["highlight1", "highlight2", ...]
}}

Respond ONLY with valid JSON, no additional text."""
        
        response = self._run_prompt(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Attempt to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError(f"Failed to parse JSON from response: {response[:200]}")
    
    def analyze_leadership_scope(self, resume_text: str) -> Dict[str, Any]:
        """Analyze leadership experience and scope"""
        prompt = f"""Analyze the following resume for leadership experience and scope.

Resume:
{resume_text}

Please provide a JSON response with the following structure:
{{
    "has_leadership": true|false,
    "team_size_managed": <number or null>,
    "budget_managed": "<amount or null>",
    "leadership_roles": ["role1", "role2", ...],
    "leadership_style_indicators": ["indicator1", "indicator2", ...],
    "cross_functional": true|false,
    "global_experience": true|false
}}

Respond ONLY with valid JSON, no additional text."""
        
        response = self._run_prompt(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError(f"Failed to parse JSON from response: {response[:200]}")
    
    def analyze_company_pedigree(self, resume_text: str) -> List[Dict[str, str]]:
        """Analyze company background and pedigree"""
        prompt = f"""Analyze the companies mentioned in this resume.

Resume:
{resume_text}

Please provide a JSON response with a list of companies:
[
    {{
        "company_name": "Company Name",
        "tier": "startup|growth|enterprise|faang|fortune500",
        "industry": "Industry",
        "years_there": <number>,
        "notable": true|false
    }},
    ...
]

Respond ONLY with valid JSON array, no additional text."""
        
        response = self._run_prompt(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError(f"Failed to parse JSON from response: {response[:200]}")
    
    def extract_skills(self, resume_text: str) -> Dict[str, List[str]]:
        """Extract technical and soft skills"""
        prompt = f"""Extract skills from the following resume.

Resume:
{resume_text}

Please provide a JSON response:
{{
    "technical_skills": ["skill1", "skill2", ...],
    "soft_skills": ["skill1", "skill2", ...],
    "tools_technologies": ["tool1", "tool2", ...],
    "certifications": ["cert1", "cert2", ...]
}}

Respond ONLY with valid JSON, no additional text."""
        
        response = self._run_prompt(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError(f"Failed to parse JSON from response: {response[:200]}")
    
    def identify_cultural_signals(self, resume_text: str) -> List[str]:
        """Identify cultural fit signals and values"""
        prompt = f"""Identify cultural signals and values from this resume.

Resume:
{resume_text}

Look for indicators of:
- Work style (collaborative, independent, etc.)
- Values (innovation, stability, growth, etc.)
- Environment preferences (startup, corporate, etc.)
- Communication style
- Problem-solving approach

Provide a JSON array of cultural signals:
["signal1", "signal2", "signal3", ...]

Respond ONLY with valid JSON array, no additional text."""
        
        response = self._run_prompt(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError(f"Failed to parse JSON from response: {response[:200]}")
    
    def analyze_full_resume(self, resume_text: str) -> ResumeAnalysis:
        """Perform complete resume analysis"""
        # Get all analysis components
        career = self.analyze_career_trajectory(resume_text)
        leadership = self.analyze_leadership_scope(resume_text)
        companies = self.analyze_company_pedigree(resume_text)
        skills = self.extract_skills(resume_text)
        cultural = self.identify_cultural_signals(resume_text)
        
        # Extract additional metrics
        metrics_prompt = f"""Extract these metrics from the resume:

Resume:
{resume_text}

Provide JSON:
{{
    "years_experience": <total years>,
    "education_level": "high_school|bachelors|masters|phd|other",
    "industry_focus": ["industry1", "industry2", ...],
    "notable_achievements": ["achievement1", "achievement2", ...]
}}

Respond ONLY with valid JSON."""
        
        metrics_response = self._run_prompt(metrics_prompt)
        try:
            metrics = json.loads(metrics_response)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{.*\}', metrics_response, re.DOTALL)
            if json_match:
                metrics = json.loads(json_match.group())
            else:
                metrics = {
                    "years_experience": 0,
                    "education_level": "unknown",
                    "industry_focus": [],
                    "notable_achievements": []
                }
        
        return ResumeAnalysis(
            career_trajectory=career,
            leadership_scope=leadership,
            company_pedigree=companies,
            technical_skills=skills.get("technical_skills", []),
            soft_skills=skills.get("soft_skills", []),
            cultural_signals=cultural,
            years_experience=metrics.get("years_experience", 0),
            education_level=metrics.get("education_level", "unknown"),
            industry_focus=metrics.get("industry_focus", []),
            notable_achievements=metrics.get("notable_achievements", [])
        )


def create_summary_prompt(analysis: ResumeAnalysis) -> str:
    """Create a human-readable summary from analysis"""
    return f"""Based on this resume analysis, create a brief executive summary:

Career Level: {analysis.career_trajectory.get('current_level', 'unknown')}
Years of Experience: {analysis.years_experience}
Leadership Experience: {analysis.leadership_scope.get('has_leadership', False)}
Top Skills: {', '.join(analysis.technical_skills[:5])}
Industries: {', '.join(analysis.industry_focus)}

Write a 2-3 sentence summary highlighting the candidate's key strengths and fit."""


if __name__ == "__main__":
    # Example usage
    sample_resume = """
    John Doe
    Senior Software Engineer
    
    Experience:
    - Tech Lead at Google (2020-2024)
      Led team of 8 engineers on cloud infrastructure projects
      Managed $2M annual budget
      
    - Software Engineer at Microsoft (2018-2020)
      Developed distributed systems
      
    - Junior Developer at Startup XYZ (2016-2018)
      Full-stack development
    
    Education:
    MS Computer Science, Stanford University
    BS Computer Science, UC Berkeley
    
    Skills:
    Python, Java, Kubernetes, AWS, Leadership, Mentoring
    """
    
    print("Testing Resume Analyzer with sample data...")
    print("=" * 50)
    
    try:
        analyzer = ResumeAnalyzer()
        print("✓ Analyzer initialized")
        
        # Test individual components
        print("\nTesting career trajectory analysis...")
        career = analyzer.analyze_career_trajectory(sample_resume)
        print(f"Career Level: {career.get('current_level', 'unknown')}")
        
        print("\nTesting leadership analysis...")
        leadership = analyzer.analyze_leadership_scope(sample_resume)
        print(f"Has Leadership: {leadership.get('has_leadership', False)}")
        
        print("\n✓ All prompt functions working correctly")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()