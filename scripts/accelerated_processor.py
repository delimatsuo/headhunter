#!/usr/bin/env python3
"""
Accelerated Processor - Fast sequential processing with optimizations
Simplified but high-performance version
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import re
import signal
import sys
import psutil

class AcceleratedProcessor:
    def __init__(self):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.enhanced_dir.mkdir(exist_ok=True)
        
        # Optimized settings
        self.save_every = 50  # Save progress every 50 candidates
        self.timeout = 30  # Reduced timeout for faster processing
        
        # Timing
        self.end_time = (datetime.now() + timedelta(days=1)).replace(hour=7, minute=0, second=0)
        
        self.processed_count = 0
        self.failed_count = 0
        self.start_time = datetime.now()
        
        # Progress tracking
        self.progress_file = Path("accelerated_progress.json")
        self.last_processed_index = self.load_progress()
        
        print(f"🚀 ACCELERATED PROCESSOR STARTED")
        print(f"🏁 Will run until {self.end_time.strftime('%I:%M %p tomorrow')}")
        print(f"⚡ Starting from index: {self.last_processed_index}")
        print(f"⏰ Timeout: {self.timeout}s per candidate")
        
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        signal.signal(signal.SIGTERM, self.graceful_shutdown)
        
    def load_progress(self) -> int:
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
                return data.get('last_index', 0)
        return 0
    
    def save_progress(self, index: int):
        rate = self.get_rate()
        with open(self.progress_file, 'w') as f:
            json.dump({
                'last_index': index,
                'timestamp': datetime.now().isoformat(),
                'processed': self.processed_count,
                'failed': self.failed_count,
                'rate_per_minute': rate,
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent
            }, f)
    
    def get_rate(self) -> float:
        elapsed = (datetime.now() - self.start_time).total_seconds() / 60
        return self.processed_count / elapsed if elapsed > 0 else 0
    
    def should_continue(self) -> bool:
        return datetime.now() < self.end_time
    
    def process_with_ollama(self, prompt: str) -> Optional[Dict]:
        try:
            result = subprocess.run([
                'ollama', 'run', 'llama3.1:8b', '--format', 'json', prompt
            ], capture_output=True, text=True, timeout=self.timeout)
            
            if result.returncode == 0 and result.stdout:
                json_match = re.search(r'\{.*\}', result.stdout.strip(), re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass
            return None
        except:
            return None
    
    def create_prompt(self, candidate: Dict) -> str:
        name = candidate.get('name', 'Unknown')
        education = candidate.get('education', [])[:2]  # Limit for speed
        experience = candidate.get('experience', [])[:3]
        skills = candidate.get('skills', [])[:10]
        
        return f"""Fast analysis for {name}. Return JSON:
{{"personal_details":{{"name":"{name}","location":"TBD"}},"education_analysis":{{"degrees":[""],"quality":"score"}},"experience_analysis":{{"years":0,"companies":[""],"level":"entry/mid/senior"}},"technical_assessment":{{"skills":[""],"expertise":"level"}},"market_insights":{{"salary":"$X-Y","demand":"high/med/low"}},"cultural_assessment":{{"style":"","red_flags":[]}},"recruiter_recommendations":{{"difficulty":"easy/medium/hard","strategy":"approach"}},"searchability":["keyword1","keyword2"],"executive_summary":{{"pitch":"2-line summary","rating":"A/B/C"}}}}

Ed:{json.dumps(education)} Exp:{json.dumps(experience)} Skills:{json.dumps(skills)}

JSON only."""
    
    def run(self):
        print("\n📊 Loading candidates...")
        with open(self.nas_file, 'r') as f:
            candidates = json.load(f)
        
        total = len(candidates)
        print(f"📊 Total candidates: {total}")
        print(f"📊 Remaining: {total - self.last_processed_index}")
        
        for i in range(self.last_processed_index, total):
            if not self.should_continue():
                print(f"⏰ Time limit reached at {datetime.now().strftime('%I:%M %p')}")
                break
                
            candidate = candidates[i]
            candidate_id = candidate.get('id')
            candidate_name = candidate.get('name', 'Unknown')
            
            if not candidate_id:
                continue
            
            # Check if already exists
            safe_name = re.sub(r'[^\w\s-]', '', candidate_name).replace(' ', '_')[:30]
            output_file = self.enhanced_dir / f"{candidate_id}_{safe_name}_recruiter_enhanced.json"
            
            if output_file.exists():
                self.processed_count += 1
                if i % 20 == 0:
                    print(f"  ⏭️  [{i}] {candidate_name[:30]} (skipped - exists)")
                continue
            
            # Process with LLM
            prompt = self.create_prompt(candidate)
            analysis = self.process_with_ollama(prompt)
            
            if analysis:
                try:
                    with open(output_file, 'w') as f:
                        json.dump({
                            'candidate_id': candidate_id,
                            'name': candidate_name,
                            'recruiter_analysis': analysis,
                            'timestamp': datetime.now().isoformat(),
                            'processor': 'accelerated'
                        }, f, indent=2)
                    
                    self.processed_count += 1
                    print(f"  ✅ [{i}] {candidate_name[:30]}")
                    
                except Exception as e:
                    self.failed_count += 1
                    print(f"  💾 [{i}] Save error: {e}")
            else:
                self.failed_count += 1
                print(f"  ❌ [{i}] {candidate_name[:30]} - LLM failed")
            
            # Progress update
            if i % self.save_every == 0:
                self.save_progress(i)
                rate = self.get_rate()
                remaining = total - i
                eta_hours = (remaining / rate / 60) if rate > 0 else 0
                print(f"\n📊 Progress: {i}/{total} ({100*i/total:.1f}%)")
                print(f"⚡ Rate: {rate:.1f}/min | Processed: {self.processed_count} | Failed: {self.failed_count}")
                print(f"⏱️ ETA: {eta_hours:.1f} hours | CPU: {psutil.cpu_percent()}%")
                print(f"🧠 RAM: {psutil.virtual_memory().percent}%\n")
        
        print(f"\n🏁 PROCESSING COMPLETE!")
        print(f"📊 Final: {self.processed_count} processed, {self.failed_count} failed")
        self.save_progress(total)
    
    def graceful_shutdown(self, signum, frame):
        print(f"\n🛑 Graceful shutdown...")
        print(f"📊 Processed: {self.processed_count}, Failed: {self.failed_count}")
        self.save_progress(self.last_processed_index)
        sys.exit(0)

if __name__ == "__main__":
    processor = AcceleratedProcessor()
    processor.run()