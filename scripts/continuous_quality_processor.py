#!/usr/bin/env python3
"""
Continuous Quality Processor - Processes candidates in batches of 100 with high quality
Runs continuously in the background until all candidates are processed
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import re
import sys
import signal
import psutil

class ContinuousQualityProcessor:
    def __init__(self):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.enhanced_dir.mkdir(exist_ok=True)
        
        # Processing settings
        self.batch_size = 100
        self.max_retries = 2
        self.ollama_timeout = 120
        
        # Progress tracking
        self.progress_file = Path("continuous_progress.json")
        self.metrics_file = Path("continuous_metrics.json")
        self.last_processed_index = self.load_progress()
        
        # Statistics
        self.session_start = datetime.now()
        self.total_processed = 0
        self.total_failed = 0
        self.batch_times = []
        
        print(f"🔄 CONTINUOUS QUALITY PROCESSOR")
        print(f"=" * 60)
        print(f"📦 Batch Size: {self.batch_size} candidates")
        print(f"🔄 Starting from index: {self.last_processed_index}")
        print(f"📁 Output: {self.enhanced_dir}")
        print(f"⏰ Started: {self.session_start.strftime('%I:%M %p')}")
        print()
        
        # Graceful shutdown
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        signal.signal(signal.SIGTERM, self.graceful_shutdown)
        
    def load_progress(self) -> int:
        """Load last processed index"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
                return data.get('last_index', 0)
        return 0
    
    def save_progress(self, index: int, batch_num: int):
        """Save current progress"""
        with open(self.progress_file, 'w') as f:
            json.dump({
                'last_index': index,
                'batch_number': batch_num,
                'timestamp': datetime.now().isoformat(),
                'total_processed': self.total_processed,
                'total_failed': self.total_failed,
                'session_duration': str(datetime.now() - self.session_start)
            }, f, indent=2)
    
    def save_metrics(self, batch_num: int, batch_time: float, batch_processed: int):
        """Save performance metrics"""
        metrics = {}
        if self.metrics_file.exists():
            with open(self.metrics_file, 'r') as f:
                metrics = json.load(f)
        
        if 'batches' not in metrics:
            metrics['batches'] = []
        
        metrics['batches'].append({
            'batch_number': batch_num,
            'timestamp': datetime.now().isoformat(),
            'processing_time': batch_time,
            'candidates_processed': batch_processed,
            'rate_per_minute': (batch_processed / batch_time) * 60 if batch_time > 0 else 0
        })
        
        # Overall statistics
        total_time = sum(b['processing_time'] for b in metrics['batches'])
        total_candidates = sum(b['candidates_processed'] for b in metrics['batches'])
        
        metrics['overall'] = {
            'total_batches': len(metrics['batches']),
            'total_candidates': total_candidates,
            'total_time_seconds': total_time,
            'avg_rate_per_minute': (total_candidates / total_time) * 60 if total_time > 0 else 0,
            'last_updated': datetime.now().isoformat()
        }
        
        with open(self.metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
    
    def create_comprehensive_prompt(self, candidate: Dict) -> str:
        """Create detailed prompt for comprehensive analysis"""
        name = candidate.get('name', 'Unknown')
        education = candidate.get('education', [])
        experience = candidate.get('experience', [])
        skills = candidate.get('skills', [])
        
        # Convert to text
        if isinstance(education, list):
            education_text = '\n'.join([str(e) for e in education])
        else:
            education_text = str(education)
            
        if isinstance(experience, list):
            experience_text = '\n'.join([str(e) for e in experience])
        else:
            experience_text = str(experience)
            
        if isinstance(skills, list):
            skills_text = ', '.join([str(s) for s in skills])
        else:
            skills_text = str(skills)
        
        prompt = f"""You are an expert recruiter analyzing a candidate profile. Provide a comprehensive JSON analysis.

CANDIDATE: {name}

EDUCATION:
{education_text}

EXPERIENCE:
{experience_text}

SKILLS:
{skills_text}

Provide a detailed JSON response with EXACTLY this structure (fill ALL fields with meaningful analysis):

{{
  "personal_details": {{
    "name": "{name}",
    "location": "Infer from companies/universities or put 'Unknown'",
    "seniority_level": "Entry/Mid/Senior/Executive",
    "years_of_experience": "Estimate total years"
  }},
  "education_analysis": {{
    "degrees": ["List all degrees with institutions"],
    "quality_score": "1-10 based on institution prestige",
    "relevance": "How relevant to tech roles",
    "highest_degree": "BS/MS/PhD/MBA etc"
  }},
  "experience_analysis": {{
    "total_years": "Number",
    "companies": ["List all companies"],
    "current_role": "Most recent position",
    "career_progression": "Junior to Senior trajectory description",
    "industry_focus": "Main industry experience"
  }},
  "technical_assessment": {{
    "primary_skills": ["Top 5 technical skills"],
    "secondary_skills": ["Other technical skills"],
    "expertise_level": "Beginner/Intermediate/Advanced/Expert",
    "technology_stack": "Main tech stack used",
    "certifications": ["Any mentioned certifications"]
  }},
  "market_insights": {{
    "estimated_salary_range": "$XXX,000 - $XXX,000",
    "market_demand": "High/Medium/Low for their profile",
    "competitive_advantage": "What makes them stand out",
    "placement_difficulty": "Easy/Medium/Hard to place"
  }},
  "cultural_assessment": {{
    "work_style": "Inferred work preferences",
    "company_fit": "Startup/Corporate/Both",
    "red_flags": ["Any concerns from the profile"],
    "strengths": ["Key professional strengths"]
  }},
  "recruiter_recommendations": {{
    "ideal_roles": ["3-5 suitable job titles"],
    "target_companies": ["Types of companies to target"],
    "positioning_strategy": "How to position this candidate",
    "interview_prep": "Key areas to prepare"
  }},
  "searchability": {{
    "keywords": ["10-15 searchable keywords"],
    "job_titles": ["Alternative job title matches"],
    "skills_taxonomy": ["Categorized skills for ATS"]
  }},
  "executive_summary": {{
    "one_line_pitch": "Single sentence candidate summary",
    "key_achievements": ["Top 3 achievements/highlights"],
    "overall_rating": "A+/A/B+/B/C",
    "recommendation": "Highly Recommended/Recommended/Consider/Pass"
  }}
}}

Return ONLY the JSON, no additional text."""
        
        return prompt
    
    def process_with_ollama(self, prompt: str) -> Optional[Dict]:
        """Process with Ollama"""
        for attempt in range(self.max_retries):
            try:
                cmd = [
                    'ollama', 'run', 'llama3.1:8b',
                    '--format', 'json',
                    prompt
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.ollama_timeout
                )
                
                if result.returncode == 0 and result.stdout:
                    response_text = result.stdout.strip()
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        try:
                            parsed = json.loads(json_match.group())
                            if len(json.dumps(parsed)) > 500:
                                return parsed
                        except json.JSONDecodeError:
                            pass
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                pass
        
        return None
    
    def process_batch(self, candidates: List[Dict], start_idx: int, batch_num: int):
        """Process a single batch"""
        batch_start_time = time.time()
        batch_processed = 0
        batch_failed = 0
        
        print(f"\n📋 BATCH {batch_num}: Processing candidates {start_idx} to {start_idx + len(candidates)}")
        print(f"⏰ Batch started: {datetime.now().strftime('%I:%M %p')}")
        
        for i, candidate in enumerate(candidates):
            current_idx = start_idx + i
            candidate_id = candidate.get('id', f'unknown_{current_idx}')
            candidate_name = candidate.get('name', 'Unknown')
            
            # Check if already processed
            safe_name = re.sub(r'[^\w\s-]', '', candidate_name).strip().replace(' ', '_')[:50]
            output_file = self.enhanced_dir / f"{candidate_id}_{safe_name}_enhanced.json"
            
            if output_file.exists():
                print(f"  [{i+1}/{len(candidates)}] Skipped (exists): {candidate_name[:30]}")
                batch_processed += 1
                continue
            
            # Skip if no data
            if not candidate.get('education') and not candidate.get('experience'):
                continue
            
            # Process
            prompt = self.create_comprehensive_prompt(candidate)
            analysis = self.process_with_ollama(prompt)
            
            if analysis:
                try:
                    output_data = {
                        'candidate_id': candidate_id,
                        'name': candidate_name,
                        'original_data': {
                            'education': candidate.get('education', ''),
                            'experience': candidate.get('experience', ''),
                            'skills': candidate.get('skills', '')
                        },
                        'recruiter_analysis': analysis,
                        'processing_metadata': {
                            'timestamp': datetime.now().isoformat(),
                            'processor': 'continuous_quality_processor',
                            'batch_number': batch_num
                        }
                    }
                    
                    with open(output_file, 'w') as f:
                        json.dump(output_data, f, indent=2)
                    
                    batch_processed += 1
                    self.total_processed += 1
                    print(f"  [{i+1}/{len(candidates)}] ✅ {candidate_name[:30]} ({output_file.stat().st_size} bytes)")
                    
                except Exception as e:
                    batch_failed += 1
                    self.total_failed += 1
                    print(f"  [{i+1}/{len(candidates)}] ❌ Save failed: {e}")
            else:
                batch_failed += 1
                self.total_failed += 1
                print(f"  [{i+1}/{len(candidates)}] ❌ LLM failed: {candidate_name[:30]}")
            
            # Progress update every 20
            if (i + 1) % 20 == 0:
                elapsed = time.time() - batch_start_time
                rate = (i + 1) / (elapsed / 60) if elapsed > 0 else 0
                print(f"    Progress: {i+1}/{len(candidates)} | Rate: {rate:.1f}/min")
        
        batch_time = time.time() - batch_start_time
        self.batch_times.append(batch_time)
        
        print(f"\n✅ Batch {batch_num} complete!")
        print(f"  Time: {batch_time/60:.1f} minutes")
        print(f"  Processed: {batch_processed} | Failed: {batch_failed}")
        print(f"  Rate: {batch_processed/(batch_time/60):.1f} candidates/minute")
        
        # Save metrics
        self.save_metrics(batch_num, batch_time, batch_processed)
        
        return batch_processed, batch_failed
    
    def run_continuous(self):
        """Run continuous processing"""
        print("📊 Loading candidate database...")
        with open(self.nas_file, 'r') as f:
            all_candidates = json.load(f)
        
        total_candidates = len(all_candidates)
        print(f"📊 Total candidates: {total_candidates}")
        print(f"📊 Already processed: {self.last_processed_index}")
        print(f"📊 Remaining: {total_candidates - self.last_processed_index}")
        
        current_index = self.last_processed_index
        batch_num = (current_index // self.batch_size) + 1
        
        while current_index < total_candidates:
            # Get next batch
            batch_end = min(current_index + self.batch_size, total_candidates)
            batch = all_candidates[current_index:batch_end]
            
            # Process batch
            processed, failed = self.process_batch(batch, current_index, batch_num)
            
            # Update progress
            current_index = batch_end
            self.save_progress(current_index, batch_num)
            
            # Overall statistics
            print(f"\n📊 OVERALL PROGRESS:")
            print(f"  Total Processed: {self.total_processed}/{total_candidates}")
            print(f"  Completion: {100*current_index/total_candidates:.1f}%")
            
            if self.batch_times:
                avg_batch_time = sum(self.batch_times) / len(self.batch_times)
                remaining_batches = (total_candidates - current_index) / self.batch_size
                eta_hours = (remaining_batches * avg_batch_time) / 3600
                print(f"  Avg Batch Time: {avg_batch_time/60:.1f} minutes")
                print(f"  ETA for completion: {eta_hours:.1f} hours")
            
            print(f"  System: CPU {psutil.cpu_percent()}% | RAM {psutil.virtual_memory().percent}%")
            
            batch_num += 1
            
            # Short pause between batches
            if current_index < total_candidates:
                print(f"\n⏸️ Pausing 5 seconds before next batch...")
                time.sleep(5)
        
        print(f"\n🎉 ALL PROCESSING COMPLETE!")
        print(f"Total time: {datetime.now() - self.session_start}")
        print(f"Total processed: {self.total_processed}")
        print(f"Total failed: {self.total_failed}")
    
    def graceful_shutdown(self, signum, frame):
        """Handle shutdown gracefully"""
        print(f"\n🛑 Graceful shutdown...")
        print(f"📊 Session processed: {self.total_processed}")
        print(f"📊 Session failed: {self.total_failed}")
        if hasattr(self, 'current_index'):
            self.save_progress(self.current_index, 0)
        sys.exit(0)

if __name__ == "__main__":
    processor = ContinuousQualityProcessor()
    processor.run_continuous()