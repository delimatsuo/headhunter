#!/usr/bin/env python3
"""
Turbo Parallel Processor - Maximum speed processing using all CPU cores
Runs from 6:50 PM to 7:00 AM with automatic scheduling
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import re
import signal
import sys
import os
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError
from multiprocessing import cpu_count, Manager
import threading
import psutil

class TurboParallelProcessor:
    def __init__(self):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.enhanced_dir.mkdir(exist_ok=True)
        
        # Performance settings - MAXIMIZED
        self.num_workers = cpu_count() - 1  # Use all cores except one
        self.batch_size = 50  # Smaller batches for better parallelization
        self.max_retries = 1  # Reduce retries to save time
        self.ollama_timeout = 60  # Shorter timeout
        
        # Timing settings
        self.start_time = datetime.now().replace(hour=18, minute=50, second=0)  # 6:50 PM
        self.end_time = (datetime.now() + timedelta(days=1)).replace(hour=7, minute=0, second=0)  # 7:00 AM tomorrow
        
        self.processed_count = 0
        self.failed_count = 0
        self.start_timestamp = datetime.now()
        
        # Progress tracking
        self.progress_file = Path("turbo_progress.json")
        self.last_processed_index = self.load_progress()
        
        # Thread-safe counters
        self.manager = Manager()
        self.shared_processed = self.manager.Value('i', 0)
        self.shared_failed = self.manager.Value('i', 0)
        
        print(f"🚀 TURBO PARALLEL PROCESSOR INITIALIZED")
        print(f"⚡ CPU Cores: {cpu_count()} | Workers: {self.num_workers}")
        print(f"🕐 Schedule: {self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p tomorrow')}")
        print(f"📦 Batch Size: {self.batch_size} candidates per worker")
        print(f"🔄 Starting from index: {self.last_processed_index}")
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        signal.signal(signal.SIGTERM, self.graceful_shutdown)
        
    def load_progress(self) -> int:
        """Load the last processed index from progress file"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
                return data.get('last_index', 0)
        return 0
    
    def save_progress(self, index: int):
        """Save current progress"""
        with open(self.progress_file, 'w') as f:
            json.dump({
                'last_index': index,
                'timestamp': datetime.now().isoformat(),
                'processed': self.shared_processed.value,
                'failed': self.shared_failed.value,
                'workers': self.num_workers,
                'performance': {
                    'candidates_per_minute': self.get_processing_rate(),
                    'cpu_usage': psutil.cpu_percent(),
                    'memory_usage': psutil.virtual_memory().percent
                }
            }, f)
    
    def get_processing_rate(self) -> float:
        """Calculate current processing rate"""
        elapsed = (datetime.now() - self.start_timestamp).total_seconds() / 60
        if elapsed > 0:
            return self.shared_processed.value / elapsed
        return 0
    
    def wait_for_start_time(self):
        """Wait until scheduled start time"""
        now = datetime.now()
        if now < self.start_time:
            wait_seconds = (self.start_time - now).total_seconds()
            print(f"⏰ Waiting {wait_seconds:.0f} seconds until {self.start_time.strftime('%I:%M %p')}...")
            time.sleep(wait_seconds)
    
    def should_continue(self) -> bool:
        """Check if we should continue processing"""
        now = datetime.now()
        return now < self.end_time
    
    def process_with_ollama(self, prompt: str, timeout: int = 60) -> Optional[Dict]:
        """Process a single prompt with Ollama"""
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
                timeout=timeout
            )
            
            if result.returncode == 0 and result.stdout:
                try:
                    # Extract JSON from response
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
    
    def process_candidate_batch(self, candidates: List[Dict], start_idx: int) -> List[Dict]:
        """Process a batch of candidates"""
        results = []
        
        for i, candidate in enumerate(candidates):
            if not self.should_continue():
                break
                
            # Extract candidate info
            candidate_id = candidate.get('id')
            candidate_name = candidate.get('name', 'Unknown')
            
            # Skip if no essential data
            if not candidate_id or not candidate_name:
                continue
            
            # Check if already processed
            safe_name = re.sub(r'[^\w\s-]', '', candidate_name).strip().replace(' ', '_')
            output_file = self.enhanced_dir / f"{candidate_id}_{safe_name}_recruiter_enhanced.json"
            
            if output_file.exists():
                self.shared_processed.value += 1
                continue
            
            # Create comprehensive prompt
            prompt = self.create_fast_prompt(candidate)
            
            # Process with Ollama
            analysis = self.process_with_ollama(prompt, self.ollama_timeout)
            
            if analysis:
                try:
                    # Save result
                    with open(output_file, 'w') as f:
                        json.dump({
                            'candidate_id': candidate_id,
                            'name': candidate_name,
                            'recruiter_analysis': analysis,
                            'timestamp': datetime.now().isoformat(),
                            'processor': 'turbo_parallel'
                        }, f, indent=2)
                    
                    self.shared_processed.value += 1
                    results.append({
                        'index': start_idx + i,
                        'candidate_id': candidate_id,
                        'status': 'success'
                    })
                    
                except Exception:
                    self.shared_failed.value += 1
            else:
                self.shared_failed.value += 1
                
        return results
    
    def create_fast_prompt(self, candidate: Dict) -> str:
        """Create a streamlined prompt for faster processing"""
        name = candidate.get('name', 'Unknown')
        education = candidate.get('education', [])
        experience = candidate.get('experience', [])
        skills = candidate.get('skills', [])
        
        # Simplified prompt for speed
        prompt = f"""Analyze {name} and return JSON with these exact keys:
personal_details: {{name, location}}
education_analysis: {{degrees, quality_score}}
experience_analysis: {{years, companies, level}}
technical_assessment: {{skills, expertise_level}}
market_insights: {{salary_range, demand}}
cultural_assessment: {{work_style, red_flags}}
recruiter_recommendations: {{placement_difficulty, strategy}}
searchability: {{keywords[]}}
executive_summary: {{pitch, rating}}

Education: {json.dumps(education[:3])}
Experience: {json.dumps(experience[:5])}
Skills: {json.dumps(skills[:20])}

Return ONLY valid JSON, no explanations."""
        
        return prompt
    
    def run_parallel_processing(self):
        """Main parallel processing loop"""
        print(f"\n⚡ STARTING TURBO PARALLEL PROCESSING")
        print(f"=" * 60)
        
        # Load candidates
        print("📊 Loading database...")
        with open(self.nas_file, 'r') as f:
            all_candidates = json.load(f)
        
        total_candidates = len(all_candidates)
        print(f"📊 Total candidates: {total_candidates}")
        
        # Start from last processed index
        current_index = self.last_processed_index
        
        # Process in parallel batches
        with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
            while current_index < total_candidates and self.should_continue():
                # Prepare batches for parallel processing
                futures = []
                batch_end = min(current_index + (self.batch_size * self.num_workers), total_candidates)
                
                print(f"\n📋 Processing candidates {current_index} to {batch_end}")
                print(f"⚡ Using {self.num_workers} parallel workers")
                
                # Submit batches to workers
                for worker_id in range(self.num_workers):
                    batch_start = current_index + (worker_id * self.batch_size)
                    batch_end_worker = min(batch_start + self.batch_size, total_candidates)
                    
                    if batch_start >= total_candidates:
                        break
                    
                    batch = all_candidates[batch_start:batch_end_worker]
                    if batch:
                        future = executor.submit(self.process_candidate_batch, batch, batch_start)
                        futures.append((future, batch_start, batch_end_worker))
                
                # Wait for completion
                for future, start, end in futures:
                    try:
                        results = future.result(timeout=300)  # 5 minute timeout per batch
                        print(f"  ✅ Worker completed batch {start}-{end}")
                    except TimeoutError:
                        print(f"  ⏱️ Worker timeout for batch {start}-{end}")
                    except Exception as e:
                        print(f"  ❌ Worker error for batch {start}-{end}: {e}")
                
                # Update progress
                current_index = batch_end
                self.save_progress(current_index)
                
                # Display statistics
                rate = self.get_processing_rate()
                print(f"\n📊 Progress: {self.shared_processed.value}/{total_candidates}")
                print(f"⚡ Rate: {rate:.1f} candidates/minute")
                print(f"🧠 CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}%")
                
                # Estimate completion
                if rate > 0:
                    remaining = total_candidates - current_index
                    eta_minutes = remaining / rate
                    eta_time = datetime.now() + timedelta(minutes=eta_minutes)
                    print(f"⏱️ ETA: {eta_time.strftime('%I:%M %p')} ({eta_minutes/60:.1f} hours)")
        
        print(f"\n✅ Processing session completed!")
        print(f"📊 Final stats: Processed {self.shared_processed.value}, Failed {self.shared_failed.value}")
    
    def graceful_shutdown(self, signum, frame):
        """Handle shutdown gracefully"""
        print("\n🛑 Shutdown initiated...")
        print(f"📊 Processed: {self.shared_processed.value}, Failed: {self.shared_failed.value}")
        self.save_progress(self.last_processed_index)
        print("💾 Progress saved.")
        sys.exit(0)
    
    def run(self):
        """Main entry point with scheduling"""
        # Wait for start time
        self.wait_for_start_time()
        
        print(f"\n🚀 TURBO PROCESSING STARTED at {datetime.now().strftime('%I:%M %p')}")
        print(f"🏁 Will run until {self.end_time.strftime('%I:%M %p tomorrow')}")
        
        # Run parallel processing
        self.run_parallel_processing()
        
        print(f"\n🏁 Session ended at {datetime.now().strftime('%I:%M %p')}")
        print(f"📊 Total processed: {self.shared_processed.value}")
        print(f"📊 Total failed: {self.shared_failed.value}")

if __name__ == "__main__":
    processor = TurboParallelProcessor()
    processor.run()