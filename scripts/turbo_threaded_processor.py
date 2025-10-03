#!/usr/bin/env python3
"""
Turbo Threaded Processor - High-speed processing with threading (avoids multiprocessing pickle issues)
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta
import re
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil

class TurboThreadedProcessor:
    def __init__(self):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.enhanced_dir.mkdir(exist_ok=True)
        
        # Performance settings - HIGH
        self.num_threads = 8  # Use 8 threads for Ollama processing
        self.batch_size = 20  # Smaller batches
        self.max_retries = 1
        self.ollama_timeout = 45
        
        # Timing settings
        self.start_time = datetime.now().replace(hour=18, minute=50, second=0)
        self.end_time = (datetime.now() + timedelta(days=1)).replace(hour=7, minute=0, second=0)
        
        self.processed_count = 0
        self.failed_count = 0
        self.start_timestamp = datetime.now()
        self.lock = threading.Lock()
        
        # Progress tracking
        self.progress_file = Path("turbo_threaded_progress.json")
        self.last_processed_index = self.load_progress()
        
        print("🚀 TURBO THREADED PROCESSOR INITIALIZED")
        print(f"⚡ Threads: {self.num_threads}")
        print(f"🕐 Schedule: {self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p tomorrow')}")
        print(f"📦 Batch Size: {self.batch_size}")
        print(f"🔄 Starting from index: {self.last_processed_index}")
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        signal.signal(signal.SIGTERM, self.graceful_shutdown)
        
    def load_progress(self) -> int:
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
                return data.get('last_index', 0)
        return 0
    
    def save_progress(self, index: int):
        with self.lock:
            with open(self.progress_file, 'w') as f:
                json.dump({
                    'last_index': index,
                    'timestamp': datetime.now().isoformat(),
                    'processed': self.processed_count,
                    'failed': self.failed_count,
                    'threads': self.num_threads,
                    'performance': {
                        'candidates_per_minute': self.get_processing_rate(),
                        'cpu_usage': psutil.cpu_percent(),
                        'memory_usage': psutil.virtual_memory().percent
                    }
                }, f)
    
    def get_processing_rate(self) -> float:
        elapsed = (datetime.now() - self.start_timestamp).total_seconds() / 60
        if elapsed > 0:
            return self.processed_count / elapsed
        return 0
    
    def should_continue(self) -> bool:
        now = datetime.now()
        return now < self.end_time
    
    def wait_for_start_time(self):
        now = datetime.now()
        if now < self.start_time:
            wait_seconds = (self.start_time - now).total_seconds()
            if wait_seconds > 0:
                print(f"⏰ Waiting {wait_seconds:.0f} seconds until {self.start_time.strftime('%I:%M %p')}...")
                time.sleep(wait_seconds)
    
    def process_with_ollama(self, prompt: str) -> Optional[Dict]:
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
                try:
                    response_text = result.stdout.strip()
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            return None
            
        except subprocess.TimeoutExpired:
            return None
        except Exception:
            return None
    
    def process_single_candidate(self, candidate: Dict, index: int) -> bool:
        if not self.should_continue():
            return False
            
        candidate_id = candidate.get('id')
        candidate_name = candidate.get('name', 'Unknown')
        
        if not candidate_id or not candidate_name:
            return False
        
        # Check if already processed
        safe_name = re.sub(r'[^\w\s-]', '', candidate_name).strip().replace(' ', '_')
        output_file = self.enhanced_dir / f"{candidate_id}_{safe_name}_recruiter_enhanced.json"
        
        if output_file.exists():
            with self.lock:
                self.processed_count += 1
            return True
        
        # Create fast prompt
        prompt = self.create_fast_prompt(candidate)
        
        # Process with Ollama
        analysis = self.process_with_ollama(prompt)
        
        if analysis:
            try:
                with open(output_file, 'w') as f:
                    json.dump({
                        'candidate_id': candidate_id,
                        'name': candidate_name,
                        'recruiter_analysis': analysis,
                        'timestamp': datetime.now().isoformat(),
                        'processor': 'turbo_threaded'
                    }, f, indent=2)
                
                with self.lock:
                    self.processed_count += 1
                    
                print(f"  ✅ [{index}] {candidate_name[:30]}")
                return True
                
            except Exception as e:
                print(f"  💾 Save error [{index}] {candidate_name[:30]}: {e}")
                with self.lock:
                    self.failed_count += 1
                return False
        else:
            print(f"  ❌ LLM failed [{index}] {candidate_name[:30]}")
            with self.lock:
                self.failed_count += 1
            return False
    
    def create_fast_prompt(self, candidate: Dict) -> str:
        name = candidate.get('name', 'Unknown')
        education = candidate.get('education', [])
        experience = candidate.get('experience', [])
        skills = candidate.get('skills', [])
        
        prompt = f"""Analyze {name} quickly. Return JSON:
{{
  "personal_details": {{"name": "{name}", "location": "inferred"}},
  "education_analysis": {{"degrees": [], "quality": "score"}},
  "experience_analysis": {{"years": 0, "companies": [], "level": ""}},
  "technical_assessment": {{"skills": [], "expertise": ""}},
  "market_insights": {{"salary": "", "demand": ""}},
  "cultural_assessment": {{"style": "", "flags": []}},
  "recruiter_recommendations": {{"difficulty": "", "strategy": ""}},
  "searchability": ["keywords"],
  "executive_summary": {{"pitch": "", "rating": ""}}
}}

Data:
Ed: {json.dumps(education[:2])}
Exp: {json.dumps(experience[:3])}
Skills: {json.dumps(skills[:15])}

ONLY JSON response."""
        
        return prompt
    
    def run_threaded_processing(self):
        print("\n⚡ STARTING TURBO THREADED PROCESSING")
        print("=" * 60)
        
        # Load candidates
        print("📊 Loading database...")
        with open(self.nas_file, 'r') as f:
            all_candidates = json.load(f)
        
        total_candidates = len(all_candidates)
        print(f"📊 Total candidates: {total_candidates}")
        
        # Start from last processed index
        current_index = self.last_processed_index
        
        # Thread pool processing
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            batch_count = 0
            
            while current_index < total_candidates and self.should_continue():
                batch_count += 1
                batch_end = min(current_index + self.batch_size, total_candidates)
                batch = all_candidates[current_index:batch_end]
                
                print(f"\n📋 Batch {batch_count}: Processing {current_index} to {batch_end}")
                
                # Submit batch to thread pool
                futures = []
                for i, candidate in enumerate(batch):
                    future = executor.submit(self.process_single_candidate, candidate, current_index + i)
                    futures.append(future)
                
                # Wait for batch completion
                completed = 0
                for future in as_completed(futures):
                    try:
                        success = future.result(timeout=120)
                        if success:
                            completed += 1
                    except Exception as e:
                        print(f"  ⚠️ Thread error: {e}")
                
                # Update progress
                current_index = batch_end
                self.save_progress(current_index)
                
                # Stats
                rate = self.get_processing_rate()
                print(f"  📊 Batch completed: {completed}/{len(batch)} successful")
                print(f"  ⚡ Overall: {self.processed_count}/{total_candidates} @ {rate:.1f}/min")
                print(f"  🧠 CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}%")
                
                # ETA
                if rate > 0:
                    remaining = total_candidates - current_index
                    eta_minutes = remaining / rate
                    eta_time = datetime.now() + timedelta(minutes=eta_minutes)
                    print(f"  ⏱️ ETA: {eta_time.strftime('%I:%M %p')} ({eta_minutes/60:.1f}h remaining)")
        
        print("\n✅ Processing completed!")
        print(f"📊 Final: Processed {self.processed_count}, Failed {self.failed_count}")
    
    def graceful_shutdown(self, signum, frame):
        print("\n🛑 Shutdown initiated...")
        print(f"📊 Final stats: Processed {self.processed_count}, Failed {self.failed_count}")
        self.save_progress(self.last_processed_index)
        print("💾 Progress saved.")
        sys.exit(0)
    
    def run(self):
        # Wait for start time
        self.wait_for_start_time()
        
        print(f"\n🚀 TURBO PROCESSING STARTED at {datetime.now().strftime('%I:%M %p')}")
        print(f"🏁 Will run until {self.end_time.strftime('%I:%M %p tomorrow')}")
        
        # Run threaded processing
        self.run_threaded_processing()
        
        print(f"\n🏁 Session ended at {datetime.now().strftime('%I:%M %p')}")

if __name__ == "__main__":
    processor = TurboThreadedProcessor()
    processor.run()