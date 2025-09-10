#!/usr/bin/env python3
"""
Intelligent Batch Processor with Resource Monitoring
Automatically adjusts parallel processing based on system resources
to prevent system crashes while maximizing throughput.
"""

import json
import os
import time
import psutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import signal
import sys

class ResourceMonitor:
    """Monitor system resources and Ollama status"""
    
    def __init__(self):
        self.cpu_threshold = 80.0  # Max CPU usage %
        self.memory_threshold = 85.0  # Max memory usage %
        self.ollama_response_threshold = 60  # Max seconds for Ollama response
        self.check_interval = 5  # Seconds between resource checks
        self.monitoring = True
        self.current_workers = 1
        self.max_workers = 4
        self.min_workers = 1
        
    def get_system_stats(self) -> Dict[str, float]:
        """Get current system resource usage"""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'available_memory_gb': psutil.virtual_memory().available / (1024**3),
            'disk_usage_percent': psutil.disk_usage('/').percent
        }
    
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
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def recommend_worker_count(self) -> int:
        """Recommend number of parallel workers based on resources"""
        stats = self.get_system_stats()
        
        # Check if system is under stress
        if stats['cpu_percent'] > self.cpu_threshold:
            return max(self.min_workers, self.current_workers - 1)
        elif stats['memory_percent'] > self.memory_threshold:
            return max(self.min_workers, self.current_workers - 1)
        elif stats['available_memory_gb'] < 2.0:  # Less than 2GB available
            return self.min_workers
        elif stats['cpu_percent'] < 50 and stats['memory_percent'] < 60:
            # System has capacity for more
            return min(self.max_workers, self.current_workers + 1)
        else:
            return self.current_workers

class IntelligentBatchProcessor:
    """Process candidates with intelligent resource management"""
    
    def __init__(self, input_file: str, output_dir: str = "enhanced_analysis"):
        self.input_file = input_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.monitor = ResourceMonitor()
        self.processed_count = 0
        self.failed_count = 0
        self.total_count = 0
        self.start_time = None
        self.processing_times = []
        self.current_executor = None
        self.shutdown_requested = False
        
        # Set up graceful shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        print("\n⚠️ Shutdown requested. Finishing current batch...")
        self.shutdown_requested = True
        if self.current_executor:
            self.current_executor.shutdown(wait=True)
        self.save_progress_report()
        sys.exit(0)
    
    def load_candidates(self) -> List[Dict[str, Any]]:
        """Load candidates from JSON file"""
        print(f"📂 Loading candidates from {self.input_file}")
        with open(self.input_file, 'r') as f:
            data = json.load(f)
        return data
    
    def check_already_processed(self, candidate_id: str) -> bool:
        """Check if candidate has already been processed"""
        output_file = self.output_dir / f"{candidate_id}_enhanced.json"
        return output_file.exists()
    
    def create_enhanced_prompt(self, candidate: Dict[str, Any]) -> str:
        """Create comprehensive prompt for PRD-compliant analysis"""
        # Extract candidate information
        name = candidate.get('name', 'Unknown')
        comments = candidate.get('comments', [])
        
        # Build comment history
        comment_text = ""
        if comments:
            comment_text = "\n\nRecruiter Comments and History:\n"
            for comment in comments[-10:]:  # Last 10 comments
                author = comment.get('author', 'Unknown')
                date = comment.get('date', 'N/A')
                text = comment.get('text', '')
                if text:
                    comment_text += f"[{date}] {author}: {text[:200]}...\n"
        
        prompt = f"""You are an expert executive search consultant analyzing a candidate profile.
Analyze the following candidate and provide a comprehensive assessment.

Candidate: {name}
ID: {candidate.get('id', 'unknown')}

Current Status: {candidate.get('status', 'Unknown')}
Source: {candidate.get('source', 'Unknown')}
Location: {candidate.get('location', 'Unknown')}

{comment_text}

Provide a detailed JSON analysis with ALL of the following fields:

{{
  "career_trajectory": {{
    "current_level": "Junior/Mid/Senior/Staff/Principal/Executive",
    "progression_speed": "slow/steady/fast/exceptional",
    "trajectory_type": "individual_contributor/technical_leadership/people_management/executive",
    "years_experience": 0,
    "career_highlights": ["achievement1", "achievement2"],
    "role_progression": ["role1", "role2", "current_role"],
    "industry_experience": ["industry1", "industry2"],
    "velocity": "accelerating/steady/plateauing"
  }},
  "leadership_scope": {{
    "has_leadership": true/false,
    "team_size": 0,
    "leadership_level": "none/team_lead/manager/director/vp/c_level",
    "leadership_style": "collaborative/directive/coaching/strategic",
    "direct_reports": 0,
    "indirect_influence": 0,
    "cross_functional": true/false,
    "budget_responsibility": "none/small/medium/large",
    "p_and_l": true/false
  }},
  "company_pedigree": {{
    "current_company": "Company Name",
    "company_tier": "startup/scale_up/mid_market/enterprise/faang",
    "previous_companies": ["company1", "company2"],
    "company_tiers": ["tier1", "tier2"],
    "industry_reputation": "unknown/rising/established/leading",
    "years_at_current": 0,
    "stability_pattern": "job_hopper/stable/very_stable"
  }},
  "cultural_signals": {{
    "work_style": "independent/collaborative/hybrid",
    "communication_style": "direct/diplomatic/analytical",
    "values_alignment": ["value1", "value2"],
    "motivators": ["motivator1", "motivator2"],
    "red_flags": ["flag1", "flag2"] or [],
    "strengths": ["strength1", "strength2", "strength3"],
    "development_areas": ["area1", "area2"],
    "cultural_fit_indicators": ["indicator1", "indicator2"]
  }},
  "skill_assessment": {{
    "technical_skills": {{
      "core_competencies": ["skill1", "skill2", "skill3"],
      "emerging_skills": ["skill1", "skill2"],
      "skill_depth": "surface/intermediate/deep/expert",
      "technical_leadership": true/false
    }},
    "soft_skills": {{
      "communication": "weak/developing/strong/exceptional",
      "collaboration": "weak/developing/strong/exceptional",
      "problem_solving": "weak/developing/strong/exceptional",
      "leadership": "weak/developing/strong/exceptional",
      "adaptability": "weak/developing/strong/exceptional"
    }},
    "domain_expertise": ["domain1", "domain2"],
    "certifications": ["cert1", "cert2"] or []
  }},
  "recruiter_insights": {{
    "summary_assessment": "Brief overall assessment",
    "placement_likelihood": "low/medium/high",
    "salary_expectations": "below_market/market/above_market",
    "availability": "immediate/short_notice/long_notice/not_looking",
    "geographical_flexibility": "none/limited/flexible/fully_remote",
    "best_fit_roles": ["role1", "role2"],
    "companies_to_target": ["company1", "company2"],
    "key_selling_points": ["point1", "point2", "point3"],
    "concerns": ["concern1", "concern2"] or []
  }},
  "search_optimization": {{
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
    "similar_profiles": ["profile_type1", "profile_type2"],
    "niche_expertise": ["expertise1", "expertise2"],
    "competitive_advantage": "What makes this candidate unique",
    "search_tags": ["tag1", "tag2", "tag3"]
  }},
  "executive_summary": {{
    "one_line_pitch": "A single compelling line about the candidate",
    "ideal_next_role": "Description of perfect next position",
    "three_year_trajectory": "Where they could be in 3 years",
    "retention_risk": "low/medium/high",
    "package_expectations": {{
      "base_salary_range": "range",
      "equity_expectations": "none/nice_to_have/required/critical",
      "benefits_priorities": ["priority1", "priority2"]
    }},
    "overall_rating": 0
  }}
}}

Provide ONLY valid JSON output, no additional text."""
        
        return prompt
    
    def process_with_ollama(self, prompt: str, timeout: int = 60) -> Optional[Dict[str, Any]]:
        """Process prompt with Ollama with timeout"""
        try:
            result = subprocess.run(
                ['ollama', 'run', 'llama3.1:8b', prompt],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                return None
            
            # Parse JSON from response
            response = result.stdout.strip()
            
            # Try to extract JSON
            if '{' in response and '}' in response:
                start = response.index('{')
                end = response.rindex('}') + 1
                json_str = response[start:end]
                return json.loads(json_str)
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"⏱️ Timeout processing candidate")
            return None
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON response")
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def process_candidate(self, candidate: Dict[str, Any]) -> Tuple[str, bool, float]:
        """Process a single candidate"""
        candidate_id = candidate.get('id', 'unknown')
        
        # Check if already processed
        if self.check_already_processed(candidate_id):
            return candidate_id, True, 0.0
        
        start_time = time.time()
        
        # Create prompt
        prompt = self.create_enhanced_prompt(candidate)
        
        # Process with Ollama
        analysis = self.process_with_ollama(prompt)
        
        if analysis:
            # Save enhanced analysis
            output_file = self.output_dir / f"{candidate_id}_enhanced.json"
            enhanced_data = {
                'candidate_id': candidate_id,
                'name': candidate.get('name', 'Unknown'),
                'original_data': candidate,
                'enhanced_analysis': analysis,
                'processing_timestamp': datetime.now().isoformat()
            }
            
            with open(output_file, 'w') as f:
                json.dump(enhanced_data, f, indent=2)
            
            processing_time = time.time() - start_time
            return candidate_id, True, processing_time
        else:
            processing_time = time.time() - start_time
            return candidate_id, False, processing_time
    
    def process_batch(self, candidates: List[Dict[str, Any]], max_workers: int) -> Dict[str, Any]:
        """Process a batch of candidates with parallel workers"""
        batch_results = {
            'processed': 0,
            'failed': 0,
            'skipped': 0,
            'times': []
        }
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            self.current_executor = executor
            futures = []
            
            for candidate in candidates:
                if self.shutdown_requested:
                    break
                future = executor.submit(self.process_candidate, candidate)
                futures.append(future)
            
            for future in as_completed(futures):
                if self.shutdown_requested:
                    break
                    
                candidate_id, success, processing_time = future.result()
                
                if processing_time == 0.0:  # Already processed
                    batch_results['skipped'] += 1
                elif success:
                    batch_results['processed'] += 1
                    batch_results['times'].append(processing_time)
                else:
                    batch_results['failed'] += 1
                
                # Update global counters
                self.processed_count = batch_results['processed']
                self.failed_count = batch_results['failed']
        
        self.current_executor = None
        return batch_results
    
    def save_progress_report(self):
        """Save current progress report"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_candidates': self.total_count,
            'processed': self.processed_count,
            'failed': self.failed_count,
            'elapsed_time_seconds': elapsed,
            'average_processing_time': sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0,
            'estimated_remaining_time': self.estimate_remaining_time()
        }
        
        with open('processing_progress.json', 'w') as f:
            json.dump(report, f, indent=2)
    
    def estimate_remaining_time(self) -> float:
        """Estimate remaining processing time"""
        if not self.processing_times:
            return 0
        
        avg_time = sum(self.processing_times) / len(self.processing_times)
        remaining = self.total_count - self.processed_count - self.failed_count
        return remaining * avg_time / self.monitor.current_workers
    
    def run(self):
        """Run the intelligent batch processor"""
        print("🚀 Starting Intelligent Batch Processor")
        print("📊 Resource Monitoring Enabled")
        
        # Check Ollama
        if not self.monitor.check_ollama_health():
            print("❌ Ollama is not running. Please start Ollama first.")
            return
        
        # Load candidates
        candidates = self.load_candidates()
        self.total_count = len(candidates)
        print(f"📋 Found {self.total_count} candidates to process")
        
        # Filter out already processed
        unprocessed = []
        for candidate in candidates:
            if not self.check_already_processed(candidate.get('id', 'unknown')):
                unprocessed.append(candidate)
        
        print(f"📊 {len(unprocessed)} candidates need processing")
        print(f"✅ {self.total_count - len(unprocessed)} already processed")
        
        if not unprocessed:
            print("✨ All candidates already processed!")
            return
        
        self.start_time = time.time()
        
        # Process in adaptive batches
        batch_size = 50
        for i in range(0, len(unprocessed), batch_size):
            if self.shutdown_requested:
                break
                
            batch = unprocessed[i:i+batch_size]
            
            # Get recommended worker count
            stats = self.monitor.get_system_stats()
            recommended_workers = self.monitor.recommend_worker_count()
            self.monitor.current_workers = recommended_workers
            
            print(f"\n📦 Processing batch {i//batch_size + 1}/{(len(unprocessed) + batch_size - 1)//batch_size}")
            print(f"   System: CPU {stats['cpu_percent']:.1f}% | RAM {stats['memory_percent']:.1f}%")
            print(f"   Workers: {recommended_workers} parallel processes")
            
            # Process batch
            batch_results = self.process_batch(batch, recommended_workers)
            
            # Update statistics
            if batch_results['times']:
                self.processing_times.extend(batch_results['times'])
            
            # Progress update
            total_processed = self.processed_count + (self.total_count - len(unprocessed))
            progress = (total_processed / self.total_count) * 100
            avg_time = sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0
            
            print(f"   ✅ Processed: {batch_results['processed']} | ❌ Failed: {batch_results['failed']} | ⏭️ Skipped: {batch_results['skipped']}")
            print(f"   📊 Overall Progress: {progress:.1f}% ({total_processed}/{self.total_count})")
            print(f"   ⏱️ Avg time per candidate: {avg_time:.2f}s")
            
            # Save progress
            self.save_progress_report()
            
            # Brief pause between batches
            if i + batch_size < len(unprocessed):
                time.sleep(2)
        
        # Final report
        elapsed = time.time() - self.start_time
        print("\n" + "="*60)
        print("✅ PROCESSING COMPLETE")
        print(f"📊 Total processed: {self.processed_count}")
        print(f"❌ Failed: {self.failed_count}")
        print(f"⏱️ Total time: {elapsed/60:.2f} minutes")
        if self.processing_times:
            print(f"📈 Average time per candidate: {sum(self.processing_times)/len(self.processing_times):.2f}s")
        print(f"💾 Results saved to: {self.output_dir}")
        
        # Save final report
        self.save_progress_report()

def main():
    """Main entry point"""
    # Path to merged candidate data
    input_file = "/Volumes/DataBackup/business analysis/full_candidates_merged.json"
    
    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        print("Looking for alternative files...")
        
        # Try alternative locations
        alternatives = [
            "scripts/comprehensive_candidates_processed.json",
            "comprehensive_candidates_processed.json",
            "/Volumes/DataBackup/business analysis/comprehensive_candidates_processed.json"
        ]
        
        for alt in alternatives:
            if os.path.exists(alt):
                input_file = alt
                print(f"✅ Found: {input_file}")
                break
        else:
            print("❌ No candidate data file found")
            return
    
    # Create and run processor
    processor = IntelligentBatchProcessor(input_file)
    processor.run()

if __name__ == "__main__":
    main()