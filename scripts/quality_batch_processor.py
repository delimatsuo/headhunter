#!/usr/bin/env python3
"""
Quality Batch Processor - Process 100 candidates with comprehensive analysis
Focus on quality over speed with detailed metrics
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import re
import psutil

class QualityBatchProcessor:
    def __init__(self, batch_size=100):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.enhanced_dir.mkdir(exist_ok=True)
        
        # Quality settings
        self.batch_size = batch_size
        self.max_retries = 2
        self.ollama_timeout = 120  # 2 minutes per candidate for quality
        
        # Metrics
        self.start_time = None
        self.end_time = None
        self.processed_count = 0
        self.failed_count = 0
        self.file_sizes = []
        self.processing_times = []
        
        print("🎯 QUALITY BATCH PROCESSOR")
        print("=" * 60)
        print(f"📦 Batch Size: {self.batch_size} candidates")
        print(f"⏱️ Timeout: {self.ollama_timeout}s per candidate")
        print(f"🔄 Max Retries: {self.max_retries}")
        print(f"📁 Output: {self.enhanced_dir}")
        print()
        
    def create_comprehensive_prompt(self, candidate: Dict) -> str:
        """Create a detailed prompt for comprehensive analysis"""
        name = candidate.get('name', 'Unknown')
        education = candidate.get('education', [])
        experience = candidate.get('experience', [])
        skills = candidate.get('skills', [])
        
        # Convert lists to readable format
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
        """Process with Ollama and get JSON response"""
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
                    # Extract JSON from response
                    response_text = result.stdout.strip()
                    
                    # Try to find JSON in the response
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        try:
                            parsed = json.loads(json_match.group())
                            # Validate that we got substantial content
                            if len(json.dumps(parsed)) > 500:  # Ensure meaningful response
                                return parsed
                            else:
                                print(f"    ⚠️ Response too short ({len(json.dumps(parsed))} bytes), retrying...")
                        except json.JSONDecodeError as e:
                            print(f"    ⚠️ JSON parse error: {e}, retrying...")
                
            except subprocess.TimeoutExpired:
                print(f"    ⏱️ Timeout on attempt {attempt + 1}")
            except Exception as e:
                print(f"    ❌ Error on attempt {attempt + 1}: {e}")
        
        return None
    
    def process_batch(self):
        """Process a batch of candidates with detailed metrics"""
        print("📊 Loading candidate database...")
        with open(self.nas_file, 'r') as f:
            all_candidates = json.load(f)
        
        total_available = len(all_candidates)
        print(f"📊 Total candidates available: {total_available}")
        
        # Take first batch_size candidates
        candidates_to_process = all_candidates[:self.batch_size]
        print(f"📋 Processing first {len(candidates_to_process)} candidates\n")
        
        self.start_time = datetime.now()
        print(f"⏰ Start time: {self.start_time.strftime('%I:%M:%S %p')}")
        print("=" * 60)
        
        for i, candidate in enumerate(candidates_to_process, 1):
            candidate_start = time.time()
            
            candidate_id = candidate.get('id', f'unknown_{i}')
            candidate_name = candidate.get('name', 'Unknown')
            
            print(f"\n[{i}/{self.batch_size}] Processing: {candidate_name} (ID: {candidate_id})")
            
            # Skip if no meaningful data
            if not candidate.get('education') and not candidate.get('experience'):
                print("    ⏭️ Skipped - No education or experience data")
                continue
            
            # Create comprehensive prompt
            prompt = self.create_comprehensive_prompt(candidate)
            
            # Process with Ollama
            print("    🤖 Sending to LLM...")
            analysis = self.process_with_ollama(prompt)
            
            if analysis:
                # Save to file
                safe_name = re.sub(r'[^\w\s-]', '', candidate_name).strip().replace(' ', '_')[:50]
                output_file = self.enhanced_dir / f"{candidate_id}_{safe_name}_enhanced.json"
                
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
                            'processor': 'quality_batch_processor',
                            'llm_model': 'llama3.1:8b',
                            'processing_time': time.time() - candidate_start
                        }
                    }
                    
                    with open(output_file, 'w') as f:
                        json.dump(output_data, f, indent=2)
                    
                    file_size = output_file.stat().st_size
                    self.file_sizes.append(file_size)
                    self.processing_times.append(time.time() - candidate_start)
                    self.processed_count += 1
                    
                    print(f"    ✅ Success! File size: {file_size:,} bytes")
                    print(f"    ⏱️ Processing time: {time.time() - candidate_start:.1f}s")
                    
                except Exception as e:
                    print(f"    ❌ Failed to save: {e}")
                    self.failed_count += 1
            else:
                print("    ❌ LLM processing failed")
                self.failed_count += 1
                
            # Progress update every 10 candidates
            if i % 10 == 0:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                rate = i / (elapsed / 60) if elapsed > 0 else 0
                print(f"\n📊 Progress: {i}/{self.batch_size} | Rate: {rate:.1f}/min | Success: {self.processed_count}")
        
        self.end_time = datetime.now()
        self.print_final_report()
    
    def print_final_report(self):
        """Print comprehensive metrics report"""
        duration = (self.end_time - self.start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print("📊 FINAL REPORT")
        print("=" * 60)
        
        print("\n⏰ TIMING:")
        print(f"  Start: {self.start_time.strftime('%I:%M:%S %p')}")
        print(f"  End: {self.end_time.strftime('%I:%M:%S %p')}")
        print(f"  Total Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        
        print("\n📈 PROCESSING METRICS:")
        print(f"  Attempted: {self.batch_size}")
        print(f"  Successful: {self.processed_count}")
        print(f"  Failed: {self.failed_count}")
        print(f"  Success Rate: {100*self.processed_count/self.batch_size:.1f}%")
        
        if self.processing_times:
            avg_time = sum(self.processing_times) / len(self.processing_times)
            print("\n⚡ PERFORMANCE:")
            print(f"  Avg Time per Candidate: {avg_time:.1f}s")
            print(f"  Processing Rate: {60/avg_time:.1f} candidates/minute")
            print(f"  Estimated for 29,138: {29138*avg_time/3600:.1f} hours")
        
        if self.file_sizes:
            avg_size = sum(self.file_sizes) / len(self.file_sizes)
            print("\n📁 FILE QUALITY:")
            print(f"  Avg File Size: {avg_size:,.0f} bytes")
            print(f"  Min File Size: {min(self.file_sizes):,} bytes")
            print(f"  Max File Size: {max(self.file_sizes):,} bytes")
            
            # Quality assessment
            good_files = sum(1 for s in self.file_sizes if s > 2000)
            print(f"  Files >2KB (good quality): {good_files}/{len(self.file_sizes)}")
        
        print("\n💻 SYSTEM RESOURCES:")
        print(f"  CPU Usage: {psutil.cpu_percent()}%")
        print(f"  Memory Usage: {psutil.virtual_memory().percent}%")
        
        # Save metrics to file
        metrics_file = Path("quality_batch_metrics.json")
        with open(metrics_file, 'w') as f:
            json.dump({
                'batch_size': self.batch_size,
                'processed': self.processed_count,
                'failed': self.failed_count,
                'duration_seconds': duration,
                'avg_time_per_candidate': avg_time if self.processing_times else 0,
                'avg_file_size': avg_size if self.file_sizes else 0,
                'file_sizes': self.file_sizes,
                'processing_times': self.processing_times,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"\n💾 Metrics saved to: {metrics_file}")
        print("=" * 60)

if __name__ == "__main__":
    processor = QualityBatchProcessor(batch_size=100)
    processor.process_batch()