#!/usr/bin/env python3
"""
Enhanced LLM processor that generates comprehensive candidate analysis 
matching the PRD requirements for Headhunter v1.1
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

# Constants
NAS_DIR = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project")
MERGED_FILE = NAS_DIR / "comprehensive_merged_candidates.json"
OUTPUT_DIR = NAS_DIR / "enhanced_analysis"

def create_enhanced_prompt(candidate):
    """Create comprehensive prompt matching PRD requirements"""
    
    # Gather all candidate data
    name = candidate.get('name', 'Unknown')
    email = candidate.get('email', 'N/A')
    headline = candidate.get('headline', 'N/A')
    summary = candidate.get('summary', 'N/A')
    skills = candidate.get('skills', 'N/A')
    education = candidate.get('education', 'N/A')
    experience = candidate.get('experience', 'N/A')
    
    # Process recruiter comments
    comments = candidate.get('comments', [])
    recruiter_notes = []
    for comment in comments[:5]:  # Top 5 most recent
        author = comment.get('author', 'Unknown')
        text = comment.get('text', '')
        date = comment.get('date', '')[:10]  # Just date part
        if text.strip():
            recruiter_notes.append(f"[{date}] {author}: {text[:200]}...")
    
    prompt = f"""You are an expert executive search consultant analyzing a candidate profile. Provide comprehensive analysis in the specified JSON format.

CANDIDATE PROFILE:
Name: {name}
Email: {email}
Current Title/Headline: {headline}
Professional Summary: {summary[:500]}
Skills: {skills[:300]}
Education: {education[:300]}
Experience: {experience[:500]}

RECRUITER INSIGHTS ({len(comments)} total comments):
{chr(10).join(recruiter_notes) if recruiter_notes else 'No recruiter comments available'}

ANALYSIS REQUIREMENTS:
Provide a detailed JSON analysis with these exact fields:

{{
  "career_trajectory": {{
    "progression_pattern": "describe career progression (linear/exponential/lateral/diverse)",
    "velocity": "career advancement speed (slow/steady/fast/accelerated)",
    "trajectory_type": "specialist/generalist/hybrid",
    "key_transitions": ["list major career transitions"],
    "growth_indicators": ["evidence of professional growth"]
  }},
  "leadership_scope": {{
    "management_experience": "years of people management experience",
    "team_sizes": ["ranges of team sizes managed"],
    "reporting_levels": "number of levels in reporting structure",
    "leadership_style": "identified leadership characteristics",
    "scale_of_responsibility": "scope of business impact"
  }},
  "company_pedigree": {{
    "company_tiers": ["tier classification of employers (Tier1/Tier2/Startup/Enterprise)"],
    "industry_experience": ["primary industries worked in"],
    "company_stages": ["startup/growth/mature company experience"],
    "brand_recognition": "level of employer brand strength",
    "career_context": "industry and company context analysis"
  }},
  "cultural_signals": {{
    "strengths": ["identified positive traits and behaviors"],
    "potential_red_flags": ["areas of concern or risk factors"],
    "work_style_indicators": ["communication, collaboration, work preferences"],
    "cultural_fit_factors": ["adaptability, values, team dynamics"],
    "motivation_drivers": ["what appears to motivate this candidate"]
  }},
  "skill_assessment": {{
    "technical_skills": {{
      "core_competencies": ["primary technical skills"],
      "proficiency_levels": {{"skill": "beginner/intermediate/advanced/expert"}},
      "emerging_skills": ["recently acquired or developing skills"],
      "skill_gaps": ["notable missing skills for their level"]
    }},
    "soft_skills": {{
      "communication": "assessment of communication abilities",
      "leadership": "leadership capability assessment", 
      "problem_solving": "analytical and problem-solving skills",
      "adaptability": "change management and learning agility",
      "collaboration": "teamwork and stakeholder management"
    }}
  }},
  "recruiter_insights": {{
    "synthesized_feedback": "summary of all recruiter comments and observations",
    "consistent_themes": ["recurring themes across recruiter notes"],
    "performance_indicators": ["evidence of strong/weak performance"],
    "client_feedback": "any client or interview feedback patterns",
    "placement_history": "success rate and placement context"
  }},
  "search_optimization": {{
    "recommended_roles": ["specific job titles this candidate would excel in"],
    "ideal_company_types": ["types of companies that would be best fit"],
    "compensation_range": "estimated salary range based on experience",
    "availability_signals": ["indicators of job search activity or openness"],
    "match_keywords": ["key terms that would surface this candidate in searches"]
  }},
  "executive_summary": {{
    "overall_rating": 8,
    "one_line_pitch": "compelling 1-sentence candidate summary",
    "key_differentiators": ["what makes this candidate unique"],
    "ideal_opportunity": "description of their perfect next role",
    "placement_confidence": "high/medium/low confidence in successful placement"
  }}
}}

Provide ONLY the JSON response with comprehensive analysis based on all available data:"""

    return prompt

def process_candidates_enhanced(limit=10):
    """Process candidates with enhanced LLM analysis matching PRD"""
    
    print("=" * 80)
    print("ENHANCED LLM PROCESSING - PRD COMPLIANT ANALYSIS")
    print("=" * 80)
    
    # Load candidates
    print("Loading candidate data...")
    with open(MERGED_FILE, 'r', encoding='utf-8') as f:
        all_candidates = json.load(f)
    
    # Get candidates with rich data (comments preferred)
    candidates_with_data = [c for c in all_candidates 
                           if c.get('data_status') != 'orphaned' 
                           and c.get('name')
                           and (c.get('comments') or c.get('experience') or c.get('summary'))]
    
    # Sort by comment count (most comments first)
    candidates_with_data.sort(key=lambda x: len(x.get('comments', [])), reverse=True)
    
    candidates = candidates_with_data[:limit]
    print(f"Selected {len(candidates)} candidates with rich data for processing")
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Process each candidate
    results = []
    successful = 0
    failed = 0
    total_start = time.time()
    
    for i, candidate in enumerate(candidates, 1):
        name = candidate.get('name', 'Unknown')
        cid = candidate.get('id')
        comment_count = len(candidate.get('comments', []))
        
        print(f"\n[{i:2d}/{len(candidates)}] Processing: {name[:40]}")
        print(f"          ID: {cid}")
        print(f"          Comments: {comment_count}")
        
        start_time = time.time()
        
        # Create enhanced prompt
        prompt = create_enhanced_prompt(candidate)
        
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,  # Lower temperature for more consistent output
                        "num_ctx": 8192,     # Larger context window
                        "num_predict": 4096  # Allow longer responses
                    }
                },
                timeout=120  # Longer timeout for complex analysis
            )
            
            if response.status_code == 200:
                result = response.json()
                processing_time = time.time() - start_time
                
                # Extract and parse JSON response
                llm_response = result.get('response', '')
                enhanced_analysis = None
                
                try:
                    # Extract JSON if wrapped in text
                    if '{' in llm_response and '}' in llm_response:
                        json_start = llm_response.find('{')
                        json_end = llm_response.rfind('}') + 1
                        json_text = llm_response[json_start:json_end]
                        enhanced_analysis = json.loads(json_text)
                        
                        print(f"          ✓ {processing_time:.2f}s")
                        
                        # Show key insights
                        if enhanced_analysis:
                            rating = enhanced_analysis.get('executive_summary', {}).get('overall_rating', 'N/A')
                            pitch = enhanced_analysis.get('executive_summary', {}).get('one_line_pitch', 'N/A')
                            trajectory = enhanced_analysis.get('career_trajectory', {}).get('progression_pattern', 'N/A')
                            
                            print(f"          Rating: {rating}/10")
                            print(f"          Pitch: {pitch[:60]}...")
                            print(f"          Trajectory: {trajectory}")
                            
                    else:
                        print("          ⚠ No JSON found in response")
                        enhanced_analysis = {'parsing_error': llm_response[:200]}
                        
                except json.JSONDecodeError as e:
                    print(f"          ⚠ JSON parsing failed: {e}")
                    enhanced_analysis = {'json_error': str(e), 'raw_response': llm_response[:300]}
                
                # Store result
                results.append({
                    'candidate_id': cid,
                    'name': name,
                    'processing_time': round(processing_time, 2),
                    'enhanced_analysis': enhanced_analysis,
                    'comments_count': comment_count,
                    'status': 'success'
                })
                
                successful += 1
                
            else:
                failed += 1
                print(f"          ✗ HTTP {response.status_code}")
                results.append({
                    'candidate_id': cid,
                    'name': name,
                    'processing_time': time.time() - start_time,
                    'enhanced_analysis': {'error': f'HTTP {response.status_code}'},
                    'status': 'failed'
                })
                
        except Exception as e:
            failed += 1
            processing_time = time.time() - start_time
            print(f"          ✗ Error: {e}")
            
            results.append({
                'candidate_id': cid,
                'name': name,
                'processing_time': round(processing_time, 2),
                'enhanced_analysis': {'error': str(e)},
                'status': 'failed'
            })
        
        # Prevent overwhelming Ollama
        time.sleep(0.5)
    
    total_time = time.time() - total_start
    avg_time = total_time / len(candidates)
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    final_results = {
        'processing_info': {
            'total_candidates': len(candidates),
            'successful': successful,
            'failed': failed,
            'total_time_seconds': round(total_time, 2),
            'avg_time_per_candidate': round(avg_time, 2),
            'processed_at': datetime.now().isoformat(),
            'analysis_type': 'enhanced_prd_compliant'
        },
        'results': results
    }
    
    output_file = OUTPUT_DIR / f"enhanced_analysis_{timestamp}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, indent=2, ensure_ascii=False)
    
    # Summary
    print("\n" + "=" * 80)
    print("ENHANCED PROCESSING COMPLETE")
    print("=" * 80)
    print(f"Processed: {len(candidates)} candidates")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Success rate: {successful/len(candidates)*100:.1f}%")
    print(f"Total time: {total_time:.2f} seconds ({total_time/60:.1f} minutes)")
    print(f"Average time: {avg_time:.2f} seconds per candidate")
    print(f"\n📁 Results saved to: {output_file}")
    print(f"File size: {output_file.stat().st_size / (1024*1024):.1f} MB")

if __name__ == "__main__":
    process_candidates_enhanced(3)