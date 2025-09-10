#!/usr/bin/env python3
"""
Smart Batch Processor for All Candidates
Processes all candidates with intelligent resource management
Uses system commands for monitoring (no psutil needed)
"""

import json
import os
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal
import sys
import platform

class SystemMonitor:
    """Monitor system resources using OS commands"""
    
    def __init__(self):
        self.is_mac = platform.system() == "Darwin"
        self.current_workers = 2  # Start conservative
        self.max_workers = 4
        self.min_workers = 1
        self.last_check = time.time()
        self.check_interval = 30  # Check every 30 seconds
        
    def get_memory_usage(self) -> float:
        """Get memory pressure (macOS specific)"""
        try:
            if self.is_mac:
                # Use vm_stat on macOS
                result = subprocess.run(
                    ['vm_stat'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if 'Pages free' in line:
                            free_pages = int(line.split(':')[1].strip().replace('.', ''))
                            # Each page is 4096 bytes
                            free_gb = (free_pages * 4096) / (1024**3)
                            return free_gb
            return 4.0  # Default assumption
        except:
            return 4.0  # Default if check fails
    
    def get_cpu_load(self) -> float:
        """Get system load average"""
        try:
            result = subprocess.run(
                ['uptime'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                # Extract load average (1 minute)
                output = result.stdout
                if 'load average' in output:
                    load_part = output.split('load average')[1]
                    load_values = load_part.replace(':', '').strip().split(',')
                    if load_values:
                        return float(load_values[0].strip())
            return 2.0  # Default assumption
        except:
            return 2.0
    
    def check_ollama_health(self) -> bool:
        """Check if Ollama is responsive"""
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def should_adjust_workers(self) -> Optional[int]:
        """Determine if we should adjust worker count"""
        if time.time() - self.last_check < self.check_interval:
            return None
            
        self.last_check = time.time()
        
        # Get system metrics
        free_memory = self.get_memory_usage()
        cpu_load = self.get_cpu_load()
        
        print(f"   📊 System Check: Free Memory: {free_memory:.1f}GB | Load: {cpu_load:.2f}")
        
        # Decision logic
        if free_memory < 1.0:  # Less than 1GB free
            return max(self.min_workers, self.current_workers - 1)
        elif cpu_load > 4.0:  # High load
            return max(self.min_workers, self.current_workers - 1)
        elif free_memory > 4.0 and cpu_load < 2.0:  # System has capacity
            return min(self.max_workers, self.current_workers + 1)
        
        return None  # No change needed

class SmartBatchProcessor:
    """Process all candidates with smart resource management"""
    
    def __init__(self):
        # Use NAS enhanced_analysis directory
        self.output_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.output_dir.mkdir(exist_ok=True)
        self.monitor = SystemMonitor()
        self.processed_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.total_count = 0
        self.start_time = None
        self.processing_times = []
        self.shutdown_requested = False
        self.checkpoint_file = "processing_checkpoint.json"
        
        # Set up graceful shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        print("\n⚠️ Shutdown requested. Saving progress...")
        self.shutdown_requested = True
        self.save_checkpoint()
        print(f"✅ Progress saved. Processed {self.processed_count} candidates.")
        sys.exit(0)
    
    def find_candidate_file(self) -> Optional[str]:
        """Find the candidate data file"""
        possible_files = [
            "/Volumes/DataBackup/business analysis/full_candidates_merged.json",
            "/Volumes/DataBackup/business analysis/comprehensive_candidates_processed.json",
            "scripts/comprehensive_candidates_processed.json",
            "comprehensive_candidates_processed.json"
        ]
        
        for file_path in possible_files:
            if os.path.exists(file_path):
                return file_path
        
        # Look for any large JSON file
        print("📂 Searching for candidate files...")
        for file in Path("scripts").glob("*candidates*.json"):
            if file.stat().st_size > 1000000:  # Larger than 1MB
                return str(file)
        
        return None
    
    def load_candidates(self, file_path: str) -> List[Dict[str, Any]]:
        """Load candidates from JSON file"""
        print(f"📂 Loading candidates from {file_path}")
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    
    def load_checkpoint(self) -> set:
        """Load processing checkpoint"""
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
                return set(checkpoint.get('processed_ids', []))
        return set()
    
    def save_checkpoint(self):
        """Save processing checkpoint"""
        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'processed_ids': list(self.get_processed_ids()),
            'processed_count': self.processed_count,
            'failed_count': self.failed_count,
            'skipped_count': self.skipped_count
        }
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def get_processed_ids(self) -> set:
        """Get IDs of already processed candidates"""
        processed = set()
        for file in self.output_dir.glob("*_enhanced.json"):
            candidate_id = file.stem.replace('_enhanced', '')
            processed.add(candidate_id)
        return processed
    
    def create_enhanced_prompt(self, candidate: Dict[str, Any]) -> str:
        """Create comprehensive prompt for PRD-compliant analysis"""
        name = candidate.get('name', 'Unknown')
        comments = candidate.get('comments', [])
        
        # Build comment summary
        comment_text = ""
        if comments:
            comment_text = "\n\nRecruiter Comments:\n"
            for comment in comments[-5:]:  # Last 5 comments
                text = comment.get('text', '')
                if text:
                    comment_text += f"- {text[:150]}...\n"
        
        prompt = f"""Analyze this candidate and provide a JSON assessment:

Candidate: {name}
Status: {candidate.get('status', 'Unknown')}
{comment_text}

Return ONLY valid JSON with these fields:
{{
  "career_trajectory": {{
    "current_level": "Junior/Mid/Senior/Principal/Executive",
    "progression_speed": "slow/steady/fast",
    "years_experience": 0
  }},
  "leadership_scope": {{
    "has_leadership": true/false,
    "team_size": 0,
    "leadership_level": "none/lead/manager/director/vp"
  }},
  "company_pedigree": {{
    "company_tier": "startup/mid_market/enterprise/faang",
    "stability_pattern": "job_hopper/stable/very_stable"
  }},
  "cultural_signals": {{
    "strengths": ["strength1", "strength2"],
    "red_flags": []
  }},
  "skill_assessment": {{
    "technical_skills": {{
      "core_competencies": ["skill1", "skill2"]
    }},
    "soft_skills": {{
      "communication": "developing/strong/exceptional"
    }}
  }},
  "recruiter_insights": {{
    "placement_likelihood": "low/medium/high",
    "best_fit_roles": ["role1"]
  }},
  "search_optimization": {{
    "keywords": ["keyword1", "keyword2"]
  }},
  "executive_summary": {{
    "one_line_pitch": "Brief summary",
    "overall_rating": 0
  }}
}}"""
        return prompt
    
    def process_with_ollama(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Process with Ollama"""
        try:
            result = subprocess.run(
                ['ollama', 'run', 'llama3.1:8b', prompt],
                capture_output=True,
                text=True,
                timeout=45
            )
            
            if result.returncode != 0:
                return None
            
            response = result.stdout.strip()
            
            # Extract JSON
            if '{' in response and '}' in response:
                start = response.index('{')
                end = response.rindex('}') + 1
                json_str = response[start:end]
                return json.loads(json_str)
            
            return None
            
        except subprocess.TimeoutExpired:
            return None
        except json.JSONDecodeError:
            return None
        except Exception:
            return None
    
    def process_candidate(self, candidate: Dict[str, Any]) -> Tuple[str, str, float]:
        """Process a single candidate"""
        candidate_id = candidate.get('id', 'unknown')
        
        # Check if already processed
        output_file = self.output_dir / f"{candidate_id}_enhanced.json"
        if output_file.exists():
            return candidate_id, 'skipped', 0.0
        
        start_time = time.time()
        
        # Create and process prompt
        prompt = self.create_enhanced_prompt(candidate)
        analysis = self.process_with_ollama(prompt)
        
        if analysis:
            # Save result
            enhanced_data = {
                'candidate_id': candidate_id,
                'name': candidate.get('name', 'Unknown'),
                'enhanced_analysis': analysis,
                'timestamp': datetime.now().isoformat()
            }
            
            with open(output_file, 'w') as f:
                json.dump(enhanced_data, f, indent=2)
            
            return candidate_id, 'success', time.time() - start_time
        else:
            return candidate_id, 'failed', time.time() - start_time
    
    def run(self):
        """Run the batch processor"""
        print("🚀 Smart Batch Processor for All Candidates")
        print("="*60)
        
        # Check Ollama
        if not self.monitor.check_ollama_health():
            print("❌ Ollama is not running. Starting Ollama...")
            subprocess.run(['ollama', 'serve'], capture_output=True, timeout=2)
            time.sleep(2)
            if not self.monitor.check_ollama_health():
                print("❌ Could not start Ollama. Please start it manually.")
                return
        
        print("✅ Ollama is running")
        
        # Find candidate file
        input_file = self.find_candidate_file()
        if not input_file:
            print("❌ No candidate data file found")
            return
        
        # Load candidates
        candidates = self.load_candidates(input_file)
        self.total_count = len(candidates)
        print(f"📋 Found {self.total_count} total candidates")
        
        # Check already processed
        processed_ids = self.get_processed_ids()
        unprocessed = [c for c in candidates if c.get('id') not in processed_ids]
        
        print(f"✅ Already processed: {len(processed_ids)}")
        print(f"📊 Need to process: {len(unprocessed)}")
        
        if not unprocessed:
            print("✨ All candidates already processed!")
            return
        
        self.start_time = time.time()
        batch_size = 20  # Smaller batches for better control
        
        # Process in batches
        for i in range(0, len(unprocessed), batch_size):
            if self.shutdown_requested:
                break
            
            batch = unprocessed[i:i+batch_size]
            batch_num = i//batch_size + 1
            total_batches = (len(unprocessed) + batch_size - 1)//batch_size
            
            # Check if we should adjust workers
            new_workers = self.monitor.should_adjust_workers()
            if new_workers:
                self.monitor.current_workers = new_workers
                print(f"   ⚙️ Adjusted workers to: {new_workers}")
            
            print(f"\n📦 Batch {batch_num}/{total_batches} ({self.monitor.current_workers} parallel workers)")
            
            # Process batch
            with ThreadPoolExecutor(max_workers=self.monitor.current_workers) as executor:
                futures = [executor.submit(self.process_candidate, c) for c in batch]
                
                for future in as_completed(futures):
                    if self.shutdown_requested:
                        break
                    
                    candidate_id, status, proc_time = future.result()
                    
                    if status == 'success':
                        self.processed_count += 1
                        if proc_time > 0:
                            self.processing_times.append(proc_time)
                    elif status == 'failed':
                        self.failed_count += 1
                    else:
                        self.skipped_count += 1
            
            # Progress update
            total_done = self.processed_count + self.skipped_count + len(processed_ids)
            progress = (total_done / self.total_count) * 100
            
            if self.processing_times:
                avg_time = sum(self.processing_times) / len(self.processing_times)
                remaining = len(unprocessed) - i - batch_size
                if remaining > 0:
                    eta_seconds = (remaining * avg_time) / self.monitor.current_workers
                    eta_minutes = eta_seconds / 60
                    print(f"   ⏱️ ETA: {eta_minutes:.1f} minutes")
            
            print(f"   📊 Progress: {progress:.1f}% | ✅ {self.processed_count} | ❌ {self.failed_count}")
            
            # Save checkpoint every 5 batches
            if batch_num % 5 == 0:
                self.save_checkpoint()
            
            # Brief pause
            if i + batch_size < len(unprocessed):
                time.sleep(1)
        
        # Final report
        elapsed = time.time() - self.start_time
        print("\n" + "="*60)
        print("✅ PROCESSING COMPLETE")
        print(f"📊 Processed: {self.processed_count} candidates")
        print(f"⏭️ Skipped: {self.skipped_count} (already done)")
        print(f"❌ Failed: {self.failed_count}")
        print(f"⏱️ Total time: {elapsed/60:.1f} minutes")
        
        if self.processing_times:
            avg = sum(self.processing_times) / len(self.processing_times)
            print(f"📈 Avg time per candidate: {avg:.1f}s")
        
        print(f"💾 Results saved to: {self.output_dir}/")
        self.save_checkpoint()

def main():
    """Main entry point"""
    processor = SmartBatchProcessor()
    processor.run()

if __name__ == "__main__":
    main()