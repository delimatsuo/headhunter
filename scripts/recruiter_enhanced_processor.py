#!/usr/bin/env python3
"""
Recruiter-Enhanced Processor with Deep Resume Analysis
Extracts ALL resume details and enriches with industry knowledge
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import re

class RecruiterEnhancedProcessor:
    def __init__(self):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.enhanced_dir.mkdir(exist_ok=True)
        self.batch_size = 20  # Process 20 for quality review
        self.max_retries = 3
        
    def load_nas_data(self):
        """Load the NAS database"""
        print(f"📂 Loading NAS database...")
        with open(self.nas_file, 'r') as f:
            return json.load(f)
    
    def save_nas_data(self, data):
        """Save updated data back to NAS with backup"""
        backup_file = self.nas_file.replace('.json', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        print(f"💾 Creating backup: {backup_file}")
        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Updating NAS database...")
        with open(self.nas_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def parse_education(self, education_text: str) -> List[Dict]:
        """Parse education text into structured format"""
        if not education_text or education_text == '':
            return []
        
        education_list = []
        lines = education_text.strip().split('\n')
        
        current_edu = {}
        for line in lines:
            line = line.strip()
            if not line or line == '-':
                continue
                
            # Check for date pattern
            date_pattern = r'(\d{4}/\d{2})\s*-\s*(\d{4}/\d{2})?'
            date_match = re.search(date_pattern, line)
            
            if date_match:
                if current_edu:
                    education_list.append(current_edu)
                current_edu = {
                    'start_date': date_match.group(1),
                    'end_date': date_match.group(2) if date_match.group(2) else 'Present'
                }
            elif line.startswith('-'):
                # This is likely a school or degree line
                clean_line = line.lstrip('- ').strip()
                if 'institution' not in current_edu and clean_line:
                    current_edu['institution'] = clean_line
                elif 'degree' not in current_edu and clean_line:
                    current_edu['degree'] = clean_line
            else:
                # Could be institution or degree
                if 'institution' not in current_edu:
                    current_edu['institution'] = line
                elif 'degree' not in current_edu:
                    current_edu['degree'] = line
                elif 'field' not in current_edu:
                    current_edu['field'] = line
        
        if current_edu:
            education_list.append(current_edu)
        
        return education_list
    
    def parse_experience(self, experience_text: str) -> List[Dict]:
        """Parse experience text into structured format"""
        if not experience_text or experience_text == '':
            return []
        
        experience_list = []
        lines = experience_text.strip().split('\n')
        
        current_exp = {}
        for line in lines:
            line = line.strip()
            if not line or line == '-':
                continue
            
            # Check for date pattern
            date_pattern = r'(\d{4}/\d{2})\s*-\s*(\d{4}/\d{2})?'
            date_match = re.search(date_pattern, line)
            
            if date_match:
                if current_exp:
                    experience_list.append(current_exp)
                current_exp = {
                    'start_date': date_match.group(1),
                    'end_date': date_match.group(2) if date_match.group(2) else 'Present'
                }
            elif ':' in line:
                # Company : Position format
                parts = line.split(':', 1)
                if len(parts) == 2:
                    company = parts[0].strip().lstrip('- ')
                    position = parts[1].strip()
                    if company:
                        current_exp['company'] = company
                    if position:
                        current_exp['position'] = position
            elif line.startswith('-'):
                clean_line = line.lstrip('- ').strip()
                if 'company' not in current_exp and clean_line:
                    current_exp['company'] = clean_line
                elif 'position' not in current_exp and clean_line:
                    current_exp['position'] = clean_line
        
        if current_exp:
            experience_list.append(current_exp)
        
        return experience_list
    
    def calculate_years_experience(self, experience_list: List[Dict]) -> float:
        """Calculate total years of experience"""
        total_months = 0
        
        for exp in experience_list:
            start = exp.get('start_date', '')
            end = exp.get('end_date', '')
            
            if start:
                try:
                    start_year, start_month = map(int, start.split('/'))
                    
                    if end and end != 'Present':
                        end_year, end_month = map(int, end.split('/'))
                    else:
                        # Current date
                        end_year = 2025
                        end_month = 9
                    
                    months = (end_year - start_year) * 12 + (end_month - start_month)
                    total_months += max(0, months)
                except:
                    continue
        
        return round(total_months / 12, 1)
    
    def create_recruiter_prompt(self, candidate: Dict[str, Any]) -> str:
        """Create comprehensive prompt for recruiter-level analysis"""
        name = candidate.get('name', 'Unknown')
        email = candidate.get('email', '')
        headline = candidate.get('headline', '')
        summary = candidate.get('summary', '')
        
        # Parse structured data
        education_raw = candidate.get('education', '')
        experience_raw = candidate.get('experience', '')
        skills_raw = candidate.get('skills', '')
        
        education_list = self.parse_education(education_raw)
        experience_list = self.parse_experience(experience_raw)
        years_exp = self.calculate_years_experience(experience_list)
        
        # Format education for prompt
        education_text = "EDUCATION DETAILS:\n"
        if education_list:
            for edu in education_list:
                education_text += f"• {edu.get('institution', 'Unknown School')}\n"
                education_text += f"  Degree: {edu.get('degree', 'N/A')}\n"
                education_text += f"  Field: {edu.get('field', 'N/A')}\n"
                education_text += f"  Period: {edu.get('start_date', 'N/A')} - {edu.get('end_date', 'N/A')}\n\n"
        else:
            education_text += "No formal education listed\n"
        
        # Format experience for prompt
        experience_text = "PROFESSIONAL EXPERIENCE:\n"
        if experience_list:
            for exp in experience_list:
                experience_text += f"• {exp.get('company', 'Unknown Company')}\n"
                experience_text += f"  Position: {exp.get('position', 'N/A')}\n"
                experience_text += f"  Period: {exp.get('start_date', 'N/A')} - {exp.get('end_date', 'N/A')}\n\n"
        else:
            experience_text += "No work experience listed\n"
        
        # Format skills
        skills_text = "TECHNICAL SKILLS:\n"
        if skills_raw:
            skills_text += skills_raw
        else:
            skills_text += "No specific skills listed\n"
        
        # Format comments
        comments = candidate.get('comments', [])
        comment_text = "\nRECRUITER NOTES AND OBSERVATIONS:\n"
        if comments:
            for comment in comments[-5:]:  # Last 5 comments
                text = comment.get('text', '')
                if text:
                    comment_text += f"• {text}\n"
        else:
            comment_text += "No recruiter notes available\n"
        
        prompt = f"""You are an expert technical recruiter analyzing a candidate's complete profile. 
Provide a COMPREHENSIVE analysis that a recruiter would create after reviewing the full resume.

CANDIDATE: {name}
EMAIL: {email if email else 'Not provided'}
HEADLINE: {headline if headline else 'Not provided'}
CALCULATED EXPERIENCE: {years_exp} years

PROFESSIONAL SUMMARY:
{summary if summary else 'No summary provided'}

{education_text}

{experience_text}

{skills_text}

{comment_text}

Based on this candidate's COMPLETE profile, provide a detailed recruiter analysis. 
Include insights about:
1. The actual companies they worked at (use your knowledge about these companies - size, culture, tech stack)
2. Their actual education (specific schools, degrees, and what that tells us)
3. Career progression patterns and red flags
4. Technical depth based on roles and companies
5. Market positioning and compensation expectations
6. Cultural fit indicators

Return ONLY valid JSON with these comprehensive fields:

{{
  "personal_details": {{
    "full_name": "{name}",
    "email": "{email if email else 'not_provided'}",
    "location": "extract from profile or infer from companies",
    "linkedin_headline": "{headline if headline else 'none'}"
  }},
  "education_analysis": {{
    "degrees": [
      {{
        "institution": "exact school name",
        "institution_tier": "top_tier/mid_tier/standard/unknown",
        "degree_type": "Bachelor's/Master's/PhD/Certificate",
        "field_of_study": "specific field",
        "graduation_year": "year or estimated",
        "relevance_to_tech": "high/medium/low"
      }}
    ],
    "education_quality": "ivy_league/top_tier/good/standard/limited",
    "continuous_learning": "certifications or ongoing education indicators"
  }},
  "experience_analysis": {{
    "total_years": {years_exp},
    "companies_worked": [
      {{
        "company_name": "exact company name",
        "company_type": "FAANG/unicorn/startup/enterprise/consultancy/unknown",
        "company_size": "estimate employees",
        "company_reputation": "excellent/good/standard/poor/unknown",
        "role": "exact title",
        "seniority_level": "junior/mid/senior/lead/principal/staff",
        "duration_months": "calculate",
        "tech_stack_used": ["likely technologies based on company and role"]
      }}
    ],
    "career_progression": {{
      "trajectory": "upward/lateral/mixed/declining",
      "promotion_velocity": "fast/normal/slow",
      "job_stability": "very_stable/stable/moderate/job_hopper",
      "average_tenure_months": "calculate"
    }}
  }},
  "technical_assessment": {{
    "primary_skills": ["list main technical skills"],
    "secondary_skills": ["supporting skills"],
    "skill_depth": {{
      "frontend": "none/basic/intermediate/advanced/expert",
      "backend": "none/basic/intermediate/advanced/expert",
      "mobile": "none/basic/intermediate/advanced/expert",
      "devops": "none/basic/intermediate/advanced/expert",
      "data": "none/basic/intermediate/advanced/expert",
      "ai_ml": "none/basic/intermediate/advanced/expert"
    }},
    "technology_categories": ["web/mobile/cloud/data/ai/embedded"],
    "years_with_primary_skill": "estimate based on roles"
  }},
  "market_insights": {{
    "current_market_value": {{
      "seniority_bracket": "junior/mid/senior/staff/principal",
      "estimated_salary_range": "provide realistic range based on experience and location",
      "market_demand": "very_high/high/moderate/low",
      "competing_offers_likelihood": "high/medium/low"
    }},
    "best_fit_companies": ["list 3-5 company types that would be good matches"],
    "ideal_next_role": "specific role recommendation",
    "career_growth_potential": "high/medium/low"
  }},
  "cultural_assessment": {{
    "work_environment_preference": "startup/scaleup/enterprise/remote/hybrid",
    "team_collaboration_style": "independent/collaborative/leadership",
    "company_values_alignment": ["innovation/stability/growth/work-life-balance"],
    "red_flags": ["any concerns from job history or notes"],
    "green_flags": ["positive indicators"]
  }},
  "recruiter_recommendations": {{
    "placement_difficulty": "easy/moderate/challenging/very_challenging",
    "interview_readiness": "ready/needs_prep/significant_prep_required",
    "negotiation_leverage": "strong/moderate/weak",
    "urgency_to_place": "immediate/soon/no_rush",
    "commission_potential": "high/medium/low",
    "client_presentation_notes": "key points to highlight to clients"
  }},
  "searchability": {{
    "ats_keywords": ["keywords for applicant tracking systems"],
    "boolean_search_terms": ["terms for Boolean searches"],
    "skill_synonyms": ["alternative terms for their skills"],
    "competitor_companies": ["companies they might come from or go to"]
  }},
  "enriched_insights": {{
    "industry_context": "current state of their industry/domain",
    "technology_trends": "how their skills align with current trends",
    "geographic_factors": "location-based insights",
    "diversity_indicators": "any diversity/inclusion relevant factors",
    "security_clearance": "if applicable or inferrable"
  }},
  "executive_summary": {{
    "one_line_pitch": "compelling 1-line summary for client presentation",
    "strengths": ["top 3 strengths"],
    "development_areas": ["areas for growth"],
    "overall_rating": "score 1-100",
    "placement_strategy": "recommended approach for placing this candidate"
  }}
}}

IMPORTANT: Base ALL analysis on the ACTUAL data provided. Use your knowledge about the companies, schools, and technologies mentioned to provide rich context."""
        
        return prompt
    
    def process_with_ollama(self, prompt: str, retry_count: int = 0) -> Optional[Dict[str, Any]]:
        """Process with Ollama with retry logic"""
        try:
            result = subprocess.run(
                ['ollama', 'run', 'llama3.1:8b', prompt],
                capture_output=True,
                text=True,
                timeout=120  # Longer timeout for detailed analysis
            )
            
            if result.returncode != 0:
                if retry_count < self.max_retries:
                    time.sleep(3)
                    return self.process_with_ollama(prompt, retry_count + 1)
                return None
            
            response = result.stdout.strip()
            
            # Extract JSON
            if '{' in response and '}' in response:
                start = response.index('{')
                end = response.rindex('}') + 1
                json_str = response[start:end]
                analysis = json.loads(json_str)
                
                # Validate that we have actual content
                if (analysis.get('personal_details') and 
                    analysis.get('education_analysis') and
                    analysis.get('experience_analysis')):
                    return analysis
                else:
                    print(f"    ⚠️ Incomplete analysis, retrying...")
                    if retry_count < self.max_retries:
                        time.sleep(3)
                        return self.process_with_ollama(prompt, retry_count + 1)
                    return None
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"    ⏱️ Timeout, retrying...")
            if retry_count < self.max_retries:
                time.sleep(3)
                return self.process_with_ollama(prompt, retry_count + 1)
            return None
        except json.JSONDecodeError as e:
            print(f"    ❌ JSON Error: {e}")
            if retry_count < self.max_retries:
                time.sleep(3)
                return self.process_with_ollama(prompt, retry_count + 1)
            return None
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return None
    
    def process_sample_batch(self):
        """Process 20 candidates for quality review"""
        start_time = datetime.now()
        
        # Load data
        candidates = self.load_nas_data()
        total_candidates = len(candidates)
        print(f"📊 Total candidates in database: {total_candidates}")
        
        # Find candidates with good data to process
        good_candidates = []
        for i, candidate in enumerate(candidates):
            # Skip if already processed
            if candidate.get('recruiter_enhanced_analysis'):
                continue
                
            # Check if has meaningful data
            has_experience = bool(candidate.get('experience') and len(candidate.get('experience', '')) > 50)
            has_education = bool(candidate.get('education') and len(candidate.get('education', '')) > 20)
            has_name = bool(candidate.get('name'))
            
            if has_name and (has_experience or has_education):
                good_candidates.append((i, candidate))
                
            if len(good_candidates) >= 20:
                break
        
        if not good_candidates:
            print("❌ No suitable candidates found for processing")
            return
        
        print(f"\n🎯 Processing {len(good_candidates)} candidates with rich data for quality review")
        print("=" * 60)
        
        processed_count = 0
        failed_count = 0
        
        for j, (idx, candidate) in enumerate(good_candidates):
            candidate_id = candidate.get('id')
            candidate_name = candidate.get('name', 'Unknown')
            
            # Parse to check data quality
            education_list = self.parse_education(candidate.get('education', ''))
            experience_list = self.parse_experience(candidate.get('experience', ''))
            years_exp = self.calculate_years_experience(experience_list)
            
            print(f"\n[{j+1}/{len(good_candidates)}] {candidate_name} (ID: {candidate_id})")
            print(f"  📊 Data: {len(education_list)} education, {len(experience_list)} jobs, {years_exp} years exp")
            
            # Create comprehensive prompt
            prompt = self.create_recruiter_prompt(candidate)
            
            # Process with Ollama
            print(f"  🤖 Generating recruiter-level analysis...", end="")
            analysis = self.process_with_ollama(prompt)
            
            if analysis:
                # Update candidate in main list
                candidates[idx]['recruiter_enhanced_analysis'] = {
                    'analysis': analysis,
                    'processing_timestamp': datetime.now().isoformat(),
                    'processor_version': 'recruiter_v1'
                }
                
                # Save to individual file with rich filename
                safe_name = re.sub(r'[^\w\s-]', '', candidate_name).strip().replace(' ', '_')
                output_file = self.enhanced_dir / f"{candidate_id}_{safe_name}_recruiter_enhanced.json"
                
                with open(output_file, 'w') as f:
                    json.dump({
                        'candidate_id': candidate_id,
                        'name': candidate_name,
                        'original_data': {
                            'education': candidate.get('education', ''),
                            'experience': candidate.get('experience', ''),
                            'skills': candidate.get('skills', ''),
                            'summary': candidate.get('summary', '')
                        },
                        'parsed_data': {
                            'education_parsed': education_list,
                            'experience_parsed': experience_list,
                            'calculated_years': years_exp
                        },
                        'recruiter_analysis': analysis,
                        'timestamp': datetime.now().isoformat()
                    }, f, indent=2)
                
                processed_count += 1
                print(" ✅")
                
                # Show key insights
                if analysis.get('executive_summary'):
                    print(f"  💡 {analysis['executive_summary'].get('one_line_pitch', 'N/A')}")
                    print(f"  📈 Rating: {analysis['executive_summary'].get('overall_rating', 'N/A')}/100")
                
            else:
                failed_count += 1
                print(" ❌")
            
            # Brief pause between candidates
            time.sleep(2)
        
        # Save updated database
        if processed_count > 0:
            self.save_nas_data(candidates)
        
        # Final report
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print("📋 QUALITY REVIEW BATCH COMPLETE")
        print(f"✅ Successfully processed: {processed_count}")
        print(f"❌ Failed: {failed_count}")
        print(f"⏱️ Total time: {elapsed/60:.1f} minutes")
        print(f"📁 Files saved to: {self.enhanced_dir}/")
        print("\n🔍 Please review the generated files for quality before proceeding with full processing")

def main():
    processor = RecruiterEnhancedProcessor()
    processor.process_sample_batch()

if __name__ == "__main__":
    main()