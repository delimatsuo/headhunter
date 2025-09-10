#!/usr/bin/env python3
"""
Process candidates from NAS database and update with enhanced analysis
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

class NASProcessor:
    def __init__(self):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("enhanced_analysis")
        self.enhanced_dir.mkdir(exist_ok=True)
        
    def load_nas_data(self):
        """Load the NAS database"""
        print(f"📂 Loading NAS database...")
        with open(self.nas_file, 'r') as f:
            return json.load(f)
    
    def save_nas_data(self, data):
        """Save updated data back to NAS"""
        backup_file = self.nas_file.replace('.json', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        print(f"💾 Creating backup: {backup_file}")
        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Updating NAS database...")
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
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def process_batch(self, limit=50):
        """Process a batch of candidates and update NAS"""
        # Load data
        candidates = self.load_nas_data()
        print(f"📊 Total candidates: {len(candidates)}")
        
        # Find unprocessed candidates
        unprocessed = []
        for candidate in candidates:
            if not candidate.get('enhanced_analysis') and candidate.get('id'):
                unprocessed.append(candidate)
        
        print(f"📊 Unprocessed candidates: {len(unprocessed)}")
        
        if not unprocessed:
            print("✅ All candidates already processed!")
            return
        
        # Process batch
        batch = unprocessed[:limit]
        print(f"🔄 Processing {len(batch)} candidates...")
        
        processed_count = 0
        failed_count = 0
        
        for i, candidate in enumerate(batch):
            candidate_id = candidate.get('id')
            print(f"  [{i+1}/{len(batch)}] Processing {candidate_id}...", end="")
            
            # Create prompt
            prompt = self.create_enhanced_prompt(candidate)
            
            # Process with Ollama
            analysis = self.process_with_ollama(prompt)
            
            if analysis:
                # Update candidate in main list
                for j, c in enumerate(candidates):
                    if c.get('id') == candidate_id:
                        candidates[j]['enhanced_analysis'] = {
                            'analysis': analysis,
                            'processing_timestamp': datetime.now().isoformat()
                        }
                        break
                
                # Also save to individual file
                output_file = self.enhanced_dir / f"{candidate_id}_enhanced.json"
                with open(output_file, 'w') as f:
                    json.dump({
                        'candidate_id': candidate_id,
                        'name': candidate.get('name'),
                        'enhanced_analysis': analysis,
                        'timestamp': datetime.now().isoformat()
                    }, f, indent=2)
                
                processed_count += 1
                print(" ✅")
            else:
                failed_count += 1
                print(" ❌")
            
            # Brief pause to avoid overload
            if i % 5 == 4:
                time.sleep(1)
        
        # Save updated data back to NAS
        if processed_count > 0:
            self.save_nas_data(candidates)
            print(f"\n✅ Successfully processed {processed_count} candidates")
            print(f"❌ Failed: {failed_count}")
            print(f"💾 NAS database updated!")
        else:
            print("\n⚠️ No candidates were successfully processed")
        
        # Show current stats
        total_with_analysis = sum(1 for c in candidates if c.get('enhanced_analysis'))
        print(f"\n📊 Total candidates with enhanced analysis: {total_with_analysis}/{len(candidates)}")

def main():
    processor = NASProcessor()
    processor.process_batch(limit=100)  # Process 100 candidates

if __name__ == "__main__":
    main()