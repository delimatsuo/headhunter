#!/usr/bin/env python3
"""
Process ALL candidates from NAS database with smart resource management
Continues until all candidates are processed
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

class CompleteBatchProcessor:
    def __init__(self):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.enhanced_dir.mkdir(exist_ok=True)
        self.batch_size = 100
        self.max_retries = 2
        
    def load_nas_data(self):
        """Load the NAS database"""
        print("📂 Loading NAS database...")
        with open(self.nas_file, 'r') as f:
            return json.load(f)
    
    def save_nas_data(self, data):
        """Save updated data back to NAS with backup"""
        backup_file = self.nas_file.replace('.json', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        print(f"💾 Creating backup: {backup_file}")
        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print("💾 Updating NAS database...")
        with open(self.nas_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def create_enhanced_prompt(self, candidate: Dict[str, Any]) -> str:
        """Create PRD-compliant prompt"""
        name = candidate.get('name', 'Unknown')
        comments = candidate.get('comments', [])
        
        comment_text = ""
        if comments:
            comment_text = "\n\nRecruiter Comments:\n"
            for comment in comments[-5:]:
                text = comment.get('text', '')
                if text:
                    comment_text += f"- {text[:150]}...\n"
        
        prompt = f"""Analyze this candidate and provide a JSON assessment:

Candidate: {name}
ID: {candidate.get('id')}
Status: {candidate.get('status', 'Unknown')}
{comment_text}

Return ONLY valid JSON with ALL these fields:
{{
  "career_trajectory": {{
    "current_level": "Junior/Mid/Senior/Principal/Executive",
    "progression_speed": "slow/steady/fast",
    "trajectory_type": "individual_contributor/technical_leadership/people_management",
    "years_experience": 5,
    "velocity": "accelerating/steady/plateauing"
  }},
  "leadership_scope": {{
    "has_leadership": false,
    "team_size": 0,
    "leadership_level": "none/lead/manager/director/vp",
    "leadership_style": "collaborative/directive/coaching"
  }},
  "company_pedigree": {{
    "company_tier": "startup/mid_market/enterprise/faang",
    "company_tiers": ["startup", "mid_market"],
    "stability_pattern": "job_hopper/stable/very_stable"
  }},
  "cultural_signals": {{
    "strengths": ["technical expertise", "communication"],
    "red_flags": [],
    "work_style": "independent/collaborative"
  }},
  "skill_assessment": {{
    "technical_skills": {{
      "core_competencies": ["Python", "React", "AWS"],
      "skill_depth": "intermediate/deep/expert"
    }},
    "soft_skills": {{
      "communication": "developing/strong/exceptional",
      "leadership": "developing/strong/exceptional"
    }}
  }},
  "recruiter_insights": {{
    "placement_likelihood": "low/medium/high",
    "best_fit_roles": ["Senior Engineer", "Tech Lead"],
    "salary_expectations": "market/above_market",
    "availability": "immediate/short_notice/not_looking"
  }},
  "search_optimization": {{
    "keywords": ["python", "react", "leadership", "startup"],
    "search_tags": ["technical", "leadership", "growth"]
  }},
  "executive_summary": {{
    "one_line_pitch": "Experienced engineer with startup experience",
    "ideal_next_role": "Senior or Lead role at growth-stage company",
    "overall_rating": 75
  }}
}}"""
        return prompt
    
    def process_with_ollama(self, prompt: str, retry_count: int = 0) -> Optional[Dict[str, Any]]:
        """Process with Ollama with retry logic"""
        try:
            result = subprocess.run(
                ['ollama', 'run', 'llama3.1:8b', prompt],
                capture_output=True,
                text=True,
                timeout=60
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
        except json.JSONDecodeError as e:
            print(f"❌ JSON Error: {e}")
            if retry_count < self.max_retries:
                time.sleep(2)
                return self.process_with_ollama(prompt, retry_count + 1)
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def process_all(self):
        """Process ALL candidates in batches until complete"""
        start_time = datetime.now()
        
        # Load data
        candidates = self.load_nas_data()
        total_candidates = len(candidates)
        print(f"📊 Total candidates: {total_candidates}")
        
        # Find unprocessed candidates
        unprocessed = []
        for i, candidate in enumerate(candidates):
            if not candidate.get('enhanced_analysis') and candidate.get('id'):
                unprocessed.append((i, candidate))
        
        initial_unprocessed = len(unprocessed)
        print(f"📊 Unprocessed candidates: {initial_unprocessed}")
        
        if not unprocessed:
            print("✅ All candidates already processed!")
            return
        
        total_processed = 0
        total_failed = 0
        batch_num = 0
        
        print(f"\n🚀 Starting continuous processing of {initial_unprocessed} candidates")
        print("=" * 60)
        
        while unprocessed:
            batch_num += 1
            batch = unprocessed[:self.batch_size]
            remaining = len(unprocessed)
            
            print(f"\n📦 Batch {batch_num} - Processing {len(batch)} candidates ({remaining} remaining)")
            
            batch_processed = 0
            batch_failed = 0
            
            for j, (idx, candidate) in enumerate(batch):
                candidate_id = candidate.get('id')
                print(f"  [{j+1}/{len(batch)}] Processing {candidate_id}...", end="")
                
                # Create prompt
                prompt = self.create_enhanced_prompt(candidate)
                
                # Process with Ollama (with retries)
                analysis = self.process_with_ollama(prompt)
                
                if analysis:
                    # Update candidate in main list
                    candidates[idx]['enhanced_analysis'] = {
                        'analysis': analysis,
                        'processing_timestamp': datetime.now().isoformat()
                    }
                    
                    # Also save to individual file
                    output_file = self.enhanced_dir / f"{candidate_id}_enhanced.json"
                    with open(output_file, 'w') as f:
                        json.dump({
                            'candidate_id': candidate_id,
                            'name': candidate.get('name'),
                            'enhanced_analysis': analysis,
                            'timestamp': datetime.now().isoformat()
                        }, f, indent=2)
                    
                    batch_processed += 1
                    print(" ✅")
                else:
                    batch_failed += 1
                    print(" ❌")
                
                # Brief pause every 5 candidates
                if j % 5 == 4:
                    time.sleep(1)
            
            # Update totals
            total_processed += batch_processed
            total_failed += batch_failed
            
            # Save progress after each batch
            if batch_processed > 0:
                self.save_nas_data(candidates)
                print(f"  ✓ Batch complete: {batch_processed} processed, {batch_failed} failed")
                print("  💾 Database updated")
            
            # Remove processed candidates from unprocessed list
            unprocessed = unprocessed[len(batch):]
            
            # Show progress
            progress_pct = ((initial_unprocessed - len(unprocessed)) / initial_unprocessed) * 100
            enhanced_count = sum(1 for c in candidates if c.get('enhanced_analysis'))
            print(f"  📊 Overall progress: {progress_pct:.1f}% | Enhanced candidates: {enhanced_count}/{total_candidates}")
            
            # Estimate time remaining
            if total_processed > 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                avg_time = elapsed / total_processed
                eta_seconds = len(unprocessed) * avg_time
                eta_minutes = eta_seconds / 60
                if eta_minutes > 60:
                    eta_hours = eta_minutes / 60
                    print(f"  ⏱️ Estimated time remaining: {eta_hours:.1f} hours")
                else:
                    print(f"  ⏱️ Estimated time remaining: {eta_minutes:.1f} minutes")
            
            # Brief pause between batches
            if unprocessed:
                print("  ⏸️ Pausing before next batch...")
                time.sleep(3)
        
        # Final report
        elapsed = (datetime.now() - start_time).total_seconds()
        final_enhanced = sum(1 for c in candidates if c.get('enhanced_analysis'))
        
        print("\n" + "=" * 60)
        print("🎉 ALL PROCESSING COMPLETE!")
        print(f"📊 Total processed: {total_processed}")
        print(f"❌ Total failed: {total_failed}")
        print(f"✅ Success rate: {(total_processed/(total_processed+total_failed)*100):.1f}%")
        print(f"📈 Total enhanced candidates: {final_enhanced}/{total_candidates}")
        print(f"⏱️ Total time: {elapsed/60:.1f} minutes")
        if total_processed > 0:
            print(f"📈 Average time per candidate: {elapsed/total_processed:.1f} seconds")
        print(f"💾 All results saved to: {self.enhanced_dir}/")

def main():
    processor = CompleteBatchProcessor()
    processor.process_all()

if __name__ == "__main__":
    main()