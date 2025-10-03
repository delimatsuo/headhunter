#!/usr/bin/env python3
"""
Quality Validation System for LLM Outputs
Provides JSON schema validation, quality scoring, and consistency checks for LLM responses
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
from jsonschema import validate, ValidationError
import statistics

# Import our analysis classes
try:
    from llm_prompts import ResumeAnalysis
    from recruiter_prompts import RecruiterInsights
except ImportError:
    # Handle case when run as standalone script
    import sys
    sys.path.append(str(Path(__file__).parent))
    from llm_prompts import ResumeAnalysis
    from recruiter_prompts import RecruiterInsights


@dataclass
class ValidationResult:
    """Result of validation checks"""
    is_valid: bool
    quality_score: float  # 0.0 to 1.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    validated_data: Optional[Dict] = None
    fallback_applied: bool = False


@dataclass
class QualityMetrics:
    """Quality metrics for LLM outputs"""
    completeness_score: float = 0.0
    consistency_score: float = 0.0
    schema_compliance_score: float = 0.0
    content_quality_score: float = 0.0
    overall_score: float = 0.0
    
    def calculate_overall(self):
        """Calculate overall quality score from individual metrics"""
        scores = [
            self.completeness_score,
            self.consistency_score, 
            self.schema_compliance_score,
            self.content_quality_score
        ]
        self.overall_score = statistics.mean(scores) if scores else 0.0
        return self.overall_score


class LLMOutputValidator:
    """Validates LLM outputs for quality, consistency, and schema compliance"""
    
    def __init__(self, log_level: str = "INFO"):
        """Initialize validator with logging and schemas"""
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Load JSON schemas
        self._load_schemas()
        
        # Quality thresholds
        self.min_quality_threshold = 0.6
        self.warning_threshold = 0.8
        
        self.logger.info("LLMOutputValidator initialized")
    
    def _load_schemas(self):
        """Load JSON schemas for validation"""
        # Resume Analysis Schema
        self.resume_schema = {
            "type": "object",
            "required": [
                "career_trajectory",
                "leadership_scope", 
                "company_pedigree",
                "years_experience",
                "technical_skills",
                "soft_skills"
            ],
            "properties": {
                "career_trajectory": {
                    "type": "object",
                    "required": ["current_level", "progression_speed", "trajectory_type"],
                    "properties": {
                        "current_level": {"type": "string", "enum": ["Entry", "Mid", "Senior", "Staff", "Principal", "Executive"]},
                        "progression_speed": {"type": "string", "enum": ["Slow", "Steady", "Fast", "Accelerated"]},
                        "trajectory_type": {"type": "string", "enum": ["Individual Contributor", "Management", "Technical Leadership", "Executive"]},
                        "career_changes": {"type": "integer", "minimum": 0},
                        "domain_expertise": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "leadership_scope": {
                    "type": "object",
                    "required": ["has_leadership", "team_size", "leadership_level"],
                    "properties": {
                        "has_leadership": {"type": "boolean"},
                        "team_size": {"type": "integer", "minimum": 0},
                        "leadership_level": {"type": "string", "enum": ["None", "Team Lead", "Manager", "Senior Manager", "Director", "VP", "C-Level"]},
                        "leadership_style": {"type": "array", "items": {"type": "string"}},
                        "mentorship_experience": {"type": "boolean"}
                    }
                },
                "company_pedigree": {
                    "type": "object", 
                    "required": ["tier_level", "company_types", "brand_recognition"],
                    "properties": {
                        "tier_level": {"type": "string", "enum": ["Tier1", "Tier2", "Tier3", "Mixed"]},
                        "company_types": {"type": "array", "items": {"type": "string"}},
                        "brand_recognition": {"type": "string", "enum": ["High", "Medium", "Low", "Mixed"]},
                        "recent_companies": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "years_experience": {"type": "integer", "minimum": 0, "maximum": 50},
                "technical_skills": {"type": "array", "items": {"type": "string"}},
                "soft_skills": {"type": "array", "items": {"type": "string"}},
                "education": {
                    "type": "object",
                    "properties": {
                        "highest_degree": {"type": "string"},
                        "institutions": {"type": "array", "items": {"type": "string"}},
                        "fields_of_study": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "cultural_signals": {"type": "array", "items": {"type": "string"}}
            }
        }
        
        # Recruiter Insights Schema
        self.recruiter_schema = {
            "type": "object",
            "required": [
                "sentiment",
                "strengths", 
                "concerns",
                "recommendation",
                "readiness_level"
            ],
            "properties": {
                "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative", "mixed"]},
                "strengths": {"type": "array", "items": {"type": "string"}, "minItems": 0},
                "concerns": {"type": "array", "items": {"type": "string"}, "minItems": 0},
                "red_flags": {"type": "array", "items": {"type": "string"}, "minItems": 0},
                "leadership_indicators": {"type": "array", "items": {"type": "string"}, "minItems": 0},
                "cultural_fit": {
                    "type": "object",
                    "required": ["cultural_alignment"],
                    "properties": {
                        "cultural_alignment": {"type": "string", "enum": ["excellent", "good", "moderate", "poor", "unclear"]},
                        "work_style": {"type": "array", "items": {"type": "string"}},
                        "values_alignment": {"type": "array", "items": {"type": "string"}},
                        "team_fit": {"type": "string", "enum": ["excellent", "good", "moderate", "poor", "unclear"]},
                        "communication_style": {"type": "string"},
                        "adaptability": {"type": "string", "enum": ["high", "medium", "low", "unclear"]},
                        "cultural_add": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "recommendation": {"type": "string", "enum": ["strong_hire", "hire", "maybe", "no_hire"]},
                "readiness_level": {"type": "string", "enum": ["ready_now", "ready_soon", "needs_development", "not_ready"]},
                "key_themes": {"type": "array", "items": {"type": "string"}, "minItems": 0},
                "development_areas": {"type": "array", "items": {"type": "string"}, "minItems": 0},
                "competitive_advantages": {"type": "array", "items": {"type": "string"}, "minItems": 0}
            }
        }
        
        self.logger.debug("JSON schemas loaded successfully")
    
    def validate_schema(self, data: Dict, schema_type: str) -> Tuple[bool, List[str]]:
        """Validate data against JSON schema"""
        errors = []
        
        try:
            if schema_type == "resume":
                validate(instance=data, schema=self.resume_schema)
            elif schema_type == "recruiter":
                validate(instance=data, schema=self.recruiter_schema)
            else:
                errors.append(f"Unknown schema type: {schema_type}")
                return False, errors
            
            return True, []
            
        except ValidationError as e:
            errors.append(f"Schema validation error: {e.message}")
            self.logger.warning(f"Schema validation failed for {schema_type}: {e.message}")
            return False, errors
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            self.logger.error(f"Unexpected validation error: {e}")
            return False, errors
    
    def check_completeness(self, data: Dict, schema_type: str) -> float:
        """Check completeness of required and optional fields"""
        if schema_type == "resume":
            schema = self.resume_schema
        elif schema_type == "recruiter":
            schema = self.recruiter_schema
        else:
            return 0.0
        
        required_fields = schema.get("required", [])
        total_fields = len(schema.get("properties", {}))
        
        if not required_fields or not total_fields:
            return 1.0
        
        # Check required fields
        required_present = sum(1 for field in required_fields if field in data and data[field])
        required_score = required_present / len(required_fields) if required_fields else 1.0
        
        # Check all fields (including optional)
        all_present = sum(1 for field in schema["properties"] if field in data and data[field])
        completeness_score = all_present / total_fields if total_fields else 1.0
        
        # Weight required fields more heavily
        final_score = (required_score * 0.7) + (completeness_score * 0.3)
        
        return min(final_score, 1.0)
    
    def check_content_quality(self, data: Dict, schema_type: str) -> float:
        """Assess content quality of the response"""
        quality_score = 1.0
        
        if schema_type == "resume":
            # Check for meaningful content in key fields
            if "technical_skills" in data:
                if len(data["technical_skills"]) < 2:
                    quality_score -= 0.1
                if any(len(skill.strip()) < 2 for skill in data["technical_skills"]):
                    quality_score -= 0.1
            
            if "years_experience" in data:
                if not isinstance(data["years_experience"], int) or data["years_experience"] < 0:
                    quality_score -= 0.2
                if data["years_experience"] > 50:
                    quality_score -= 0.1  # Unrealistic
            
            # Check career trajectory consistency
            if "career_trajectory" in data:
                traj = data["career_trajectory"]
                if traj.get("current_level") == "Entry" and data.get("years_experience", 0) > 10:
                    quality_score -= 0.1  # Inconsistent
        
        elif schema_type == "recruiter":
            # Check for meaningful insights
            if "strengths" in data and len(data["strengths"]) == 0:
                quality_score -= 0.1
            
            if "concerns" in data and "red_flags" in data:
                if len(data["concerns"]) == 0 and len(data["red_flags"]) == 0:
                    # No concerns at all might indicate poor analysis
                    quality_score -= 0.05
            
            # Check sentiment consistency with recommendation
            sentiment_rec_mapping = {
                "positive": ["strong_hire", "hire"],
                "negative": ["no_hire"],
                "neutral": ["maybe", "hire"],
                "mixed": ["maybe", "hire", "no_hire"]
            }
            
            sentiment = data.get("sentiment", "")
            recommendation = data.get("recommendation", "")
            
            if sentiment in sentiment_rec_mapping:
                if recommendation not in sentiment_rec_mapping[sentiment]:
                    quality_score -= 0.1  # Inconsistent sentiment/recommendation
        
        return max(quality_score, 0.0)
    
    def check_consistency(self, data: Dict, schema_type: str) -> float:
        """Check internal consistency of the data"""
        consistency_score = 1.0
        
        if schema_type == "resume":
            # Check leadership scope vs years experience
            if "leadership_scope" in data and "years_experience" in data:
                leadership = data["leadership_scope"]
                years = data.get("years_experience", 0)
                
                if leadership.get("has_leadership", False):
                    if years < 2:  # Very junior for leadership
                        consistency_score -= 0.1
                    if leadership.get("team_size", 0) > 50 and years < 5:
                        consistency_score -= 0.1  # Large team, little experience
                
                # Leadership level consistency
                level_experience_map = {
                    "Team Lead": 2,
                    "Manager": 3,
                    "Senior Manager": 7,
                    "Director": 10,
                    "VP": 15,
                    "C-Level": 20
                }
                
                leadership_level = leadership.get("leadership_level", "None")
                if leadership_level in level_experience_map:
                    min_years = level_experience_map[leadership_level]
                    if years < min_years:
                        consistency_score -= 0.1
        
        elif schema_type == "recruiter":
            # Check cultural fit consistency
            if "cultural_fit" in data:
                cultural_fit = data["cultural_fit"]
                overall_alignment = cultural_fit.get("cultural_alignment", "")
                team_fit = cultural_fit.get("team_fit", "")
                
                # If overall cultural alignment is poor, team fit shouldn't be excellent
                if overall_alignment == "poor" and team_fit == "excellent":
                    consistency_score -= 0.1
                
                # Check recommendation consistency with cultural fit
                recommendation = data.get("recommendation", "")
                if overall_alignment in ["poor"] and recommendation in ["strong_hire", "hire"]:
                    consistency_score -= 0.1
        
        return max(consistency_score, 0.0)
    
    def calculate_quality_metrics(self, data: Dict, schema_type: str) -> QualityMetrics:
        """Calculate comprehensive quality metrics"""
        metrics = QualityMetrics()
        
        # Schema compliance
        is_valid, errors = self.validate_schema(data, schema_type)
        metrics.schema_compliance_score = 1.0 if is_valid else max(0.5 - len(errors) * 0.1, 0.0)
        
        # Completeness
        metrics.completeness_score = self.check_completeness(data, schema_type)
        
        # Content quality
        metrics.content_quality_score = self.check_content_quality(data, schema_type)
        
        # Consistency
        metrics.consistency_score = self.check_consistency(data, schema_type)
        
        # Calculate overall score
        metrics.calculate_overall()
        
        return metrics
    
    def apply_fallback_corrections(self, data: Dict, schema_type: str) -> Tuple[Dict, bool]:
        """Apply fallback corrections for common issues"""
        corrected_data = data.copy()
        fallback_applied = False
        
        try:
            if schema_type == "resume":
                # Fix missing or invalid years_experience
                if "years_experience" not in corrected_data or not isinstance(corrected_data["years_experience"], int):
                    corrected_data["years_experience"] = 5  # Default reasonable value
                    fallback_applied = True
                
                # Ensure arrays exist for required fields
                for field in ["technical_skills", "soft_skills"]:
                    if field not in corrected_data or not isinstance(corrected_data[field], list):
                        corrected_data[field] = ["Not specified"]
                        fallback_applied = True
                
                # Fix missing career trajectory
                if "career_trajectory" not in corrected_data:
                    corrected_data["career_trajectory"] = {
                        "current_level": "Mid",
                        "progression_speed": "Steady", 
                        "trajectory_type": "Individual Contributor"
                    }
                    fallback_applied = True
            
            elif schema_type == "recruiter":
                # Ensure required arrays exist
                for field in ["strengths", "concerns", "red_flags", "leadership_indicators", "key_themes"]:
                    if field not in corrected_data or not isinstance(corrected_data[field], list):
                        corrected_data[field] = []
                        fallback_applied = True
                
                # Fix missing sentiment
                if "sentiment" not in corrected_data or corrected_data["sentiment"] not in ["positive", "neutral", "negative", "mixed"]:
                    corrected_data["sentiment"] = "neutral"
                    fallback_applied = True
                
                # Fix missing recommendation
                if "recommendation" not in corrected_data or corrected_data["recommendation"] not in ["strong_hire", "hire", "maybe", "no_hire"]:
                    corrected_data["recommendation"] = "maybe"
                    fallback_applied = True
        
        except Exception as e:
            self.logger.error(f"Error applying fallback corrections: {e}")
        
        return corrected_data, fallback_applied
    
    def validate_llm_output(self, data: Dict, schema_type: str, apply_fallbacks: bool = True) -> ValidationResult:
        """Main validation method for LLM outputs"""
        self.logger.info(f"Validating {schema_type} output")
        
        result = ValidationResult(is_valid=False, quality_score=0.0)
        
        try:
            # Initial schema validation
            is_valid, errors = self.validate_schema(data, schema_type)
            result.errors.extend(errors)
            
            # Apply fallback corrections if needed and requested
            working_data = data
            if not is_valid and apply_fallbacks:
                working_data, fallback_applied = self.apply_fallback_corrections(data, schema_type)
                result.fallback_applied = fallback_applied
                
                if fallback_applied:
                    # Re-validate after corrections
                    is_valid, fallback_errors = self.validate_schema(working_data, schema_type)
                    if not is_valid:
                        result.errors.extend([f"Post-fallback: {err}" for err in fallback_errors])
            
            # Calculate quality metrics
            metrics = self.calculate_quality_metrics(working_data, schema_type)
            result.metrics = {
                "completeness": metrics.completeness_score,
                "consistency": metrics.consistency_score,
                "schema_compliance": metrics.schema_compliance_score,
                "content_quality": metrics.content_quality_score,
                "overall": metrics.overall_score
            }
            
            result.quality_score = metrics.overall_score
            result.validated_data = working_data
            
            # Determine if result is acceptable
            result.is_valid = is_valid and result.quality_score >= self.min_quality_threshold
            
            # Add warnings for low quality scores
            if result.quality_score < self.warning_threshold:
                result.warnings.append(f"Quality score ({result.quality_score:.2f}) below warning threshold ({self.warning_threshold})")
            
            if result.fallback_applied:
                result.warnings.append("Fallback corrections were applied to fix validation issues")
            
            self.logger.info(f"Validation complete - Valid: {result.is_valid}, Quality: {result.quality_score:.2f}")
            
        except Exception as e:
            result.errors.append(f"Validation failed: {str(e)}")
            self.logger.error(f"Validation error: {e}")
        
        return result
    
    def validate_resume_analysis(self, analysis: Union[ResumeAnalysis, Dict]) -> ValidationResult:
        """Validate resume analysis output"""
        if isinstance(analysis, ResumeAnalysis):
            data = analysis.to_dict()
        else:
            data = analysis
        
        return self.validate_llm_output(data, "resume")
    
    def validate_recruiter_insights(self, insights: Union[RecruiterInsights, Dict]) -> ValidationResult:
        """Validate recruiter insights output"""
        if isinstance(insights, RecruiterInsights):
            data = insights.to_dict()
        else:
            data = insights
        
        return self.validate_llm_output(data, "recruiter")


def main():
    """CLI interface for validation testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='LLM Output Quality Validator')
    parser.add_argument('file', help='JSON file to validate')
    parser.add_argument('--type', choices=['resume', 'recruiter'], required=True,
                       help='Type of data to validate')
    parser.add_argument('--no-fallbacks', action='store_true',
                       help='Disable fallback corrections')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    
    args = parser.parse_args()
    
    # Initialize validator
    validator = LLMOutputValidator(log_level=args.log_level)
    
    # Load and validate data
    try:
        with open(args.file, 'r') as f:
            data = json.load(f)
        
        result = validator.validate_llm_output(
            data, 
            args.type, 
            apply_fallbacks=not args.no_fallbacks
        )
        
        # Print results
        print(f"\n{'='*60}")
        print(f"VALIDATION RESULTS FOR {args.type.upper()}")
        print(f"{'='*60}")
        print(f"Valid: {result.is_valid}")
        print(f"Quality Score: {result.quality_score:.3f}")
        print(f"Fallback Applied: {result.fallback_applied}")
        
        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors:
                print(f"  ❌ {error}")
        
        if result.warnings:
            print(f"\nWarnings ({len(result.warnings)}):")
            for warning in result.warnings:
                print(f"  ⚠️  {warning}")
        
        print("\nQuality Metrics:")
        for metric, score in result.metrics.items():
            print(f"  {metric.title()}: {score:.3f}")
        
        return 0 if result.is_valid else 1
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())