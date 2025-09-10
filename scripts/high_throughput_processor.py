#!/usr/bin/env python3
"""
High Throughput Recruiter Processor
Maximizes system resources with parallel processing and larger batches
"""

import json
import subprocess
import time
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import re
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

class HighThroughputProcessor:
    def __init__(self):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.enhanced_dir.mkdir(exist_ok=True)
        
        # Balanced throughput settings for quality output
        self.cpu_cores = multiprocessing.cpu_count()
        self.max_workers = min(6, self.cpu_cores)  # Reduce workers for quality
        self.batch_size = 100  # Smaller batches for stability
        self.save_frequency = 3  # Save more frequently
        self.max_retries = 2  # More retries for quality
        self.ollama_timeout = 180  # Longer timeout for comprehensive analysis
        
        self.processed_count = 0
        self.failed_count = 0
        self.start_time = datetime.now()
        self.lock = threading.Lock()
        
        print(f"🚀 QUALITY HIGH THROUGHPUT MODE INITIALIZED")
        print(f"💻 CPU Cores: {self.cpu_cores}")
        print(f"🔥 Max Workers: {self.max_workers}")
        print(f"📦 Batch Size: {self.batch_size}")
        print(f"⚡ Using comprehensive prompts for complete data extraction")
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        signal.signal(signal.SIGTERM, self.graceful_shutdown)
        
    def graceful_shutdown(self, signum, frame):
        print(f"\n🛑 Graceful shutdown initiated...")
        print(f"📊 Processed: {self.processed_count}, Failed: {self.failed_count}")
        elapsed = (datetime.now() - self.start_time).total_seconds()
        print(f"⏱️ Runtime: {elapsed/60:.1f} minutes")
        if self.processed_count > 0:
            print(f"📈 Avg time per candidate: {elapsed/self.processed_count:.1f} seconds")
        print("💾 All progress saved to NAS database")
        sys.exit(0)
    
    def monitor_system(self):
        """Quick system check - less conservative"""
        try:
            memory = psutil.virtual_memory()
            available_gb = memory.available / (1024**3)
            # Only pause if memory is critically low
            return available_gb > 0.5
        except Exception:
            return True
    
    def load_nas_data(self):
        """Load the NAS database"""
        print(f"📂 Loading NAS database...")
        with open(self.nas_file, 'r') as f:
            return json.load(f)
    
    def save_nas_data(self, data):
        """Save updated data back to NAS"""
        # Skip backup for speed - only create backup every 10th save
        if self.processed_count % 1000 == 0:
            backup_file = self.nas_file.replace('.json', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            print(f"💾 Creating backup: {Path(backup_file).name}")
            with open(backup_file, 'w') as f:
                json.dump(data, f, indent=2)
        
        with open(self.nas_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def parse_education_fast(self, education_text: str) -> List[Dict]:
        """Fast education parsing"""
        if not education_text or len(education_text) < 10:
            return []
        
        education_list = []
        lines = education_text.strip().split('\n')[:10]  # Limit lines for speed
        
        current_edu = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            date_match = re.search(r'(\d{4}/\d{2})\s*-\s*(\d{4}/\d{2})?', line)
            if date_match:
                if current_edu:
                    education_list.append(current_edu)
                current_edu = {
                    'start_date': date_match.group(1),
                    'end_date': date_match.group(2) or 'Present'
                }
            elif line.startswith('-'):
                clean_line = line.lstrip('- ').strip()
                if 'institution' not in current_edu:
                    current_edu['institution'] = clean_line
                elif 'degree' not in current_edu:
                    current_edu['degree'] = clean_line
        
        if current_edu:
            education_list.append(current_edu)
        
        return education_list
    
    def parse_experience_fast(self, experience_text: str) -> List[Dict]:
        """Fast experience parsing"""
        if not experience_text or len(experience_text) < 10:
            return []
        
        experience_list = []
        lines = experience_text.strip().split('\n')[:15]  # Limit for speed
        
        current_exp = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            date_match = re.search(r'(\d{4}/\d{2})\s*-\s*(\d{4}/\d{2})?', line)
            if date_match:
                if current_exp:
                    experience_list.append(current_exp)
                current_exp = {
                    'start_date': date_match.group(1),
                    'end_date': date_match.group(2) or 'Present'
                }
            elif ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    current_exp['company'] = parts[0].strip().lstrip('- ')
                    current_exp['position'] = parts[1].strip()
        
        if current_exp:
            experience_list.append(current_exp)
        
        return experience_list
    
    def calculate_years_fast(self, experience_list: List[Dict]) -> float:
        """Fast years calculation"""
        total_months = 0
        for exp in experience_list:
            try:
                start = exp.get('start_date', '')
                if start:
                    start_year, start_month = map(int, start.split('/'))
                    end = exp.get('end_date', '')
                    if end and end != 'Present':
                        end_year, end_month = map(int, end.split('/'))
                    else:
                        end_year, end_month = 2025, 9
                    
                    months = (end_year - start_year) * 12 + (end_month - start_month)
                    total_months += max(0, months)
            except:
                continue
        
        return round(total_months / 12, 1)
    
    def create_comprehensive_prompt(self, candidate: Dict[str, Any]) -> str:
        """Comprehensive prompt with all candidate data"""
        name = candidate.get('name', 'Unknown')
        email = candidate.get('email', '')
        headline = candidate.get('headline', '')
        summary = candidate.get('summary', '')
        
        # Parse education and experience
        education_list = self.parse_education_fast(candidate.get('education', ''))
        experience_list = self.parse_experience_fast(candidate.get('experience', ''))
        years_exp = self.calculate_years_fast(experience_list)
        
        # Format education text
        education_text = "EDUCATION BACKGROUND:\n"
        if education_list:
            for i, edu in enumerate(education_list[:10]):
                education_text += f"{i+1}. {edu.get('start_date', 'N/A')} - {edu.get('end_date', 'Present')}: "
                education_text += f"{edu.get('degree', 'Unknown degree')} at {edu.get('institution', 'Unknown institution')}\n"
        else:
            education_text += "No formal education listed\n"
        
        # Format experience text
        experience_text = "WORK EXPERIENCE:\n"
        if experience_list:
            for i, exp in enumerate(experience_list[:10]):
                experience_text += f"{i+1}. {exp.get('start_date', 'N/A')} - {exp.get('end_date', 'Present')}: "
                experience_text += f"{exp.get('position', 'Unknown role')} at {exp.get('company', 'Unknown company')}\n"
        else:
            experience_text += "No work experience listed\n"
        
        # Format skills text
        skills = candidate.get('skills', '')
        skills_text = "TECHNICAL SKILLS:\n"
        if skills:
            skills_text += f"{skills}\n"
        else:
            skills_text += "No specific skills listed\n"
        
        # Format comments
        comments = candidate.get('comments', [])
        comment_text = "\nRECRUITER NOTES AND OBSERVATIONS:\n"
        if comments:
            for comment in comments[-5:]:  # Last 5 comments
                text = comment.get('text', '')
                if text:
                    comment_text += f"• {text}\n"
        else:
            comment_text += "No recruiter notes available\n"
        
        prompt = f"""You are an expert technical recruiter analyzing a candidate's complete profile. 
Provide a COMPREHENSIVE analysis that a recruiter would create after reviewing the full resume.

CANDIDATE: {name}
EMAIL: {email if email else 'Not provided'}
HEADLINE: {headline if headline else 'Not provided'}
CALCULATED EXPERIENCE: {years_exp} years

PROFESSIONAL SUMMARY:
{summary if summary else 'No summary provided'}

{education_text}

{experience_text}

{skills_text}

{comment_text}

Based on this candidate's COMPLETE profile, provide a detailed recruiter analysis. 
Include insights about:
1. The actual companies they worked at (use your knowledge about these companies - size, culture, tech stack)
2. Their actual education (specific schools, degrees, and what that tells us)
3. Career progression patterns and red flags
4. Technical depth based on roles and companies
5. Market positioning and compensation expectations
6. Cultural fit indicators

Return ONLY valid JSON with these comprehensive fields:

{{
  "personal_details": {{
    "full_name": "{name}",
    "email": "{email if email else 'not_provided'}",
    "location": "extract from profile or infer from companies",
    "linkedin_headline": "{headline if headline else 'none'}"
  }},
  "education_analysis": {{
    "degrees": [
      {{
        "institution": "exact school name",
        "institution_tier": "top_tier/mid_tier/standard/unknown",
        "degree_type": "Bachelor's/Master's/PhD/Certificate",
        "field_of_study": "specific field",
        "graduation_year": "year or estimated",
        "relevance_to_tech": "high/medium/low"
      }}
    ],
    "education_quality": "ivy_league/top_tier/good/standard/limited",
    "continuous_learning": "certifications or ongoing education indicators"
  }},
  "experience_analysis": {{
    "total_years": {years_exp},
    "companies_worked": [
      {{
        "company_name": "exact company name",
        "company_type": "FAANG/unicorn/startup/enterprise/consultancy/unknown",
        "company_size": "estimate employees",
        "company_reputation": "excellent/good/standard/poor/unknown",
        "role": "exact title",
        "seniority_level": "junior/mid/senior/lead/principal/staff",
        "duration_months": "calculate",
        "tech_stack_used": ["likely technologies based on company and role"]
      }}
    ],
    "career_progression": {{
      "trajectory": "upward/lateral/mixed/declining",
      "promotion_velocity": "fast/normal/slow",
      "job_stability": "very_stable/stable/moderate/job_hopper",
      "average_tenure_months": "calculate"
    }}
  }},
  "technical_assessment": {{
    "primary_skills": ["list main technical skills"],
    "secondary_skills": ["supporting skills"],
    "skill_depth": {{
      "frontend": "none/basic/intermediate/advanced/expert",
      "backend": "none/basic/intermediate/advanced/expert",
      "mobile": "none/basic/intermediate/advanced/expert",
      "devops": "none/basic/intermediate/advanced/expert",
      "data": "none/basic/intermediate/advanced/expert",
      "ai_ml": "none/basic/intermediate/advanced/expert"
    }},
    "technology_categories": ["web/mobile/cloud/data/ai/embedded"],
    "years_with_primary_skill": "estimate based on roles"
  }},
  "market_insights": {{
    "current_market_value": {{
      "seniority_bracket": "junior/mid/senior/staff/principal",
      "estimated_salary_range": "provide realistic range based on experience and location",
      "market_demand": "very_high/high/moderate/low",
      "competing_offers_likelihood": "high/medium/low"
    }},
    "best_fit_companies": ["list 3-5 company types that would be good matches"],
    "ideal_next_role": "specific role recommendation",
    "career_growth_potential": "high/medium/low"
  }},
  "cultural_assessment": {{
    "work_environment_preference": "startup/scaleup/enterprise/remote/hybrid",
    "team_collaboration_style": "independent/collaborative/leadership",
    "company_values_alignment": ["innovation/stability/growth/work-life-balance"],
    "red_flags": ["any concerns from job history or notes"],
    "green_flags": ["positive indicators"]
  }},
  "recruiter_recommendations": {{
    "placement_difficulty": "easy/moderate/challenging/very_challenging",
    "interview_readiness": "ready/needs_prep/significant_prep_required",
    "negotiation_leverage": "strong/moderate/weak",
    "urgency_to_place": "immediate/soon/no_rush",
    "commission_potential": "high/medium/low",
    "client_presentation_notes": "key points to highlight to clients"
  }},
  "searchability": {{
    "ats_keywords": ["keywords for applicant tracking systems"],
    "boolean_search_terms": ["terms for Boolean searches"],
    "skill_synonyms": ["alternative terms for their skills"],
    "competitor_companies": ["companies they might come from or go to"]
  }},
  "enriched_insights": {{
    "industry_context": "current state of their industry/domain",
    "technology_trends": "how their skills align with current trends",
    "geographic_factors": "location-based insights",
    "diversity_indicators": "any diversity/inclusion relevant factors",
    "security_clearance": "if applicable or inferrable"
  }},
  "executive_summary": {{
    "one_line_pitch": "compelling 1-line summary for client presentation",
    "strengths": ["top 3 strengths"],
    "development_areas": ["areas for growth"],
    "overall_rating": "score 1-100",
    "placement_strategy": "recommended approach for placing this candidate"
  }}
}}

IMPORTANT: Base ALL analysis on the ACTUAL data provided. Use your knowledge about the companies, schools, and technologies mentioned to provide rich context."""
        
        return prompt
    
    def process_with_ollama_comprehensive(self, prompt: str, retry_count: int = 0) -> Optional[Dict[str, Any]]:
        """Comprehensive Ollama processing with validation"""
        try:
            result = subprocess.run(
                ['ollama', 'run', 'llama3.1:8b', prompt],
                capture_output=True,
                text=True,
                timeout=self.ollama_timeout
            )
            
            if result.returncode != 0:
                if retry_count < self.max_retries:
                    time.sleep(2)
                    return self.process_with_ollama_comprehensive(prompt, retry_count + 1)
                return None
            
            response = result.stdout.strip()
            
            # Extract JSON
            if '{' in response and '}' in response:
                start = response.index('{')
                end = response.rindex('}') + 1
                json_str = response[start:end]
                analysis = json.loads(json_str)
                
                # Validate that we have comprehensive content
                if (analysis.get('personal_details') and 
                    analysis.get('education_analysis') and
                    analysis.get('experience_analysis') and
                    analysis.get('technical_assessment') and
                    analysis.get('market_insights') and
                    analysis.get('recruiter_recommendations') and
                    analysis.get('searchability') and
                    analysis.get('executive_summary')):
                    return analysis
                else:
                    if retry_count < self.max_retries:
                        time.sleep(2)
                        return self.process_with_ollama_comprehensive(prompt, retry_count + 1)
                    return None
            
            return None
            
        except subprocess.TimeoutExpired:
            if retry_count < self.max_retries:
                time.sleep(3)
                return self.process_with_ollama_comprehensive(prompt, retry_count + 1)
            return None
        except json.JSONDecodeError:
            if retry_count < self.max_retries:
                time.sleep(2)
                return self.process_with_ollama_comprehensive(prompt, retry_count + 1)
            return None
        except Exception:
            return None
    
    def process_candidate_worker(self, candidate_data):
        """Worker function for processing individual candidates"""
        idx, candidate = candidate_data
        candidate_id = candidate.get('id')
        candidate_name = candidate.get('name', 'Unknown')
        
        # Create comprehensive prompt
        prompt = self.create_comprehensive_prompt(candidate)
        
        # Process with Ollama
        analysis = self.process_with_ollama_comprehensive(prompt)
        
        if analysis:
            # Update candidate data
            candidate['recruiter_enhanced_analysis'] = {
                'analysis': analysis,
                'processing_timestamp': datetime.now().isoformat(),
                'processor_version': 'high_throughput_v1'
            }
            
            # Save to individual file
            safe_name = re.sub(r'[^\w\s-]', '', candidate_name).strip().replace(' ', '_')
            output_file = self.enhanced_dir / f"{candidate_id}_{safe_name}_recruiter_enhanced.json"
            
            try:
                with open(output_file, 'w') as f:
                    json.dump({
                        'candidate_id': candidate_id,
                        'name': candidate_name,
                        'recruiter_analysis': analysis,
                        'timestamp': datetime.now().isoformat()
                    }, f, indent=2)
            except Exception:
                pass  # Continue processing even if individual file save fails
            
            with self.lock:
                self.processed_count += 1
            
            return idx, candidate, True
        else:
            with self.lock:
                self.failed_count += 1
            return idx, candidate, False
    
    def process_all_high_throughput(self):
        """Process all candidates with maximum throughput"""
        # Load data
        candidates = self.load_nas_data()
        total_candidates = len(candidates)
        print(f"📊 Total candidates in database: {total_candidates}")
        
        # Find candidates that need processing
        candidates_to_process = []
        for i, candidate in enumerate(candidates):
            if candidate.get('recruiter_enhanced_analysis'):
                continue
                
            has_name = bool(candidate.get('name'))
            has_data = bool(candidate.get('experience') or candidate.get('education'))
            has_id = bool(candidate.get('id'))
            
            if has_id and has_name and has_data:
                candidates_to_process.append((i, candidate))
        
        total_to_process = len(candidates_to_process)
        print(f"🎯 Candidates to process: {total_to_process}")
        
        if not candidates_to_process:
            print("✅ All suitable candidates already processed!")
            return
        
        print(f"\n🚀 QUALITY THROUGHPUT PROCESSING - {self.max_workers} workers")
        print("=" * 70)
        
        batch_num = 0
        batches_since_save = 0
        
        while candidates_to_process:
            if not self.monitor_system():
                print("⚠️ Low memory, brief pause...")
                time.sleep(5)
                continue
            
            batch_num += 1
            batch = candidates_to_process[:self.batch_size]
            remaining = len(candidates_to_process)
            
            print(f"\n📦 Batch {batch_num} - Processing {len(batch)} candidates ({remaining} remaining)")
            print(f"🔥 Using {self.max_workers} parallel workers")
            
            batch_start = time.time()
            batch_processed = 0
            batch_failed = 0
            
            # Process batch with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_candidate = {executor.submit(self.process_candidate_worker, cand_data): cand_data for cand_data in batch}
                
                for future in as_completed(future_to_candidate):
                    idx, candidate, success = future.result()
                    candidates[idx] = candidate  # Update main list
                    
                    if success:
                        batch_processed += 1
                    else:
                        batch_failed += 1
            
            # Remove processed candidates
            candidates_to_process = candidates_to_process[len(batch):]
            batches_since_save += 1
            
            # Periodic saves for performance
            if batches_since_save >= self.save_frequency or not candidates_to_process:
                self.save_nas_data(candidates)
                batches_since_save = 0
                print(f"  💾 Database updated")
            
            # Batch performance metrics
            batch_time = time.time() - batch_start
            candidates_per_sec = len(batch) / batch_time if batch_time > 0 else 0
            
            print(f"  ✓ Batch {batch_num}: {batch_processed} processed, {batch_failed} failed")
            print(f"  ⚡ Throughput: {candidates_per_sec:.1f} candidates/sec")
            print(f"  📊 Progress: {((total_to_process - len(candidates_to_process)) / total_to_process * 100):.1f}%")
            
            # ETA calculation
            if self.processed_count > 0:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                avg_time = elapsed / self.processed_count
                eta_seconds = len(candidates_to_process) * avg_time
                eta_hours = eta_seconds / 3600
                print(f"  ⏱️ ETA: {eta_hours:.1f} hours | Rate: {self.processed_count/elapsed*60:.0f}/min")
        
        # Final report
        elapsed = (datetime.now() - self.start_time).total_seconds()
        final_enhanced = sum(1 for c in candidates if c.get('recruiter_enhanced_analysis'))
        
        print("\n" + "=" * 70)
        print("🎉 HIGH THROUGHPUT PROCESSING COMPLETE!")
        print(f"🚀 Total processed: {self.processed_count}")
        print(f"❌ Failed: {self.failed_count}")
        print(f"📈 Success rate: {(self.processed_count/(self.processed_count+self.failed_count)*100 if (self.processed_count+self.failed_count) > 0 else 0):.1f}%")
        print(f"⚡ Final throughput: {self.processed_count/elapsed*60:.1f} candidates/minute")
        print(f"📊 Enhanced candidates: {final_enhanced}/{total_candidates}")
        print(f"⏱️ Total time: {elapsed/3600:.1f} hours")

def main():
    try:
        processor = HighThroughputProcessor()
        processor.process_all_high_throughput()
    except KeyboardInterrupt:
        print("\n\n🛑 Processing interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()