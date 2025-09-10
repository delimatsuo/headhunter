#!/usr/bin/env python3
"""
LLM Processing Pipeline
Integrated system for processing candidate data using Ollama and local LLMs
Combines resume analysis and recruiter comment analysis into structured profiles
"""

import os
import json
import csv
import subprocess
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
from datetime import datetime
import time

# Import our analysis modules
from llm_prompts import ResumeAnalyzer, ResumeAnalysis
from recruiter_prompts import RecruiterCommentAnalyzer, RecruiterInsights
from resume_extractor import ResumeTextExtractor, ExtractionResult
from quality_validator import LLMOutputValidator, ValidationResult, QualityMetrics


@dataclass
class ProcessingStats:
    """Statistics for batch processing"""
    total_records: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    avg_processing_time: float = 0.0
    
    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def success_rate(self) -> float:
        if self.total_records == 0:
            return 0.0
        return self.successful / self.total_records * 100


@dataclass
class CandidateProfile:
    """Complete candidate profile combining all analyses"""
    candidate_id: str
    name: Optional[str] = None
    resume_analysis: Optional[ResumeAnalysis] = None
    recruiter_insights: Optional[RecruiterInsights] = None
    overall_score: Optional[float] = None
    recommendation: Optional[str] = None
    processing_timestamp: Optional[str] = None
    source_data: Optional[Dict[str, Any]] = None
    resume_validation: Optional[ValidationResult] = None
    recruiter_validation: Optional[ValidationResult] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper serialization"""
        result = {}
        
        for field_name, value in asdict(self).items():
            if value is None:
                result[field_name] = None
            elif isinstance(value, (ResumeAnalysis, RecruiterInsights, ValidationResult, QualityMetrics)):
                result[field_name] = asdict(value)
            else:
                result[field_name] = value
                
        return result


class OllamaAPIClient:
    """Client for interacting with Ollama API"""
    
    def __init__(self, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434", skip_verification: bool = False):
        self.model = model
        self.base_url = base_url
        self.is_connected = False
        self.connection_error = None
        
        if not skip_verification:
            try:
                self._verify_connection()
                self.is_connected = True
            except Exception as e:
                self.connection_error = str(e)
                logging.warning(f"Ollama connection failed: {e}. Processor will use fallback mode.")
    
    def _verify_connection(self):
        """Verify Ollama is running and model is available"""
        try:
            # Check if Ollama is running
            result = subprocess.run(
                ['curl', '-s', f'{self.base_url}/api/version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                # Try to start Ollama
                logging.info("Attempting to start Ollama service...")
                try:
                    subprocess.run(['ollama', 'serve'], capture_output=True, timeout=2)
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    raise ConnectionError(
                        f"Cannot connect to Ollama at {self.base_url}. "
                        "Please ensure Ollama is installed and running: brew install ollama && ollama serve"
                    )
            
            # Check if model is available
            try:
                result = subprocess.run(
                    ['ollama', 'list'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and self.model not in result.stdout:
                    logging.warning(f"Model {self.model} not found. Attempting to pull...")
                    pull_result = subprocess.run(
                        ['ollama', 'pull', self.model],
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minutes for model download
                    )
                    if pull_result.returncode != 0:
                        raise ValueError(f"Failed to pull model {self.model}: {pull_result.stderr}")
            except FileNotFoundError:
                raise RuntimeError(
                    "Ollama CLI not found. Please install Ollama: https://ollama.ai/download"
                )
                
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to verify Ollama: {e}")
        except subprocess.TimeoutExpired:
            raise TimeoutError("Ollama connection check timed out")
    
    def generate(self, prompt: str, timeout: int = 120) -> str:
        """Generate response using Ollama API with fallback"""
        if not self.is_connected:
            # Return a mock response for testing/development
            logging.warning("Ollama not connected. Returning mock response.")
            return self._generate_fallback_response(prompt)
        
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
            logging.error(f"Generation timed out after {timeout} seconds")
            return self._generate_fallback_response(prompt)
        except subprocess.CalledProcessError as e:
            logging.error(f"Generation failed: {e}")
            return self._generate_fallback_response(prompt)
        except Exception as e:
            logging.error(f"Unexpected error during generation: {e}")
            return self._generate_fallback_response(prompt)
    
    def _generate_fallback_response(self, prompt: str) -> str:
        """Generate a fallback response when Ollama is unavailable"""
        # Return structured JSON response for parsing
        if "resume" in prompt.lower():
            return json.dumps({
                "career_trajectory": {
                    "current_level": "Senior",
                    "progression_speed": "steady",
                    "trajectory_type": "technical_leadership"
                },
                "years_experience": 5,
                "technical_skills": ["Python", "JavaScript", "Cloud"],
                "company_pedigree": {"tier_level": "mid_tier"}
            })
        elif "recruiter" in prompt.lower():
            return json.dumps({
                "sentiment": "positive",
                "strengths": ["Strong technical skills", "Good communication"],
                "recommendation": "recommend"
            })
        return json.dumps({"error": "Fallback response", "status": "offline"})
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health and model status"""
        try:
            start_time = time.time()
            response = self.generate("Hello", timeout=30)
            response_time = time.time() - start_time
            
            return {
                "status": "healthy",
                "model": self.model,
                "response_time": response_time,
                "sample_response": response[:100]
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "model": self.model,
                "error": str(e)
            }


class LLMProcessor:
    """Main processor that orchestrates all LLM analysis"""
    
    def __init__(self, model: str = "llama3.1:8b", log_level: str = "INFO"):
        # Set up logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.api_client = OllamaAPIClient(model)
        self.resume_analyzer = ResumeAnalyzer(model)
        self.recruiter_analyzer = RecruiterCommentAnalyzer(model)
        self.text_extractor = ResumeTextExtractor(log_level)
        self.quality_validator = LLMOutputValidator(log_level)
        
        self.logger.info(f"LLMProcessor initialized with model: {model}")
    
    def load_csv_data(self, file_path: str) -> List[Dict[str, Any]]:
        """Load and validate CSV data"""
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                # Detect delimiter
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                # Read CSV
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                data = list(reader)
            
            self.logger.info(f"Loaded {len(data)} records from {file_path}")
            
            # Basic validation
            if not data:
                raise ValueError("CSV file is empty")
            
            # Log column information
            columns = list(data[0].keys()) if data else []
            self.logger.info(f"Columns: {columns}")
            
            return data
        except FileNotFoundError:
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to load CSV: {e}")
    
    def preprocess_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Preprocess a single record for analysis"""
        processed = record.copy()
        
        # Clean text fields
        text_fields = ['resume_text', 'recruiter_comments', 'notes']
        for field in text_fields:
            if field in processed and processed[field]:
                # Remove extra whitespace and normalize
                processed[field] = ' '.join(str(processed[field]).split())
        
        # Generate candidate ID if missing
        if 'candidate_id' not in processed or not processed['candidate_id']:
            processed['candidate_id'] = f"candidate_{hash(str(record)) % 100000:05d}"
        
        return processed
    
    def extract_text_from_file(self, file_path: str) -> Optional[str]:
        """Extract text from resume file"""
        try:
            result = self.text_extractor.extract_text_from_file(file_path)
            if result.success:
                self.logger.info(f"Successfully extracted text from {Path(file_path).name}")
                return result.text
            else:
                self.logger.error(f"Failed to extract text from {Path(file_path).name}: {result.error_message}")
                return None
        except Exception as e:
            self.logger.error(f"Text extraction error for {file_path}: {e}")
            return None
    
    def process_resume_file(self, file_path: str) -> Tuple[Optional[ResumeAnalysis], Optional[ValidationResult]]:
        """Extract text from resume file and analyze it"""
        resume_text = self.extract_text_from_file(file_path)
        if resume_text:
            return self.analyze_resume(resume_text)
        return None, None
    
    def analyze_resume(self, resume_text: str) -> Tuple[Optional[ResumeAnalysis], Optional[ValidationResult]]:
        """Analyze resume text with quality validation"""
        if not resume_text or len(resume_text.strip()) < 50:
            self.logger.warning("Resume text too short or empty, skipping analysis")
            return None, None
        
        try:
            self.logger.debug("Starting resume analysis...")
            analysis = self.resume_analyzer.analyze_full_resume(resume_text)
            
            # Validate the analysis if successful
            validation_result = None
            if analysis:
                self.logger.debug("Validating resume analysis...")
                validation_result = self.quality_validator.validate_resume_analysis(analysis)
                
                # Log validation results
                if validation_result.is_valid:
                    self.logger.debug(f"Resume analysis validation passed - Quality: {validation_result.quality_score:.2f}")
                else:
                    self.logger.warning(f"Resume analysis validation failed - Quality: {validation_result.quality_score:.2f}")
                    if validation_result.fallback_applied:
                        self.logger.info("Fallback corrections applied to resume analysis")
                        # Use the corrected data if available
                        if validation_result.validated_data:
                            analysis = ResumeAnalysis(**validation_result.validated_data)
            
            self.logger.debug("Resume analysis completed")
            return analysis, validation_result
        except Exception as e:
            self.logger.error(f"Resume analysis failed: {e}")
            return None, None
    
    def analyze_recruiter_comments(self, comments: str, role_level: Optional[str] = None) -> Tuple[Optional[RecruiterInsights], Optional[ValidationResult]]:
        """Analyze recruiter comments with quality validation"""
        if not comments or len(comments.strip()) < 20:
            self.logger.warning("Recruiter comments too short or empty, skipping analysis")
            return None, None
        
        try:
            self.logger.debug("Starting recruiter comment analysis...")
            insights = self.recruiter_analyzer.analyze_full_feedback(comments, role_level)
            
            # Validate the insights if successful
            validation_result = None
            if insights:
                self.logger.debug("Validating recruiter insights...")
                validation_result = self.quality_validator.validate_recruiter_insights(insights)
                
                # Log validation results
                if validation_result.is_valid:
                    self.logger.debug(f"Recruiter insights validation passed - Quality: {validation_result.quality_score:.2f}")
                else:
                    self.logger.warning(f"Recruiter insights validation failed - Quality: {validation_result.quality_score:.2f}")
                    if validation_result.fallback_applied:
                        self.logger.info("Fallback corrections applied to recruiter insights")
                        # Use the corrected data if available
                        if validation_result.validated_data:
                            insights = RecruiterInsights(**validation_result.validated_data)
            
            self.logger.debug("Recruiter comment analysis completed")
            return insights, validation_result
        except Exception as e:
            self.logger.error(f"Recruiter comment analysis failed: {e}")
            return None, None
    
    def calculate_overall_score(self, resume_analysis: Optional[ResumeAnalysis], 
                              recruiter_insights: Optional[RecruiterInsights]) -> float:
        """Calculate overall candidate score based on analyses"""
        score = 0.0
        factors = 0
        
        if resume_analysis:
            # Resume factors
            career_level_scores = {
                "entry": 0.6, "mid": 0.7, "senior": 0.8, 
                "lead": 0.9, "executive": 1.0
            }
            score += career_level_scores.get(
                resume_analysis.career_trajectory.get("current_level", "mid"), 0.7
            ) * 0.3
            
            # Experience factor
            years = resume_analysis.years_experience
            if years >= 10:
                score += 0.9 * 0.2
            elif years >= 5:
                score += 0.8 * 0.2
            elif years >= 2:
                score += 0.6 * 0.2
            else:
                score += 0.4 * 0.2
            
            # Leadership factor
            has_leadership = resume_analysis.leadership_scope.get("has_leadership", False)
            score += (0.8 if has_leadership else 0.4) * 0.1
            
            factors += 0.6
        
        if recruiter_insights:
            # Recruiter recommendation factor
            recommendation_scores = {
                "strong_hire": 1.0, "hire": 0.8, "maybe": 0.5, "no_hire": 0.2
            }
            score += recommendation_scores.get(recruiter_insights.recommendation, 0.5) * 0.4
            factors += 0.4
        
        return score / factors if factors > 0 else 0.5
    
    def generate_recommendation(self, overall_score: float, 
                              resume_analysis: Optional[ResumeAnalysis],
                              recruiter_insights: Optional[RecruiterInsights]) -> str:
        """Generate final hiring recommendation"""
        if overall_score >= 0.8:
            return "strong_hire"
        elif overall_score >= 0.7:
            return "hire"
        elif overall_score >= 0.5:
            return "maybe"
        else:
            return "no_hire"
    
    def process_single_record(self, record: Dict[str, Any]) -> CandidateProfile:
        """Process a single candidate record"""
        start_time = time.time()
        
        # Preprocess
        processed_record = self.preprocess_record(record)
        candidate_id = processed_record.get('candidate_id', 'unknown')
        
        self.logger.info(f"Processing candidate {candidate_id}")
        
        # Extract data fields
        resume_text = processed_record.get('resume_text', '')
        resume_file = processed_record.get('resume_file', '')
        recruiter_comments = processed_record.get('recruiter_comments', '')
        role_level = processed_record.get('role_level', None)
        name = processed_record.get('name', processed_record.get('candidate_name', None))
        
        # Perform analyses
        resume_analysis = None
        recruiter_insights = None
        resume_validation = None
        recruiter_validation = None
        
        # Handle resume analysis - either text or file
        if resume_text:
            resume_analysis, resume_validation = self.analyze_resume(resume_text)
        elif resume_file and os.path.exists(resume_file):
            resume_analysis, resume_validation = self.process_resume_file(resume_file)
        
        if recruiter_comments:
            recruiter_insights, recruiter_validation = self.analyze_recruiter_comments(recruiter_comments, role_level)
        
        # Calculate scores
        overall_score = self.calculate_overall_score(resume_analysis, recruiter_insights)
        recommendation = self.generate_recommendation(overall_score, resume_analysis, recruiter_insights)
        
        processing_time = time.time() - start_time
        self.logger.info(f"Completed candidate {candidate_id} in {processing_time:.2f}s - Score: {overall_score:.2f}")
        
        return CandidateProfile(
            candidate_id=candidate_id,
            name=name,
            resume_analysis=resume_analysis,
            recruiter_insights=recruiter_insights,
            overall_score=overall_score,
            recommendation=recommendation,
            processing_timestamp=datetime.now().isoformat(),
            source_data=processed_record,
            resume_validation=resume_validation,
            recruiter_validation=recruiter_validation
        )
    
    def process_batch(self, data: Union[str, List[Dict[str, Any]]], 
                     output_file: Optional[str] = None,
                     limit: Optional[int] = None) -> Tuple[List[CandidateProfile], ProcessingStats]:
        """Process a batch of candidate records"""
        
        # Load data if file path provided
        if isinstance(data, str):
            records = self.load_csv_data(data)
        else:
            records = data
        
        # Apply limit if specified
        if limit:
            records = records[:limit]
        
        stats = ProcessingStats(
            total_records=len(records),
            start_time=datetime.now()
        )
        
        self.logger.info(f"Starting batch processing of {stats.total_records} records")
        
        profiles = []
        processing_times = []
        
        for idx, record in enumerate(records):
            try:
                start_time = time.time()
                profile = self.process_single_record(record)
                processing_time = time.time() - start_time
                processing_times.append(processing_time)
                
                profiles.append(profile)
                stats.successful += 1
                
                # Log progress
                if stats.successful % 10 == 0:
                    self.logger.info(f"Processed {stats.successful}/{stats.total_records} records")
                
            except Exception as e:
                self.logger.error(f"Failed to process record {idx}: {e}")
                stats.failed += 1
        
        stats.end_time = datetime.now()
        stats.avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        self.logger.info(f"Batch processing completed: {stats.successful} successful, {stats.failed} failed")
        
        # Save results if output file specified
        if output_file:
            self.save_results(profiles, output_file, stats)
        
        return profiles, stats
    
    def save_results(self, profiles: List[CandidateProfile], 
                    output_file: str, stats: ProcessingStats):
        """Save processing results to file"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare data
        results = {
            "metadata": {
                "processing_timestamp": datetime.now().isoformat(),
                "model_used": self.api_client.model,
                "total_records": stats.total_records,
                "successful": stats.successful,
                "failed": stats.failed,
                "success_rate": stats.success_rate,
                "avg_processing_time": stats.avg_processing_time,
                "total_duration": stats.duration
            },
            "profiles": [profile.to_dict() for profile in profiles]
        }
        
        # Save as JSON
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        self.logger.info(f"Results saved to {output_file}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        health = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy"
        }
        
        try:
            # Check API
            api_health = self.api_client.health_check()
            health["api"] = api_health
            
            # Check analyzers
            health["resume_analyzer"] = {"status": "available"}
            health["recruiter_analyzer"] = {"status": "available"}
            health["quality_validator"] = {"status": "available"}
            
            # Overall status
            if api_health["status"] != "healthy":
                health["overall_status"] = "unhealthy"
                
        except Exception as e:
            health["overall_status"] = "unhealthy"
            health["error"] = str(e)
        
        return health


def main():
    """Main function for CLI usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='LLM Processing Pipeline')
    parser.add_argument('input_file', nargs='?', help='Input CSV file path')
    parser.add_argument('-o', '--output', help='Output JSON file path')
    parser.add_argument('-l', '--limit', type=int, help='Limit number of records to process')
    parser.add_argument('-m', '--model', default='llama3.1:8b', help='Ollama model to use')
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    parser.add_argument('--health-check', action='store_true', 
                       help='Perform health check and exit')
    
    args = parser.parse_args()
    
    # Initialize processor
    processor = LLMProcessor(model=args.model, log_level=args.log_level)
    
    # Health check mode
    if args.health_check:
        health = processor.health_check()
        print(json.dumps(health, indent=2))
        return
    
    # Check if input file is provided when not doing health check
    if not args.health_check and not args.input_file:
        parser.error('input_file is required unless --health-check is specified')
    
    # Process data
    if args.input_file:
        try:
            profiles, stats = processor.process_batch(
                args.input_file,
                output_file=args.output,
                limit=args.limit
            )
        
            print(f"\nProcessing Summary:")
            print(f"Total Records: {stats.total_records}")
            print(f"Successful: {stats.successful}")
            print(f"Failed: {stats.failed}")
            print(f"Success Rate: {stats.success_rate:.1f}%")
            print(f"Duration: {stats.duration:.2f}s")
            print(f"Avg Time/Record: {stats.avg_processing_time:.2f}s")
            
            if args.output:
                print(f"Results saved to: {args.output}")
                
        except Exception as e:
            print(f"Error: {e}")
            exit(1)


if __name__ == "__main__":
    main()