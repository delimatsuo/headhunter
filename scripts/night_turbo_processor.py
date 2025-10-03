#!/usr/bin/env python3
"""
Night Turbo Processor - Maximizes throughput from 8 PM to 7 AM
Uses concurrent processing with multiple threads for high-speed quality processing
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime, timedelta, time as datetime_time
import re
import sys
import signal
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil

class NightTurboProcessor:
    def __init__(self):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.enhanced_dir.mkdir(exist_ok=True)
        
        # Night schedule (8 PM to 7 AM)
        self.night_start = datetime_time(20, 0)  # 8:00 PM
        self.night_end = datetime_time(7, 0)     # 7:00 AM
        
        # Performance settings - MAXIMIZE for night
        self.day_threads = 2      # Conservative during day
        self.night_threads = 6    # Aggressive at night
        self.batch_size = 100
        self.max_retries = 1      # Less retries for speed
        self.ollama_timeout = 90  # Reasonable timeout
        
        # Progress tracking
        self.progress_file = Path("night_turbo_progress.json")
        self.metrics_file = Path("night_turbo_metrics.json")
        self.last_processed_index = self.load_progress()
        
        # Statistics
        self.session_start = datetime.now()
        self.total_processed = 0
        self.total_failed = 0
        self.lock = threading.Lock()
        
        # Mode tracking
        self.current_mode = "DAY" if not self.is_night_time() else "NIGHT"
        self.current_threads = self.day_threads if self.current_mode == "DAY" else self.night_threads
        
        print("🌙 NIGHT TURBO PROCESSOR")
        print("=" * 60)
        print("🕐 Night Hours: 8:00 PM - 7:00 AM (Max Performance)")
        print("☀️ Day Hours: 7:00 AM - 8:00 PM (Background Mode)")
        print(f"📊 Current Mode: {self.current_mode}")
        print(f"⚡ Active Threads: {self.current_threads}")
        print(f"🔄 Starting from index: {self.last_processed_index}")
        print()
        
        # Graceful shutdown
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        signal.signal(signal.SIGTERM, self.graceful_shutdown)
    
    def is_night_time(self) -> bool:
        """Check if current time is in night hours"""
        now = datetime.now().time()
        
        # Night crosses midnight
        if self.night_start > self.night_end:
            return now >= self.night_start or now < self.night_end
        else:
            return self.night_start <= now < self.night_end
    
    def wait_for_night(self):
        """Wait until night time if currently day"""
        if not self.is_night_time():
            now = datetime.now()
            # Calculate time until 8 PM today
            night_start_today = now.replace(hour=20, minute=0, second=0, microsecond=0)
            
            if now.time() > self.night_start:
                # Already past 8 PM today, wait for tomorrow
                night_start_today += timedelta(days=1)
            
            wait_seconds = (night_start_today - now).total_seconds()
            wait_hours = wait_seconds / 3600
            
            print(f"⏰ Waiting {wait_hours:.1f} hours until night mode (8:00 PM)...")
            print(f"💡 Running in background mode with {self.day_threads} threads until then")
    
    def adjust_thread_count(self):
        """Dynamically adjust thread count based on time"""
        is_night = self.is_night_time()
        new_mode = "NIGHT" if is_night else "DAY"
        new_threads = self.night_threads if is_night else self.day_threads
        
        if new_mode != self.current_mode:
            self.current_mode = new_mode
            self.current_threads = new_threads
            print(f"\n🔄 MODE CHANGE: Switched to {self.current_mode} mode")
            print(f"⚡ Now using {self.current_threads} threads")
            return True
        return False
    
    def load_progress(self) -> int:
        """Load last processed index"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
                return data.get('last_index', 0)
        return 0
    
    def save_progress(self, index: int):
        """Save current progress"""
        with self.lock:
            with open(self.progress_file, 'w') as f:
                json.dump({
                    'last_index': index,
                    'timestamp': datetime.now().isoformat(),
                    'total_processed': self.total_processed,
                    'total_failed': self.total_failed,
                    'mode': self.current_mode,
                    'threads': self.current_threads,
                    'session_duration': str(datetime.now() - self.session_start)
                }, f, indent=2)
    
    def save_metrics(self, batch_time: float, batch_processed: int):
        """Save performance metrics"""
        metrics = {}
        if self.metrics_file.exists():
            with open(self.metrics_file, 'r') as f:
                metrics = json.load(f)
        
        if 'sessions' not in metrics:
            metrics['sessions'] = []
        
        metrics['sessions'].append({
            'timestamp': datetime.now().isoformat(),
            'mode': self.current_mode,
            'threads': self.current_threads,
            'processing_time': batch_time,
            'candidates_processed': batch_processed,
            'rate_per_minute': (batch_processed / batch_time) * 60 if batch_time > 0 else 0
        })
        
        # Calculate separate metrics for day/night
        night_sessions = [s for s in metrics['sessions'] if s['mode'] == 'NIGHT']
        day_sessions = [s for s in metrics['sessions'] if s['mode'] == 'DAY']
        
        metrics['performance'] = {
            'night': {
                'avg_rate': sum(s['rate_per_minute'] for s in night_sessions) / len(night_sessions) if night_sessions else 0,
                'total_processed': sum(s['candidates_processed'] for s in night_sessions)
            },
            'day': {
                'avg_rate': sum(s['rate_per_minute'] for s in day_sessions) / len(day_sessions) if day_sessions else 0,
                'total_processed': sum(s['candidates_processed'] for s in day_sessions)
            }
        }
        
        with open(self.metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
    
    def create_comprehensive_prompt(self, candidate: Dict) -> str:
        """Create detailed prompt - same quality as before"""
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
            except:
                pass
        
        return None
    
    def process_single_candidate(self, candidate: Dict, idx: int) -> tuple:
        """Process a single candidate - thread worker function"""
        candidate_id = candidate.get('id', f'unknown_{idx}')
        candidate_name = candidate.get('name', 'Unknown')
        
        # Check if already processed
        safe_name = re.sub(r'[^\w\s-]', '', candidate_name).strip().replace(' ', '_')[:50]
        output_file = self.enhanced_dir / f"{candidate_id}_{safe_name}_enhanced.json"
        
        if output_file.exists():
            return (True, False, output_file.stat().st_size)
        
        # Skip if no data
        if not candidate.get('education') and not candidate.get('experience'):
            return (False, True, 0)
        
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
                        'processor': 'night_turbo_processor',
                        'mode': self.current_mode,
                        'threads': self.current_threads
                    }
                }
                
                with open(output_file, 'w') as f:
                    json.dump(output_data, f, indent=2)
                
                return (True, False, output_file.stat().st_size)
                
            except Exception:
                return (False, True, 0)
        
        return (False, True, 0)
    
    def process_batch_threaded(self, candidates: List[Dict], start_idx: int):
        """Process batch with threading"""
        batch_start = time.time()
        batch_processed = 0
        batch_failed = 0
        
        print(f"\n📋 Processing batch {start_idx}-{start_idx + len(candidates)}")
        print(f"⚡ Mode: {self.current_mode} | Threads: {self.current_threads}")
        print(f"⏰ Time: {datetime.now().strftime('%I:%M %p')}")
        
        # Use ThreadPoolExecutor with current thread count
        with ThreadPoolExecutor(max_workers=self.current_threads) as executor:
            # Submit all candidates to thread pool
            futures = {}
            for i, candidate in enumerate(candidates):
                future = executor.submit(self.process_single_candidate, candidate, start_idx + i)
                futures[future] = (i, candidate.get('name', 'Unknown')[:30])
            
            # Process results as they complete
            completed = 0
            for future in as_completed(futures):
                completed += 1
                idx, name = futures[future]
                
                try:
                    success, failed, file_size = future.result(timeout=120)
                    
                    if success and not failed:
                        batch_processed += 1
                        with self.lock:
                            self.total_processed += 1
                        
                        if file_size > 0:
                            print(f"  [{completed}/{len(candidates)}] ✅ {name} ({file_size} bytes)")
                        else:
                            print(f"  [{completed}/{len(candidates)}] ⏭️ {name} (exists)")
                    else:
                        batch_failed += 1
                        with self.lock:
                            self.total_failed += 1
                        print(f"  [{completed}/{len(candidates)}] ❌ {name}")
                    
                except Exception as e:
                    batch_failed += 1
                    with self.lock:
                        self.total_failed += 1
                    print(f"  [{completed}/{len(candidates)}] ❌ {name}: {e}")
                
                # Progress update
                if completed % 20 == 0:
                    elapsed = time.time() - batch_start
                    rate = completed / (elapsed / 60) if elapsed > 0 else 0
                    print(f"    Progress: {completed}/{len(candidates)} | Rate: {rate:.1f}/min | CPU: {psutil.cpu_percent()}%")
        
        batch_time = time.time() - batch_start
        
        print("\n✅ Batch complete!")
        print(f"  Time: {batch_time/60:.1f} minutes")
        print(f"  Processed: {batch_processed} | Failed: {batch_failed}")
        print(f"  Rate: {batch_processed/(batch_time/60):.1f} candidates/minute")
        
        # Save metrics
        self.save_metrics(batch_time, batch_processed)
        
        return batch_processed, batch_failed
    
    def run_adaptive(self):
        """Run with adaptive threading based on time of day"""
        print("📊 Loading candidate database...")
        with open(self.nas_file, 'r') as f:
            all_candidates = json.load(f)
        
        total_candidates = len(all_candidates)
        print(f"📊 Total candidates: {total_candidates}")
        print(f"📊 Starting from: {self.last_processed_index}")
        print(f"📊 Remaining: {total_candidates - self.last_processed_index}")
        
        current_index = self.last_processed_index
        
        while current_index < total_candidates:
            # Check and adjust mode
            self.adjust_thread_count()
            
            # Get next batch
            batch_end = min(current_index + self.batch_size, total_candidates)
            batch = all_candidates[current_index:batch_end]
            
            # Process batch with current thread settings
            processed, failed = self.process_batch_threaded(batch, current_index)
            
            # Update progress
            current_index = batch_end
            self.save_progress(current_index)
            
            # Statistics
            print("\n📊 OVERALL PROGRESS:")
            print(f"  Completed: {current_index}/{total_candidates} ({100*current_index/total_candidates:.1f}%)")
            print(f"  Session Total: {self.total_processed} processed, {self.total_failed} failed")
            
            # Load metrics for estimation
            if self.metrics_file.exists():
                with open(self.metrics_file, 'r') as f:
                    metrics = json.load(f)
                    if 'performance' in metrics:
                        night_rate = metrics['performance']['night']['avg_rate']
                        day_rate = metrics['performance']['day']['avg_rate']
                        
                        if self.current_mode == "NIGHT" and night_rate > 0:
                            remaining = total_candidates - current_index
                            eta_hours = remaining / (night_rate * 60)
                            print(f"  Night Rate: {night_rate:.1f}/min")
                            print(f"  ETA at night speed: {eta_hours:.1f} hours")
                        elif day_rate > 0:
                            remaining = total_candidates - current_index
                            eta_hours = remaining / (day_rate * 60)
                            print(f"  Day Rate: {day_rate:.1f}/min")
                            print(f"  ETA at day speed: {eta_hours:.1f} hours")
            
            # Short pause between batches
            if current_index < total_candidates:
                print("\n⏸️ Pausing 3 seconds before next batch...")
                time.sleep(3)
        
        print("\n🎉 ALL PROCESSING COMPLETE!")
        print(f"Total time: {datetime.now() - self.session_start}")
        print(f"Total processed: {self.total_processed}")
        print(f"Total failed: {self.total_failed}")
    
    def graceful_shutdown(self, signum, frame):
        """Handle shutdown gracefully"""
        print("\n🛑 Graceful shutdown...")
        print(f"📊 Session stats: {self.total_processed} processed, {self.total_failed} failed")
        if hasattr(self, 'current_index'):
            self.save_progress(self.current_index)
        sys.exit(0)

if __name__ == "__main__":
    processor = NightTurboProcessor()
    processor.run_adaptive()