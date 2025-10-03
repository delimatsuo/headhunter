#!/usr/bin/env python3
"""
Production-scale test: 50 candidates with timing analysis
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

# Constants
NAS_DIR = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project")
MERGED_FILE = NAS_DIR / "comprehensive_merged_candidates.json"
OUTPUT_DIR = NAS_DIR / "test_batch_50"

def test_50_candidates():
    print("=" * 80)
    print("PRODUCTION SCALE TEST: 50 Candidates with Llama 3.1:8b")
    print("=" * 80)
    
    # Load 50 candidates
    print("Loading first 50 candidates...")
    with open(MERGED_FILE, 'r', encoding='utf-8') as f:
        all_candidates = json.load(f)
    
    # Get first 50 normal candidates (with actual data)
    normal_candidates = [c for c in all_candidates if c.get('data_status') != 'orphaned' and c.get('name')]
    candidates = normal_candidates[:50]
    
    print(f"Selected {len(candidates)} candidates")
    print(f"Candidates with comments: {sum(1 for c in candidates if c.get('comments'))}")
    
    # Process each candidate
    total_start = time.time()
    results = []
    successful = 0
    failed = 0
    
    for i, candidate in enumerate(candidates, 1):
        print(f"\n[{i:2d}/50] Processing: {candidate.get('name', 'Unknown')[:40]}")
        print(f"          ID: {candidate.get('id')}")
        print(f"          Comments: {len(candidate.get('comments', []))}")
        
        candidate_start = time.time()
        
        # More comprehensive prompt
        candidate_summary = f"""
Name: {candidate.get('name', 'Unknown')}
Email: {candidate.get('email', 'N/A')}
Headline: {candidate.get('headline', 'N/A')}
Summary: {candidate.get('summary', 'N/A')[:200]}
Skills: {candidate.get('skills', 'N/A')[:200]}
Education: {candidate.get('education', 'N/A')[:200]}
Experience: {candidate.get('experience', 'N/A')[:200]}

Recent Comments ({len(candidate.get('comments', []))} total):"""
        
        # Add up to 3 recent comments
        for comment in candidate.get('comments', [])[:3]:
            candidate_summary += f"\n- {comment.get('author', 'Unknown')}: {comment.get('text', '')[:100]}"
        
        prompt = f"""Analyze this candidate profile and provide structured analysis:

{candidate_summary}

Provide a JSON response with:
{{
  "technical_skills": ["skill1", "skill2", "skill3"],
  "seniority_level": "junior/mid/senior/executive", 
  "primary_industry": "industry name",
  "key_strengths": ["strength1", "strength2", "strength3"],
  "overall_rating": 7,
  "brief_summary": "2-3 sentence summary",
  "recommended_roles": ["role1", "role2"]
}}

Respond with valid JSON only:"""

        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                processing_time = time.time() - candidate_start
                
                # Try to parse JSON response
                llm_response = result.get('response', '')
                analysis = None
                
                try:
                    # Extract JSON if wrapped
                    if '{' in llm_response:
                        json_start = llm_response.find('{')
                        json_end = llm_response.rfind('}') + 1
                        json_text = llm_response[json_start:json_end]
                        analysis = json.loads(json_text)
                except:
                    analysis = {'raw_response': llm_response[:200]}
                
                results.append({
                    'candidate_id': candidate.get('id'),
                    'name': candidate.get('name'),
                    'processing_time': round(processing_time, 2),
                    'analysis': analysis,
                    'comments_count': len(candidate.get('comments', [])),
                    'status': 'success'
                })
                
                successful += 1
                print(f"          ✓ {processing_time:.2f}s")
                
                # Show key extracted info
                if analysis and isinstance(analysis, dict):
                    rating = analysis.get('overall_rating', 'N/A')
                    skills = analysis.get('technical_skills', [])
                    if skills:
                        print(f"          Skills: {', '.join(skills[:2])}")
                    print(f"          Rating: {rating}/10")
                
            else:
                failed += 1
                print(f"          ✗ HTTP {response.status_code}")
                results.append({
                    'candidate_id': candidate.get('id'),
                    'name': candidate.get('name'),
                    'processing_time': time.time() - candidate_start,
                    'analysis': {'error': f'HTTP {response.status_code}'},
                    'status': 'failed'
                })
                
        except Exception as e:
            failed += 1
            processing_time = time.time() - candidate_start
            print(f"          ✗ Error: {e}")
            
            results.append({
                'candidate_id': candidate.get('id'),
                'name': candidate.get('name'),
                'processing_time': round(processing_time, 2),
                'analysis': {'error': str(e)},
                'status': 'failed'
            })
        
        # Small delay to avoid overwhelming Ollama
        time.sleep(0.25)
    
    total_time = time.time() - total_start
    avg_time = total_time / len(candidates)
    
    # Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    final_results = {
        'batch_info': {
            'total_candidates': len(candidates),
            'successful': successful,
            'failed': failed,
            'total_time_seconds': round(total_time, 2),
            'avg_time_per_candidate': round(avg_time, 2),
            'candidates_with_comments': sum(1 for c in candidates if c.get('comments')),
            'total_comments_processed': sum(len(c.get('comments', [])) for c in candidates),
            'processed_at': datetime.now().isoformat()
        },
        'results': results
    }
    
    output_file = OUTPUT_DIR / f"batch_50_production_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, indent=2, ensure_ascii=False)
    
    # Print comprehensive summary
    print("\n" + "=" * 80)
    print("BATCH PROCESSING COMPLETE")
    print("=" * 80)
    print(f"Total candidates processed: {len(candidates)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Success rate: {successful/len(candidates)*100:.1f}%")
    print("\nTiming Analysis:")
    print(f"  Total batch time: {total_time:.2f} seconds ({total_time/60:.1f} minutes)")
    print(f"  Average per candidate: {avg_time:.2f} seconds")
    print(f"  Fastest: {min(r['processing_time'] for r in results):.2f}s")
    print(f"  Slowest: {max(r['processing_time'] for r in results):.2f}s")
    
    # Data complexity analysis
    with_comments = sum(1 for c in candidates if c.get('comments'))
    avg_comments = sum(len(c.get('comments', [])) for c in candidates) / len(candidates)
    
    print("\nData Complexity:")
    print(f"  Candidates with comments: {with_comments}/{len(candidates)} ({with_comments/len(candidates)*100:.1f}%)")
    print(f"  Average comments per candidate: {avg_comments:.1f}")
    
    # Extrapolate to full dataset
    total_candidates = 23594
    estimated_total_time = (total_candidates / 50) * total_time
    estimated_hours = estimated_total_time / 3600
    estimated_days_24_7 = estimated_hours / 24
    estimated_days_8hr = estimated_hours / 8
    
    print(f"\n📊 FULL DATASET PROJECTIONS ({total_candidates:,} candidates):")
    print(f"  Total batches needed: {total_candidates // 50:,}")
    print(f"  Estimated total time: {estimated_hours:.1f} hours")
    print(f"  Running 24/7: {estimated_days_24_7:.1f} days")
    print(f"  Running 8hr/day: {estimated_days_8hr:.1f} work days")
    
    # Resource usage estimates
    print("\n💻 RESOURCE REQUIREMENTS:")
    print("  CPU usage: High (Ollama is CPU-intensive)")
    print("  Memory: 8-12 GB (for Llama 3.1:8b)")
    print("  Disk space: ~5-10 GB for output JSON files")
    print("  Network: None (all local processing)")
    
    print(f"\n💾 Results saved to: {output_file}")
    print(f"File size: {output_file.stat().st_size / (1024*1024):.1f} MB")
    print("=" * 80)

if __name__ == "__main__":
    test_50_candidates()