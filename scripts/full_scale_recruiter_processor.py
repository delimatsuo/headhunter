#!/usr/bin/env python3
"""
Full Scale Recruiter Enhanced Processor
Processes ALL 29,138 candidates with comprehensive analysis
Includes system monitoring and intelligent batching
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

class FullScaleRecruiterProcessor:
    def __init__(self):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.enhanced_dir.mkdir(exist_ok=True)
        self.batch_size = 50  # Larger batches for efficiency
        self.max_retries = 2
        self.processed_count = 0
        self.failed_count = 0
        self.start_time = datetime.now()
        
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
        """Monitor system resources and adjust if needed"""
        try:
            memory = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=1)
            
            # Memory check
            available_gb = memory.available / (1024**3)
            if available_gb < 1.0:  # Less than 1GB available
                print(f"  ⚠️ Low memory: {available_gb:.1f}GB available")
                return False
            
            # CPU check
            if cpu > 90:
                print(f"  ⚠️ High CPU usage: {cpu}%")
                time.sleep(2)
            
            return True
            
        except Exception:
            # Fallback if psutil fails
            return True
    
    def load_nas_data(self):
        """Load the NAS database"""
        print(f"📂 Loading NAS database...")
        with open(self.nas_file, 'r') as f:
            return json.load(f)
    
    def save_nas_data(self, data):
        """Save updated data back to NAS with backup"""
        backup_file = self.nas_file.replace('.json', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        print(f"💾 Creating backup: {Path(backup_file).name}")
        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Updating NAS database...")
        with open(self.nas_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def parse_education(self, education_text: str) -> List[Dict]:
        """Parse education text into structured format"""
        if not education_text or education_text == '':
            return []
        
        education_list = []
        lines = education_text.strip().split('\n')
        
        current_edu = {}
        for line in lines:
            line = line.strip()
            if not line or line == '-':
                continue
                
            # Check for date pattern
            date_pattern = r'(\d{4}/\d{2})\s*-\s*(\d{4}/\d{2})?'
            date_match = re.search(date_pattern, line)
            
            if date_match:
                if current_edu:
                    education_list.append(current_edu)
                current_edu = {
                    'start_date': date_match.group(1),
                    'end_date': date_match.group(2) if date_match.group(2) else 'Present'
                }
            elif line.startswith('-'):
                # This is likely a school or degree line
                clean_line = line.lstrip('- ').strip()
                if 'institution' not in current_edu and clean_line:
                    current_edu['institution'] = clean_line
                elif 'degree' not in current_edu and clean_line:
                    current_edu['degree'] = clean_line
            else:
                # Could be institution or degree
                if 'institution' not in current_edu:
                    current_edu['institution'] = line
                elif 'degree' not in current_edu:
                    current_edu['degree'] = line
                elif 'field' not in current_edu:
                    current_edu['field'] = line
        
        if current_edu:
            education_list.append(current_edu)
        
        return education_list
    
    def parse_experience(self, experience_text: str) -> List[Dict]:
        """Parse experience text into structured format"""
        if not experience_text or experience_text == '':
            return []
        
        experience_list = []
        lines = experience_text.strip().split('\n')
        
        current_exp = {}
        for line in lines:
            line = line.strip()
            if not line or line == '-':
                continue
            
            # Check for date pattern
            date_pattern = r'(\d{4}/\d{2})\s*-\s*(\d{4}/\d{2})?'
            date_match = re.search(date_pattern, line)
            
            if date_match:
                if current_exp:
                    experience_list.append(current_exp)
                current_exp = {
                    'start_date': date_match.group(1),
                    'end_date': date_match.group(2) if date_match.group(2) else 'Present'
                }
            elif ':' in line:
                # Company : Position format
                parts = line.split(':', 1)
                if len(parts) == 2:
                    company = parts[0].strip().lstrip('- ')
                    position = parts[1].strip()
                    if company:
                        current_exp['company'] = company
                    if position:
                        current_exp['position'] = position
            elif line.startswith('-'):
                clean_line = line.lstrip('- ').strip()
                if 'company' not in current_exp and clean_line:
                    current_exp['company'] = clean_line
                elif 'position' not in current_exp and clean_line:
                    current_exp['position'] = clean_line
        
        if current_exp:
            experience_list.append(current_exp)
        
        return experience_list
    
    def calculate_years_experience(self, experience_list: List[Dict]) -> float:
        """Calculate total years of experience"""
        total_months = 0
        
        for exp in experience_list:
            start = exp.get('start_date', '')
            end = exp.get('end_date', '')
            
            if start:
                try:
                    start_year, start_month = map(int, start.split('/'))
                    
                    if end and end != 'Present':
                        end_year, end_month = map(int, end.split('/'))
                    else:
                        # Current date
                        end_year = 2025
                        end_month = 9
                    
                    months = (end_year - start_year) * 12 + (end_month - start_month)
                    total_months += max(0, months)
                except:
                    continue
        
        return round(total_months / 12, 1)
    
    def create_recruiter_prompt(self, candidate: Dict[str, Any]) -> str:
        """Create comprehensive prompt for recruiter-level analysis"""
        name = candidate.get('name', 'Unknown')
        email = candidate.get('email', '')
        headline = candidate.get('headline', '')
        summary = candidate.get('summary', '')
        
        # Parse structured data
        education_raw = candidate.get('education', '')
        experience_raw = candidate.get('experience', '')
        skills_raw = candidate.get('skills', '')
        
        education_list = self.parse_education(education_raw)
        experience_list = self.parse_experience(experience_raw)
        years_exp = self.calculate_years_experience(experience_list)
        
        # Format education for prompt
        education_text = "EDUCATION DETAILS:\n"
        if education_list:
            for edu in education_list:
                education_text += f"• {edu.get('institution', 'Unknown School')}\n"
                education_text += f"  Degree: {edu.get('degree', 'N/A')}\n"
                education_text += f"  Field: {edu.get('field', 'N/A')}\n"
                education_text += f"  Period: {edu.get('start_date', 'N/A')} - {edu.get('end_date', 'N/A')}\n\n"
        else:
            education_text += "No formal education listed\n"
        
        # Format experience for prompt
        experience_text = "PROFESSIONAL EXPERIENCE:\n"
        if experience_list:
            for exp in experience_list:
                experience_text += f"• {exp.get('company', 'Unknown Company')}\n"
                experience_text += f"  Position: {exp.get('position', 'N/A')}\n"
                experience_text += f"  Period: {exp.get('start_date', 'N/A')} - {exp.get('end_date', 'N/A')}\n\n"
        else:
            experience_text += "No work experience listed\n"
        
        # Format skills
        skills_text = "TECHNICAL SKILLS:\n"
        if skills_raw:
            skills_text += skills_raw
        else:
            skills_text += "No specific skills listed\n"
        
        # Format comments (limit to save processing time)
        comments = candidate.get('comments', [])
        comment_text = "\nKEY RECRUITER NOTES:\n"
        if comments:
            for comment in comments[-3:]:  # Last 3 comments for efficiency
                text = comment.get('text', '')
                if text:
                    comment_text += f"• {text[:100]}...\n"
        else:
            comment_text += "No recruiter notes\n"
        
        prompt = f"""You are an expert technical recruiter. Analyze this candidate's profile and provide comprehensive JSON analysis for searchability.

CANDIDATE: {name}
EXPERIENCE: {years_exp} years

{education_text}

{experience_text}

{skills_text}

{comment_text}

Provide detailed recruiter analysis in JSON format with these exact fields:

{{
  "personal_details": {{
    "full_name": "{name}",
    "email": "{email if email else 'not_provided'}",
    "location": "infer from companies",
    "linkedin_headline": "{headline if headline else 'none'}"
  }},
  "education_analysis": {{
    "degrees": [list parsed degrees with institution, degree, field, year],
    "education_quality": "top_tier/good/standard/limited",
    "continuous_learning": "certifications noted"
  }},
  "experience_analysis": {{
    "total_years": {years_exp},
    "companies_worked": [list with company_name, company_type, role, seniority_level, duration_months],
    "career_progression": {{
      "trajectory": "upward/lateral/mixed",
      "promotion_velocity": "fast/normal/slow",
      "job_stability": "stable/moderate/job_hopper"
    }}
  }},
  "technical_assessment": {{
    "primary_skills": [extract main skills],
    "skill_depth": {{
      "frontend": "none/basic/intermediate/advanced",
      "backend": "none/basic/intermediate/advanced", 
      "mobile": "none/basic/intermediate/advanced",
      "devops": "none/basic/intermediate/advanced",
      "data": "none/basic/intermediate/advanced",
      "ai_ml": "none/basic/intermediate/advanced"
    }},
    "years_with_primary_skill": estimate
  }},
  "market_insights": {{
    "current_market_value": {{
      "seniority_bracket": "junior/mid/senior/staff",
      "estimated_salary_range": "realistic range",
      "market_demand": "high/moderate/low"
    }},
    "best_fit_companies": [3 company types],
    "ideal_next_role": "specific recommendation"
  }},
  "cultural_assessment": {{
    "work_environment_preference": "startup/enterprise/remote",
    "red_flags": [any concerns],
    "green_flags": [positive indicators]
  }},
  "recruiter_recommendations": {{
    "placement_difficulty": "easy/moderate/challenging",
    "commission_potential": "high/medium/low",
    "client_presentation_notes": "key selling points"
  }},
  "searchability": {{
    "ats_keywords": [keywords for searches],
    "boolean_search_terms": [search terms],
    "competitor_companies": [relevant companies]
  }},
  "executive_summary": {{
    "one_line_pitch": "compelling summary",
    "overall_rating": score_1_to_100,
    "placement_strategy": "recommended approach"
  }}
}}

IMPORTANT: Base analysis on ACTUAL data provided. Return ONLY valid JSON."""
        
        return prompt
    
    def process_with_ollama(self, prompt: str, retry_count: int = 0) -> Optional[Dict[str, Any]]:
        """Process with Ollama with retry logic"""
        try:
            result = subprocess.run(
                ['ollama', 'run', 'llama3.1:8b', prompt],
                capture_output=True,
                text=True,
                timeout=90  # Faster timeout for scale
            )
            
            if result.returncode != 0:
                if retry_count < self.max_retries:
                    time.sleep(2)
                    return self.process_with_ollama(prompt, retry_count + 1)
                return None
            
            response = result.stdout.strip()
            
            # Extract JSON
            if '{' in response and '}' in response:
                start = response.index('{')
                end = response.rindex('}') + 1
                json_str = response[start:end]
                analysis = json.loads(json_str)
                
                # Quick validation
                if analysis.get('personal_details') and analysis.get('executive_summary'):
                    return analysis
                else:
                    if retry_count < self.max_retries:
                        time.sleep(2)
                        return self.process_with_ollama(prompt, retry_count + 1)
                    return None
            
            return None
            
        except subprocess.TimeoutExpired:
            if retry_count < self.max_retries:
                time.sleep(2)
                return self.process_with_ollama(prompt, retry_count + 1)
            return None
        except json.JSONDecodeError:
            if retry_count < self.max_retries:
                time.sleep(2)
                return self.process_with_ollama(prompt, retry_count + 1)
            return None
        except Exception:
            return None
    
    def process_all_candidates(self):
        """Process ALL candidates in the database"""
        # Load data
        candidates = self.load_nas_data()
        total_candidates = len(candidates)
        print(f"📊 Total candidates in database: {total_candidates}")
        
        # Find candidates that need processing
        candidates_to_process = []
        for i, candidate in enumerate(candidates):
            # Skip if already has recruiter enhancement
            if candidate.get('recruiter_enhanced_analysis'):
                continue
                
            # Check if has meaningful data
            has_name = bool(candidate.get('name'))
            has_experience = bool(candidate.get('experience') and len(candidate.get('experience', '')) > 30)
            has_education = bool(candidate.get('education') and len(candidate.get('education', '')) > 20)
            has_id = bool(candidate.get('id'))
            
            if has_id and has_name and (has_experience or has_education):
                candidates_to_process.append((i, candidate))
        
        total_to_process = len(candidates_to_process)
        print(f"🎯 Candidates to process: {total_to_process}")
        
        if not candidates_to_process:
            print("✅ All suitable candidates already processed!")
            return
        
        print(f"\n🚀 Starting full-scale processing of {total_to_process} candidates")
        print("=" * 70)
        
        batch_num = 0
        processed_in_session = 0
        
        while candidates_to_process:
            batch_num += 1
            batch = candidates_to_process[:self.batch_size]
            remaining = len(candidates_to_process)
            
            print(f"\n📦 Batch {batch_num} - Processing {len(batch)} candidates ({remaining} remaining)")
            
            # System monitoring
            if not self.monitor_system():
                print("⚠️ System resources low, pausing...")
                time.sleep(10)
                continue
            
            batch_processed = 0
            batch_failed = 0
            
            for j, (idx, candidate) in enumerate(batch):
                candidate_id = candidate.get('id')
                candidate_name = candidate.get('name', 'Unknown')
                
                print(f"  [{j+1}/{len(batch)}] {candidate_name[:20]}... ", end="")
                
                # Create prompt
                prompt = self.create_recruiter_prompt(candidate)
                
                # Process with Ollama
                analysis = self.process_with_ollama(prompt)
                
                if analysis:
                    # Update candidate in main list
                    candidates[idx]['recruiter_enhanced_analysis'] = {
                        'analysis': analysis,
                        'processing_timestamp': datetime.now().isoformat(),
                        'processor_version': 'full_scale_v1'
                    }
                    
                    # Save to individual file
                    safe_name = re.sub(r'[^\w\s-]', '', candidate_name).strip().replace(' ', '_')
                    output_file = self.enhanced_dir / f"{candidate_id}_{safe_name}_recruiter_enhanced.json"
                    
                    with open(output_file, 'w') as f:
                        json.dump({
                            'candidate_id': candidate_id,
                            'name': candidate_name,
                            'recruiter_analysis': analysis,
                            'timestamp': datetime.now().isoformat()
                        }, f, indent=2)
                    
                    batch_processed += 1
                    self.processed_count += 1
                    processed_in_session += 1
                    print("✅")
                    
                else:
                    batch_failed += 1
                    self.failed_count += 1
                    print("❌")
                
                # Brief pause every 5 candidates
                if j % 5 == 4:
                    time.sleep(1)
            
            # Save progress after each batch
            if batch_processed > 0:
                self.save_nas_data(candidates)
                print(f"  ✓ Batch {batch_num}: {batch_processed} processed, {batch_failed} failed")
                print(f"  💾 Database updated")
            
            # Remove processed candidates
            candidates_to_process = candidates_to_process[len(batch):]
            
            # Progress reporting
            progress_pct = ((total_to_process - len(candidates_to_process)) / total_to_process) * 100
            enhanced_count = sum(1 for c in candidates if c.get('recruiter_enhanced_analysis'))
            
            print(f"  📊 Progress: {progress_pct:.1f}% | Enhanced: {enhanced_count}/{total_candidates}")
            
            # Time estimation
            if processed_in_session > 0:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                avg_time = elapsed / processed_in_session
                eta_seconds = len(candidates_to_process) * avg_time
                eta_hours = eta_seconds / 3600
                print(f"  ⏱️ ETA: {eta_hours:.1f} hours")
                print(f"  📈 Rate: {processed_in_session/elapsed*60:.1f} candidates/minute")
            
            # Brief pause between batches
            if candidates_to_process:
                print(f"  ⏸️ Brief pause before next batch...")
                time.sleep(3)
        
        # Final report
        elapsed = (datetime.now() - self.start_time).total_seconds()
        final_enhanced = sum(1 for c in candidates if c.get('recruiter_enhanced_analysis'))
        
        print("\n" + "=" * 70)
        print("🎉 FULL-SCALE PROCESSING COMPLETE!")
        print(f"✅ Successfully processed: {self.processed_count}")
        print(f"❌ Failed: {self.failed_count}")
        print(f"📈 Success rate: {(self.processed_count/(self.processed_count+self.failed_count)*100 if (self.processed_count+self.failed_count) > 0 else 0):.1f}%")
        print(f"📊 Total enhanced candidates: {final_enhanced}/{total_candidates}")
        print(f"⏱️ Total time: {elapsed/3600:.1f} hours")
        if self.processed_count > 0:
            print(f"📈 Average time per candidate: {elapsed/self.processed_count:.1f} seconds")
        print(f"💾 All results saved to NAS")

def main():
    try:
        processor = FullScaleRecruiterProcessor()
        processor.process_all_candidates()
    except KeyboardInterrupt:
        print("\n\n🛑 Processing interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()