#!/usr/bin/env python3
"""
Simple test to process 50 candidates using Ollama directly
Measure time and resource usage
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Constants
NAS_DIR = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project")
MERGED_FILE = NAS_DIR / "comprehensive_merged_candidates.json"
OUTPUT_DIR = NAS_DIR / "test_batch_50"

class SimpleOllamaClient:
    """Simple Ollama client"""
    
    def __init__(self, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
    
    def verify_connection(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                for model in models:
                    if self.model in model.get('name', ''):
                        return True
            return False
        except Exception:
            return False
    
    def process_candidate(self, candidate_data: Dict) -> Dict:
        """Process candidate with simple prompt"""
        
        # Build candidate summary
        candidate_text = f"""
Candidate: {candidate_data.get('name', 'Unknown')}
Email: {candidate_data.get('email', 'N/A')}
Phone: {candidate_data.get('phone', 'N/A')}
Headline: {candidate_data.get('headline', 'N/A')}
Summary: {candidate_data.get('summary', 'N/A')}
Skills: {candidate_data.get('skills', 'N/A')}
Education: {candidate_data.get('education', 'N/A')}
Experience: {candidate_data.get('experience', 'N/A')}

Comments ({len(candidate_data.get('comments', []))} total):
"""
        
        # Add comments
        for comment in candidate_data.get('comments', [])[:5]:  # Limit to 5 comments
            candidate_text += f"- {comment.get('author', 'Unknown')}: {comment.get('text', '')}\n"
        
        prompt = f"""Analyze this candidate profile and extract key information in JSON format.

{candidate_text}

Please provide a JSON response with:
- extracted_skills: list of technical skills
- seniority_level: junior/mid/senior/executive
- industry: primary industry
- key_strengths: list of 3 key strengths
- overall_rating: 1-10 rating
- summary: brief summary

Respond only with valid JSON."""

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                
                # Try to parse JSON response
                try:
                    # Extract JSON from response if wrapped in text
                    if '```json' in response_text:
                        json_start = response_text.find('```json') + 7
                        json_end = response_text.find('```', json_start)
                        response_text = response_text[json_start:json_end].strip()
                    elif '{' in response_text:
                        json_start = response_text.find('{')
                        json_end = response_text.rfind('}') + 1
                        response_text = response_text[json_start:json_end]
                    
                    analysis = json.loads(response_text)
                    return analysis
                    
                except json.JSONDecodeError:
                    # Return raw response if JSON parsing fails
                    return {
                        'raw_response': response_text,
                        'error': 'Failed to parse JSON'
                    }
            else:
                return {'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            return {'error': str(e)}

def load_candidates(limit: int = 50) -> List[Dict]:
    """Load first N candidates from merged data"""
    print(f"Loading first {limit} candidates from merged data...")
    
    with open(MERGED_FILE, 'r', encoding='utf-8') as f:
        all_candidates = json.load(f)
    
    # Filter to get candidates with actual data (not orphaned)
    normal_candidates = [c for c in all_candidates if c.get('data_status') != 'orphaned' and c.get('name')]
    
    # Take first 50
    selected = normal_candidates[:limit]
    
    print(f"Selected {len(selected)} candidates for processing")
    return selected

def main():
    """Main processing function"""
    print("=" * 80)
    print("HEADHUNTER: 50 Candidate Batch Processing Test")
    print("Using: Ollama with Llama 3.1:8b (Local)")
    print("=" * 80)
    
    # Step 1: Check Ollama connection
    print("\nStep 1: Checking Ollama connection...")
    client = SimpleOllamaClient()
    
    if not client.verify_connection():
        print("ERROR: Ollama is not running or llama3.1:8b model is not available")
        print("\nPlease ensure:")
        print("1. Ollama is running: ollama serve")
        print("2. Model is pulled: ollama pull llama3.1:8b")
        return
    
    print("✓ Ollama connection verified")
    
    # Step 2: Load candidates
    print("\nStep 2: Loading candidates...")
    candidates = load_candidates(limit=50)
    
    if not candidates:
        print("ERROR: No candidates found")
        return
    
    # Step 3: Process batch
    print(f"\nStep 3: Processing batch of {len(candidates)} candidates...")
    print("=" * 80)
    
    results = []
    metrics = {
        'total_candidates': len(candidates),
        'successful': 0,
        'failed': 0,
        'candidates_with_comments': 0,
        'total_comments_processed': 0
    }
    
    batch_start = time.time()
    
    for i, candidate in enumerate(candidates, 1):
        candidate_start = time.time()
        
        # Count comments
        comment_count = len(candidate.get('comments', []))
        if comment_count > 0:
            metrics['candidates_with_comments'] += 1
            metrics['total_comments_processed'] += comment_count
        
        print(f"\n[{i}/50] Processing: {candidate.get('name', 'Unknown')}")
        print(f"  ID: {candidate.get('id')}")
        print(f"  Comments: {comment_count}")
        
        try:
            # Process with Ollama
            analysis = client.process_candidate(candidate)
            
            processing_time = time.time() - candidate_start
            
            # Store result
            result = {
                'candidate_id': candidate.get('id'),
                'candidate_name': candidate.get('name'),
                'processing_time_seconds': round(processing_time, 2),
                'analysis': analysis,
                'processed_at': datetime.now().isoformat()
            }
            
            results.append(result)
            
            if 'error' not in analysis:
                metrics['successful'] += 1
                print(f"  ✓ Processed in {processing_time:.2f}s")
                
                # Show extracted info
                if isinstance(analysis, dict):
                    skills = analysis.get('extracted_skills', [])
                    if skills:
                        print(f"  Skills: {', '.join(skills[:3])}")
                    rating = analysis.get('overall_rating', 'N/A')
                    print(f"  Rating: {rating}/10")
            else:
                metrics['failed'] += 1
                print(f"  ✗ Error: {analysis.get('error', 'Unknown error')}")
            
        except Exception as e:
            processing_time = time.time() - candidate_start
            print(f"  ✗ Exception: {e}")
            
            metrics['failed'] += 1
            results.append({
                'candidate_id': candidate.get('id'),
                'candidate_name': candidate.get('name'),
                'processing_time_seconds': round(processing_time, 2),
                'analysis': {'error': str(e)},
                'processed_at': datetime.now().isoformat()
            })
        
        # Small delay between candidates
        time.sleep(0.5)
    
    # Calculate final metrics
    total_time = time.time() - batch_start
    avg_time = total_time / len(candidates)
    
    # Step 4: Save results
    print("\nStep 4: Saving results...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    final_results = {
        'batch_info': {
            'candidates_processed': len(candidates),
            'successful': metrics['successful'],
            'failed': metrics['failed'],
            'total_time_seconds': round(total_time, 2),
            'avg_time_per_candidate': round(avg_time, 2),
            'candidates_with_comments': metrics['candidates_with_comments'],
            'total_comments_processed': metrics['total_comments_processed']
        },
        'results': results
    }
    
    output_file = OUTPUT_DIR / f"batch_50_simple_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Results saved to: {output_file}")
    
    # Step 5: Print summary
    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE - SUMMARY")
    print("=" * 80)
    
    print(f"Total candidates: {metrics['total_candidates']}")
    print(f"Successful: {metrics['successful']}")
    print(f"Failed: {metrics['failed']}")
    print(f"Candidates with comments: {metrics['candidates_with_comments']}")
    print(f"Total comments processed: {metrics['total_comments_processed']}")
    print(f"\nTiming:")
    print(f"  Total time: {total_time:.2f} seconds")
    print(f"  Average per candidate: {avg_time:.2f} seconds")
    
    # Extrapolate to full dataset
    total_candidates = 23594
    estimated_time = (total_candidates / 50) * total_time
    estimated_hours = estimated_time / 3600
    
    print(f"\n📊 Extrapolation to full dataset ({total_candidates:,} candidates):")
    print(f"  Estimated time: {estimated_hours:.1f} hours")
    print(f"  Estimated days (24/7): {estimated_hours/24:.1f} days")
    print(f"  Estimated days (8hr/day): {estimated_hours/8:.1f} work days")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()