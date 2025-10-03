#!/usr/bin/env python3
"""
Enhanced Processor with FULL candidate data analysis
Processes ALL candidates with complete information
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

class EnhancedFullProcessor:
    def __init__(self):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.enhanced_dir.mkdir(exist_ok=True)
        self.batch_size = 50  # Smaller batches for better quality
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
    
    def create_comprehensive_prompt(self, candidate: Dict[str, Any]) -> str:
        """Create comprehensive prompt with ALL candidate data"""
        name = candidate.get('name', 'Unknown')
        email = candidate.get('email', '')
        headline = candidate.get('headline', '')
        summary = candidate.get('summary', '')
        
        # Format education
        education = candidate.get('education', '')
        if not education or education == '':
            education = "No education information available"
        
        # Format experience with details
        experience = candidate.get('experience', '')
        if not experience or experience == '':
            experience = "No work experience information available"
        
        # Format skills
        skills = candidate.get('skills', '')
        if not skills or skills == '':
            skills = "No specific skills listed"
        
        # Format comments
        comments = candidate.get('comments', [])
        comment_text = ""
        if comments:
            comment_text = "\n\nRecruiter Notes:\n"
            for comment in comments:
                text = comment.get('text', '')
                author = comment.get('author', '')
                date = comment.get('date', '')
                if text:
                    comment_text += f"- {text}\n"
        else:
            comment_text = "\n\nNo recruiter comments available"
        
        # Build comprehensive prompt
        prompt = f"""Analyze this candidate's COMPLETE profile and provide a detailed JSON assessment:

CANDIDATE PROFILE:
==================
Name: {name}
Email: {email if email else 'Not provided'}
Headline: {headline if headline else 'Not provided'}

PROFESSIONAL SUMMARY:
{summary if summary else 'No summary provided'}

EDUCATION:
{education}

WORK EXPERIENCE:
{experience}

SKILLS:
{skills}

RECRUITER NOTES:
{comment_text}

Based on ALL the above information, provide a comprehensive JSON analysis. Analyze the actual career progression, companies worked at, roles held, education background, and skills listed. 

Return ONLY valid JSON with these fields filled based on the ACTUAL DATA above:
{{
  "career_trajectory": {{
    "current_level": "Junior/Mid/Senior/Principal/Executive",
    "progression_speed": "slow/steady/fast",
    "trajectory_type": "individual_contributor/technical_leadership/people_management",
    "years_experience": <calculate from experience dates>,
    "velocity": "accelerating/steady/plateauing"
  }},
  "leadership_scope": {{
    "has_leadership": <true if titles show management>,
    "team_size": <estimate from titles>,
    "leadership_level": "none/lead/manager/director/vp/c-level",
    "leadership_style": "collaborative/directive/coaching/servant"
  }},
  "company_pedigree": {{
    "company_tier": "startup/mid_market/enterprise/faang",
    "company_tiers": <list companies by tier>,
    "stability_pattern": "job_hopper/stable/very_stable"
  }},
  "cultural_signals": {{
    "strengths": <based on experience and education>,
    "red_flags": <from comments and job history>,
    "work_style": "independent/collaborative/hybrid"
  }},
  "skill_assessment": {{
    "technical_skills": {{
      "core_competencies": <extract from skills and experience>,
      "skill_depth": "beginner/intermediate/advanced/expert"
    }},
    "soft_skills": {{
      "communication": "developing/strong/exceptional",
      "leadership": "developing/strong/exceptional"
    }}
  }},
  "recruiter_insights": {{
    "placement_likelihood": "low/medium/high",
    "best_fit_roles": <based on experience>,
    "salary_expectations": "below_market/market/above_market",
    "availability": "immediate/short_notice/not_looking"
  }},
  "search_optimization": {{
    "keywords": <extract key terms from profile>,
    "search_tags": <categorize skills and experience>
  }},
  "executive_summary": {{
    "one_line_pitch": <create compelling summary>,
    "ideal_next_role": <based on progression>,
    "overall_rating": <1-100 score>
  }}
}}

IMPORTANT: Base your analysis on the ACTUAL DATA provided above, not generic assumptions."""
        
        return prompt
    
    def process_with_ollama(self, prompt: str, retry_count: int = 0) -> Optional[Dict[str, Any]]:
        """Process with Ollama with retry logic"""
        try:
            result = subprocess.run(
                ['ollama', 'run', 'llama3.1:8b', prompt],
                capture_output=True,
                text=True,
                timeout=90  # Longer timeout for detailed analysis
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
                analysis = json.loads(json_str)
                
                # Validate the response has actual content
                if analysis.get('career_trajectory', {}).get('years_experience') is not None:
                    return analysis
                else:
                    print("    ⚠️ Incomplete analysis, retrying...")
                    if retry_count < self.max_retries:
                        time.sleep(2)
                        return self.process_with_ollama(prompt, retry_count + 1)
                    return None
            
            return None
            
        except subprocess.TimeoutExpired:
            print("    ⏱️ Timeout, retrying...")
            if retry_count < self.max_retries:
                time.sleep(2)
                return self.process_with_ollama(prompt, retry_count + 1)
            return None
        except json.JSONDecodeError as e:
            print(f"    ❌ JSON Error: {e}")
            if retry_count < self.max_retries:
                time.sleep(2)
                return self.process_with_ollama(prompt, retry_count + 1)
            return None
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return None
    
    def process_all(self):
        """Process ALL candidates with full data"""
        start_time = datetime.now()
        
        # Load data
        candidates = self.load_nas_data()
        total_candidates = len(candidates)
        print(f"📊 Total candidates: {total_candidates}")
        
        # Find unprocessed or poorly processed candidates
        needs_processing = []
        for i, candidate in enumerate(candidates):
            # Check if needs processing
            enhanced = candidate.get('enhanced_analysis', {})
            analysis = enhanced.get('analysis', {})
            
            # Process if:
            # 1. No enhanced analysis at all
            # 2. Has null values in critical fields
            # 3. Has empty strings in critical fields
            needs_reprocess = False
            
            if not enhanced:
                needs_reprocess = True
            elif analysis:
                # Check for poor quality analysis
                trajectory = analysis.get('career_trajectory', {})
                if (trajectory.get('years_experience') is None or 
                    trajectory.get('current_level') in [None, '', 'Unknown'] or
                    not analysis.get('skill_assessment', {}).get('technical_skills', {}).get('core_competencies')):
                    needs_reprocess = True
            
            if needs_reprocess and candidate.get('id'):
                needs_processing.append((i, candidate))
        
        initial_count = len(needs_processing)
        print(f"📊 Candidates needing full analysis: {initial_count}")
        
        if not needs_processing:
            print("✅ All candidates have quality analysis!")
            return
        
        total_processed = 0
        total_failed = 0
        batch_num = 0
        
        print(f"\n🚀 Starting comprehensive analysis of {initial_count} candidates")
        print("=" * 60)
        
        while needs_processing:
            batch_num += 1
            batch = needs_processing[:self.batch_size]
            remaining = len(needs_processing)
            
            print(f"\n📦 Batch {batch_num} - Processing {len(batch)} candidates ({remaining} remaining)")
            
            batch_processed = 0
            batch_failed = 0
            
            for j, (idx, candidate) in enumerate(batch):
                candidate_id = candidate.get('id')
                candidate_name = candidate.get('name', 'Unknown')
                has_experience = bool(candidate.get('experience'))
                has_education = bool(candidate.get('education'))
                
                print(f"  [{j+1}/{len(batch)}] {candidate_name} (ID: {candidate_id})")
                print(f"      📋 Has experience: {has_experience}, Has education: {has_education}")
                
                # Create comprehensive prompt with all data
                prompt = self.create_comprehensive_prompt(candidate)
                
                # Process with Ollama
                print("      🤖 Analyzing...", end="")
                analysis = self.process_with_ollama(prompt)
                
                if analysis:
                    # Update candidate in main list
                    candidates[idx]['enhanced_analysis'] = {
                        'analysis': analysis,
                        'processing_timestamp': datetime.now().isoformat(),
                        'processor_version': 'full_v2'
                    }
                    
                    # Save to individual file
                    output_file = self.enhanced_dir / f"{candidate_id}_enhanced.json"
                    with open(output_file, 'w') as f:
                        json.dump({
                            'candidate_id': candidate_id,
                            'name': candidate_name,
                            'has_experience': has_experience,
                            'has_education': has_education,
                            'enhanced_analysis': analysis,
                            'timestamp': datetime.now().isoformat()
                        }, f, indent=2)
                    
                    batch_processed += 1
                    print(" ✅")
                    
                    # Show sample of analysis quality
                    years = analysis.get('career_trajectory', {}).get('years_experience')
                    level = analysis.get('career_trajectory', {}).get('current_level')
                    skills = len(analysis.get('skill_assessment', {}).get('technical_skills', {}).get('core_competencies', []))
                    print(f"      📊 Years: {years}, Level: {level}, Skills: {skills}")
                else:
                    batch_failed += 1
                    print(" ❌")
                
                # Brief pause every 3 candidates
                if j % 3 == 2:
                    time.sleep(1)
            
            # Update totals
            total_processed += batch_processed
            total_failed += batch_failed
            
            # Save progress after each batch
            if batch_processed > 0:
                self.save_nas_data(candidates)
                print(f"\n  ✓ Batch complete: {batch_processed} processed, {batch_failed} failed")
                print("  💾 Database updated")
            
            # Remove processed candidates
            needs_processing = needs_processing[len(batch):]
            
            # Show progress
            progress_pct = ((initial_count - len(needs_processing)) / initial_count) * 100
            enhanced_count = sum(1 for c in candidates if c.get('enhanced_analysis'))
            print(f"  📊 Progress: {progress_pct:.1f}% | Total with analysis: {enhanced_count}/{total_candidates}")
            
            # Estimate time remaining
            if total_processed > 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                avg_time = elapsed / total_processed
                eta_seconds = len(needs_processing) * avg_time
                eta_minutes = eta_seconds / 60
                if eta_minutes > 60:
                    eta_hours = eta_minutes / 60
                    print(f"  ⏱️ ETA: {eta_hours:.1f} hours")
                else:
                    print(f"  ⏱️ ETA: {eta_minutes:.1f} minutes")
            
            # Pause between batches
            if needs_processing:
                print("  ⏸️ Pausing before next batch...")
                time.sleep(3)
        
        # Final report
        elapsed = (datetime.now() - start_time).total_seconds()
        final_enhanced = sum(1 for c in candidates if c.get('enhanced_analysis'))
        
        print("\n" + "=" * 60)
        print("🎉 COMPREHENSIVE PROCESSING COMPLETE!")
        print(f"📊 Processed with full data: {total_processed}")
        print(f"❌ Failed: {total_failed}")
        print(f"✅ Success rate: {(total_processed/(total_processed+total_failed)*100 if (total_processed+total_failed) > 0 else 0):.1f}%")
        print(f"📈 Total candidates with analysis: {final_enhanced}/{total_candidates}")
        print(f"⏱️ Total time: {elapsed/60:.1f} minutes")
        if total_processed > 0:
            print(f"📈 Avg time per candidate: {elapsed/total_processed:.1f} seconds")
        print(f"💾 Results saved to: {self.enhanced_dir}/")

def main():
    processor = EnhancedFullProcessor()
    processor.process_all()

if __name__ == "__main__":
    main()