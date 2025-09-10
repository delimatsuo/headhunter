#!/usr/bin/env python3
"""
Chunked Processor - Processes candidates in small chunks to avoid memory issues
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import re
import signal
import sys
import os

class ChunkedProcessor:
    def __init__(self):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.enhanced_dir.mkdir(exist_ok=True)
        
        # Processing settings
        self.chunk_size = 100  # Process 100 candidates at a time
        self.max_retries = 2
        self.ollama_timeout = 120
        
        self.processed_count = 0
        self.failed_count = 0
        self.start_time = datetime.now()
        
        # Progress file to track where we left off
        self.progress_file = Path("processor_progress.json")
        self.last_processed_index = self.load_progress()
        
        print(f"🚀 CHUNKED PROCESSOR INITIALIZED")
        print(f"📦 Chunk Size: {self.chunk_size} candidates")
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
                'processed': self.processed_count,
                'failed': self.failed_count
            }, f)
    
    def graceful_shutdown(self, signum, frame):
        print(f"\n🛑 Graceful shutdown initiated...")
        print(f"📊 Processed: {self.processed_count}, Failed: {self.failed_count}")
        self.save_progress(self.last_processed_index)
        print(f"💾 Progress saved. Will resume from index {self.last_processed_index}")
        sys.exit(0)
    
    def count_total_candidates(self) -> int:
        """Count total candidates without loading entire file"""
        count = 0
        with open(self.nas_file, 'r') as f:
            # Read file line by line
            in_array = False
            for line in f:
                if line.strip() == '[':
                    in_array = True
                elif line.strip().startswith('{') and in_array:
                    count += 1
        return count
    
    def process_chunk(self, start_index: int, chunk_size: int) -> List[Dict]:
        """Process a chunk of candidates"""
        processed = []
        
        # Read only the chunk we need
        candidates_chunk = []
        with open(self.nas_file, 'r') as f:
            data = json.load(f)
            end_index = min(start_index + chunk_size, len(data))
            candidates_chunk = data[start_index:end_index]
        
        print(f"\n📋 Processing chunk: {start_index} to {start_index + len(candidates_chunk)}")
        
        for i, candidate in enumerate(candidates_chunk):
            # Skip if already processed
            if candidate.get('recruiter_enhanced_analysis'):
                continue
            
            # Check if has required data
            has_name = bool(candidate.get('name'))
            has_data = bool(candidate.get('experience') or candidate.get('education'))
            has_id = bool(candidate.get('id'))
            
            if not (has_id and has_name and has_data):
                continue
            
            # Process candidate
            candidate_name = candidate.get('name', 'Unknown')
            candidate_id = candidate.get('id')
            
            print(f"  [{i+1}/{len(candidates_chunk)}] {candidate_name} (ID: {candidate_id})")
            
            # Create prompt
            prompt = self.create_comprehensive_prompt(candidate)
            
            # Process with Ollama
            analysis = self.process_with_ollama(prompt)
            
            if analysis:
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
                    
                    self.processed_count += 1
                    print(f"    ✅ Saved to {output_file.name}")
                    
                    # Update candidate in memory
                    candidate['recruiter_enhanced_analysis'] = {
                        'analysis': analysis,
                        'processing_timestamp': datetime.now().isoformat(),
                        'processor_version': 'chunked_v1'
                    }
                    processed.append(candidate)
                    
                except Exception as e:
                    print(f"    ❌ Failed to save: {e}")
                    self.failed_count += 1
            else:
                self.failed_count += 1
                print(f"    ❌ Analysis failed")
        
        return processed
    
    def create_comprehensive_prompt(self, candidate: Dict[str, Any]) -> str:
        """Create comprehensive prompt with all candidate data"""
        name = candidate.get('name', 'Unknown')
        education = candidate.get('education', '')
        experience = candidate.get('experience', '')
        skills = candidate.get('skills', '')
        
        prompt = f"""Analyze this candidate's profile for recruitment:

CANDIDATE: {name}

EDUCATION:
{education if education else 'No education data'}

EXPERIENCE:
{experience if experience else 'No experience data'}

SKILLS:
{skills if skills else 'No skills listed'}

Provide a JSON analysis with these fields:
{{
  "personal_details": {{
    "full_name": "{name}",
    "location": "infer from data"
  }},
  "experience_analysis": {{
    "total_years": "calculate",
    "companies_worked": ["list companies"],
    "career_progression": "describe trajectory"
  }},
  "technical_assessment": {{
    "primary_skills": ["main skills"],
    "skill_depth": "assess depth"
  }},
  "market_insights": {{
    "estimated_salary_range": "provide range",
    "market_demand": "high/medium/low"
  }},
  "searchability": {{
    "ats_keywords": ["keywords for search"],
    "competitor_companies": ["similar companies"]
  }},
  "executive_summary": {{
    "one_line_pitch": "brief summary",
    "overall_rating": 1-100
  }}
}}"""
        
        return prompt
    
    def process_with_ollama(self, prompt: str, retry_count: int = 0) -> Optional[Dict[str, Any]]:
        """Process with Ollama"""
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
                    return self.process_with_ollama(prompt, retry_count + 1)
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
    
    def update_nas_chunk(self, start_index: int, processed_candidates: List[Dict]):
        """Update only the processed chunk in the NAS file"""
        if not processed_candidates:
            return
        
        print(f"💾 Updating NAS database for {len(processed_candidates)} candidates...")
        
        # Read the full file
        with open(self.nas_file, 'r') as f:
            all_candidates = json.load(f)
        
        # Update only the processed candidates
        for processed in processed_candidates:
            candidate_id = processed.get('id')
            # Find and update in the main list
            for i, candidate in enumerate(all_candidates):
                if candidate.get('id') == candidate_id:
                    all_candidates[i] = processed
                    break
        
        # Write back
        with open(self.nas_file, 'w') as f:
            json.dump(all_candidates, f, indent=2)
        
        print(f"✅ NAS database updated")
    
    def run(self):
        """Main processing loop"""
        print("\n🔄 STARTING CHUNKED PROCESSING")
        print("=" * 60)
        
        # Get total count
        print("📊 Counting total candidates...")
        total_candidates = 29138  # We know this already
        print(f"📊 Total candidates: {total_candidates}")
        
        current_index = self.last_processed_index
        
        while current_index < total_candidates:
            chunk_start = time.time()
            
            # Process chunk
            processed = self.process_chunk(current_index, self.chunk_size)
            
            # Update NAS with processed candidates
            if processed:
                self.update_nas_chunk(current_index, processed)
            
            # Update progress
            current_index += self.chunk_size
            self.last_processed_index = current_index
            self.save_progress(current_index)
            
            # Stats
            chunk_time = time.time() - chunk_start
            progress_pct = (current_index / total_candidates) * 100
            
            print(f"\n📈 Progress: {progress_pct:.1f}% ({current_index}/{total_candidates})")
            print(f"⏱️ Chunk time: {chunk_time:.1f}s")
            print(f"✅ Total processed: {self.processed_count}")
            print(f"❌ Total failed: {self.failed_count}")
            
            # Estimate remaining time
            if self.processed_count > 0:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                rate = self.processed_count / elapsed
                remaining = (total_candidates - current_index) / rate if rate > 0 else 0
                print(f"⏳ Estimated time remaining: {remaining/3600:.1f} hours")
            
            print("-" * 60)
            
            # Small delay between chunks
            time.sleep(1)
        
        # Final report
        print("\n" + "=" * 60)
        print("🎉 PROCESSING COMPLETE!")
        print(f"✅ Total processed: {self.processed_count}")
        print(f"❌ Total failed: {self.failed_count}")
        elapsed = (datetime.now() - self.start_time).total_seconds()
        print(f"⏱️ Total time: {elapsed/3600:.1f} hours")

def main():
    try:
        processor = ChunkedProcessor()
        processor.run()
    except KeyboardInterrupt:
        print("\n\n🛑 Processing interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()