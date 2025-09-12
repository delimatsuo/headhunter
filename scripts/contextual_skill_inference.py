#!/usr/bin/env python3
"""
Contextual Skill Inference System

Encodes senior recruiter intelligence to infer likely skills based on:
- Company context and tier (Google vs Startup vs Non-profit)  
- Industry patterns (FinTech vs Healthcare vs Consulting)
- Role evolution and career path patterns
- Educational background and institution quality
- Geographic/market context
"""

import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import os

# Add cloud_run_worker to path
import sys
sys.path.append('cloud_run_worker')
from config import Config

@dataclass
class SkillInference:
    skill: str
    confidence: float
    source: str  # 'explicit', 'company_context', 'industry_pattern', 'role_inference', 'education_context'
    reasoning: str

@dataclass
class CompanyContext:
    name: str
    tier: str  # 'faang', 'enterprise', 'growth', 'startup', 'consulting', 'nonprofit'
    industry: str
    typical_skills: List[str]
    culture_indicators: List[str]
    skill_depth_multiplier: float

class ContextualSkillInferenceEngine:
    """Infers skills using contextual intelligence like senior recruiters"""
    
    def __init__(self):
        self.config = Config()
        
        # Company intelligence database (what senior recruiters know)
        self.company_intelligence = self._build_company_intelligence()
        
        # Industry skill patterns
        self.industry_patterns = self._build_industry_patterns()
        
        # Role evolution patterns  
        self.role_patterns = self._build_role_patterns()
        
        # Educational context
        self.education_context = self._build_education_context()
    
    def _build_company_intelligence(self) -> Dict[str, CompanyContext]:
        """Build company context intelligence like recruiters have"""
        return {
            # FAANG - High technical standards, scale, innovation
            'Google': CompanyContext('Google', 'faang', 'tech', 
                ['System Design', 'Distributed Systems', 'Algorithms', 'Code Reviews', 'Technical Leadership'],
                ['innovation', 'technical_excellence', 'scale'], 1.4),
            'Meta': CompanyContext('Meta', 'faang', 'tech',
                ['React', 'GraphQL', 'Mobile Development', 'Social Networks', 'Growth Engineering'],
                ['move_fast', 'impact', 'social_connection'], 1.4),
            'Amazon': CompanyContext('Amazon', 'faang', 'tech',
                ['AWS', 'Microservices', 'Customer Obsession', 'Operational Excellence', 'Bar Raising'],
                ['customer_obsession', 'ownership', 'operational_excellence'], 1.3),
            'Apple': CompanyContext('Apple', 'faang', 'tech',
                ['iOS Development', 'Swift', 'Hardware Integration', 'Design Thinking', 'Privacy'],
                ['design_excellence', 'privacy', 'innovation'], 1.4),
            'Netflix': CompanyContext('Netflix', 'faang', 'media',
                ['Streaming Technology', 'Microservices', 'A/B Testing', 'Data Science', 'Content Delivery'],
                ['freedom_responsibility', 'high_performance', 'innovation'], 1.3),
            
            # Consulting - Strategy, client management, structured thinking
            'McKinsey': CompanyContext('McKinsey', 'consulting', 'strategy',
                ['Strategic Thinking', 'Client Management', 'Executive Communication', 'Problem Solving', 'Analytics'],
                ['client_first', 'analytical', 'leadership'], 1.2),
            'BCG': CompanyContext('BCG', 'consulting', 'strategy',
                ['Business Strategy', 'Digital Transformation', 'Change Management', 'Data Analytics'],
                ['collaborative', 'innovative', 'impact_focused'], 1.2),
            'Deloitte': CompanyContext('Deloitte', 'consulting', 'professional_services',
                ['Enterprise Solutions', 'Digital Transformation', 'Industry Expertise', 'Client Relations'],
                ['purpose_driven', 'collaborative', 'learning'], 1.1),
            
            # Growth Stage - Scaling, versatility, rapid execution
            'Stripe': CompanyContext('Stripe', 'growth', 'fintech',
                ['Payment Systems', 'API Design', 'Financial Compliance', 'International Scaling', 'Developer Tools'],
                ['developer_first', 'global_scale', 'reliability'], 1.2),
            'Airbnb': CompanyContext('Airbnb', 'growth', 'marketplace',
                ['Marketplace Dynamics', 'Trust & Safety', 'International Growth', 'Community Building'],
                ['belonging', 'host_first', 'global_mindset'], 1.2),
            'Uber': CompanyContext('Uber', 'growth', 'mobility',
                ['Real-time Systems', 'Marketplace Optimization', 'Mobile-first', 'Global Operations'],
                ['customer_obsession', 'bold', 'efficiency'], 1.1),
            
            # Non-profit - Mission-driven, resource efficiency, social impact
            'United Nations': CompanyContext('United Nations', 'nonprofit', 'international',
                ['Cross-cultural Communication', 'Project Management', 'Policy Development', 'Stakeholder Management'],
                ['mission_driven', 'global_perspective', 'collaboration'], 0.8),
            'Red Cross': CompanyContext('Red Cross', 'nonprofit', 'humanitarian',
                ['Crisis Management', 'Emergency Response', 'Volunteer Management', 'Community Outreach'],
                ['humanitarian', 'service', 'resilience'], 0.8),
            
            # Traditional Enterprise - Process, compliance, stability
            'IBM': CompanyContext('IBM', 'enterprise', 'enterprise_tech',
                ['Enterprise Architecture', 'Legacy System Integration', 'Compliance', 'Process Management'],
                ['innovation', 'trust', 'transformation'], 1.0),
            'Oracle': CompanyContext('Oracle', 'enterprise', 'database',
                ['Database Administration', 'Enterprise Software', 'System Integration', 'Performance Tuning'],
                ['reliability', 'performance', 'enterprise_focus'], 1.0)
        }
    
    def _build_industry_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Industry-specific skill patterns that recruiters recognize"""
        return {
            'fintech': {
                'required_skills': ['Financial Modeling', 'Regulatory Compliance', 'Security', 'Payment Processing'],
                'common_skills': ['Risk Management', 'KYC/AML', 'PCI Compliance', 'Fraud Detection'],
                'depth_multiplier': 1.3,  # FinTech requires deeper expertise
                'culture': ['precision', 'compliance', 'security_first']
            },
            'healthcare': {
                'required_skills': ['HIPAA Compliance', 'Healthcare Data', 'Medical Terminology', 'Patient Privacy'],
                'common_skills': ['Electronic Health Records', 'Medical Devices', 'Clinical Workflows'],
                'depth_multiplier': 1.4,  # Healthcare has high accuracy requirements
                'culture': ['patient_first', 'accuracy', 'compliance']
            },
            'consulting': {
                'required_skills': ['Client Management', 'Strategic Thinking', 'Executive Communication', 'Problem Solving'],
                'common_skills': ['Presentation Skills', 'Business Analysis', 'Change Management'],
                'depth_multiplier': 1.2,  # Breadth over depth
                'culture': ['client_focused', 'analytical', 'communication']
            },
            'media': {
                'required_skills': ['Content Delivery', 'Streaming Technology', 'Media Processing', 'A/B Testing'],
                'common_skills': ['Video Encoding', 'CDN', 'Content Management', 'Personalization'],
                'depth_multiplier': 1.1,
                'culture': ['creative', 'user_experience', 'innovation']
            }
        }
    
    def _build_role_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Role-specific skill inference patterns"""
        return {
            'software_engineer': {
                'base_skills': ['Programming', 'Problem Solving', 'Code Review', 'Testing'],
                'progression_skills': {
                    'junior': ['Basic Programming', 'Learning', 'Mentorship Reception'],
                    'mid': ['System Design Basics', 'Code Quality', 'Feature Ownership'],
                    'senior': ['Architecture', 'Mentoring', 'Technical Leadership', 'Cross-team Collaboration'],
                    'staff': ['System Architecture', 'Technical Strategy', 'Cross-org Influence'],
                    'principal': ['Technical Vision', 'Industry Influence', 'Strategic Planning']
                }
            },
            'data_scientist': {
                'base_skills': ['Statistics', 'Machine Learning', 'Data Analysis', 'Python/R'],
                'progression_skills': {
                    'junior': ['Basic ML', 'Data Cleaning', 'Visualization'],
                    'mid': ['Advanced ML', 'Feature Engineering', 'Model Deployment'],
                    'senior': ['ML Strategy', 'Business Impact', 'Team Leadership'],
                    'staff': ['Data Strategy', 'Platform Development', 'Org-wide Impact']
                }
            }
        }
    
    def _build_education_context(self) -> Dict[str, Dict[str, Any]]:
        """Educational institution context for skill inference"""
        return {
            'tier_1': {
                'schools': ['MIT', 'Stanford', 'Carnegie Mellon', 'UC Berkeley', 'Caltech'],
                'skill_indicators': ['Research', 'Theoretical Foundation', 'Innovation', 'Technical Depth'],
                'confidence_multiplier': 1.3,
                'reasoning': 'Top-tier institution with rigorous technical curriculum'
            },
            'tier_2': {
                'schools': ['University of Washington', 'UT Austin', 'Georgia Tech', 'University of Illinois'],
                'skill_indicators': ['Solid Foundation', 'Technical Skills', 'Industry Preparation'],
                'confidence_multiplier': 1.1,
                'reasoning': 'Strong engineering program with industry connections'
            },
            'bootcamp': {
                'schools': ['General Assembly', 'Hack Reactor', 'Lambda School'],
                'skill_indicators': ['Practical Skills', 'Industry-focused', 'Recent Training'],
                'confidence_multiplier': 0.9,
                'reasoning': 'Intensive practical training with industry focus'
            }
        }
    
    async def create_contextual_enhancement_prompt(self, candidate_data: Dict[str, Any]) -> str:
        """Create expert-engineered contextual intelligence prompt"""
        
        # Import the expert prompt builder
        from expert_prompt_engineering import OptimizedPromptBuilder
        
        builder = OptimizedPromptBuilder()
        return builder.build_stage_2_contextual_prompt(candidate_data),
    
    "recruiter_verdict": {{
      "overall_rating": "A-",
      "recommendation": "highly-recommend",
      "one_line_pitch": "Context-aware compelling summary",
      "contextual_selling_points": ["Selling points based on company/industry context"],
      "placement_intelligence": {{
        "ideal_company_types": ["Based on background analysis"],
        "skill_transferability": "high/medium/low",
        "industry_fit_score": 0.90
      }}
    }}
  }}
}}

Use your contextual intelligence to provide rich, nuanced analysis that goes beyond explicit information.
"""
        
        return prompt
    
    def _analyze_company_context(self, companies: List[str]) -> str:
        """Analyze company context for skill inference"""
        context_insights = []
        
        for company in companies:
            if company in self.company_intelligence:
                comp_ctx = self.company_intelligence[company]
                context_insights.append(f"""
{company} Context ({comp_ctx.tier.upper()}):
- Typical Skills: {', '.join(comp_ctx.typical_skills)}
- Culture: {', '.join(comp_ctx.culture_indicators)}
- Skill Depth Multiplier: {comp_ctx.skill_depth_multiplier}x
- Industry: {comp_ctx.industry}""")
            else:
                # Infer from name patterns
                if any(indicator in company.lower() for indicator in ['startup', 'series', 'early']):
                    context_insights.append(f"""
{company} Context (STARTUP):
- Likely Skills: Full-stack, Scrappy execution, Resource efficiency, Wearing multiple hats
- Culture: Fast-paced, Ownership, Adaptability
- Skill Development: Broad but possibly shallow""")
                elif any(indicator in company.lower() for indicator in ['consulting', 'advisory']):
                    context_insights.append(f"""
{company} Context (CONSULTING):
- Likely Skills: Client management, Strategic thinking, Communication, Problem solving
- Culture: Client-first, Analytical, Professional
- Skill Development: Broad business acumen""")
        
        return '\n'.join(context_insights) if context_insights else "No specific company context available"
    
    def _analyze_industry_context(self, companies: List[str]) -> str:
        """Analyze industry patterns"""
        # Simple industry detection - can be enhanced
        industry_keywords = {
            'fintech': ['bank', 'financial', 'payment', 'fintech', 'stripe'],
            'healthcare': ['health', 'medical', 'pharma', 'biotech'],
            'consulting': ['consulting', 'mckinsey', 'bcg', 'deloitte'],
            'media': ['netflix', 'media', 'entertainment', 'streaming']
        }
        
        detected_industries = []
        for company in companies:
            company_lower = company.lower()
            for industry, keywords in industry_keywords.items():
                if any(keyword in company_lower for keyword in keywords):
                    if industry not in detected_industries:
                        detected_industries.append(industry)
        
        insights = []
        for industry in detected_industries:
            if industry in self.industry_patterns:
                pattern = self.industry_patterns[industry]
                insights.append(f"""
{industry.upper()} Industry Pattern:
- Required Skills: {', '.join(pattern['required_skills'])}
- Common Skills: {', '.join(pattern['common_skills'])}
- Skill Depth: {pattern['depth_multiplier']}x multiplier
- Culture: {', '.join(pattern['culture'])}""")
        
        return '\n'.join(insights) if insights else "General industry patterns apply"
    
    def _analyze_role_progression(self, role_type: str, experience_years: int) -> str:
        """Analyze expected role progression"""
        if role_type in self.role_patterns:
            pattern = self.role_patterns[role_type]
            
            # Determine seniority level
            if experience_years < 2:
                level = 'junior'
            elif experience_years < 5:
                level = 'mid'
            elif experience_years < 8:
                level = 'senior'
            elif experience_years < 12:
                level = 'staff'
            else:
                level = 'principal'
            
            base_skills = pattern['base_skills']
            level_skills = pattern['progression_skills'].get(level, [])
            
            return f"""
{role_type.upper()} Role Progression ({level.upper()} level):
- Base Skills: {', '.join(base_skills)}
- Level-specific Skills: {', '.join(level_skills)}
- Expected Progression: {experience_years} years suggests {level} level capabilities"""
        
        return f"Standard {role_type} progression patterns"
    
    def _analyze_education_context(self, education: str) -> str:
        """Analyze educational context"""
        if not education:
            return "No educational context provided"
        
        education_lower = education.lower()
        
        for tier, info in self.education_context.items():
            for school in info['schools']:
                if school.lower() in education_lower:
                    return f"""
{school} ({tier.upper()}):
- Skill Indicators: {', '.join(info['skill_indicators'])}
- Confidence Multiplier: {info['confidence_multiplier']}x
- Reasoning: {info['reasoning']}"""
        
        return f"Educational Background: {education[:100]}..."

# Test the contextual inference system
async def test_contextual_inference():
    """Test the contextual skill inference system"""
    
    engine = ContextualSkillInferenceEngine()
    
    # Test candidate with rich context
    test_candidate = {
        'name': 'Alex Chen',
        'role_type': 'software_engineer',
        'experience': 7,
        'companies': ['Google', 'Stripe'],
        'education': 'MIT Computer Science',
        'skills': ['Python', 'JavaScript', 'React']
    }
    
    prompt = await engine.create_contextual_enhancement_prompt(test_candidate)
    
    print("🧠 CONTEXTUAL SKILL INFERENCE PROMPT:")
    print("=" * 60)
    print(prompt[:2000])
    print("...")
    print("=" * 60)
    
    return prompt

if __name__ == "__main__":
    asyncio.run(test_contextual_inference())