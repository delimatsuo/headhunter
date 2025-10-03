#!/usr/bin/env python3
"""
Process exactly 50 candidates using Ollama with Llama 3.1:8b
Measure time and resource usage
"""

import json
import time
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Import existing LLM processor
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from llm_processor import OllamaAPIClient, process_candidate_with_llm

# Constants
NAS_DIR = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project")
MERGED_FILE = NAS_DIR / "comprehensive_merged_candidates.json"
OUTPUT_DIR = NAS_DIR / "test_batch_50"
BATCH_SIZE = 50

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

def process_batch(candidates: List[Dict], ollama_client: OllamaAPIClient) -> Dict[str, Any]:
    """Process batch of candidates and track metrics"""
    
    results = {
        'processed_candidates': [],
        'metrics': {
            'total_candidates': len(candidates),
            'successful': 0,
            'failed': 0,
            'total_time_seconds': 0,
            'avg_time_per_candidate': 0,
            'candidates_with_comments': 0,
            'total_comments_processed': 0,
            'start_time': datetime.now().isoformat(),
            'end_time': None
        }
    }
    
    batch_start = time.time()
    
    print("\n" + "=" * 80)
    print(f"PROCESSING BATCH OF {len(candidates)} CANDIDATES")
    print("=" * 80)
    
    for i, candidate in enumerate(candidates, 1):
        candidate_start = time.time()
        
        # Count comments
        comment_count = len(candidate.get('comments', []))
        if comment_count > 0:
            results['metrics']['candidates_with_comments'] += 1
            results['metrics']['total_comments_processed'] += comment_count
        
        print(f"\n[{i}/{len(candidates)}] Processing: {candidate.get('name', 'Unknown')}")
        print(f"  ID: {candidate.get('id')}")
        print(f"  Comments: {comment_count}")
        
        try:
            # Prepare candidate data for LLM
            candidate_data = {
                'id': candidate.get('id'),
                'name': candidate.get('name', ''),
                'email': candidate.get('email', ''),
                'phone': candidate.get('phone', ''),
                'headline': candidate.get('headline', ''),
                'summary': candidate.get('summary', ''),
                'skills': candidate.get('skills', ''),
                'education': candidate.get('education', ''),
                'experience': candidate.get('experience', ''),
                'comments': candidate.get('comments', []),
                'resume_text': ''  # No resume text for now
            }
            
            # Process with LLM
            print("  Sending to Llama 3.1:8b...")
            llm_result = process_candidate_with_llm(candidate_data, ollama_client)
            
            # Calculate processing time
            candidate_time = time.time() - candidate_start
            
            # Store result
            processed = {
                'original': candidate,
                'llm_analysis': llm_result,
                'processing_time_seconds': round(candidate_time, 2),
                'processed_at': datetime.now().isoformat()
            }
            
            results['processed_candidates'].append(processed)
            results['metrics']['successful'] += 1
            
            print(f"  ✓ Processed in {candidate_time:.2f} seconds")
            
            # Extract key insights if available
            if llm_result and 'extracted_skills' in llm_result:
                skills = llm_result['extracted_skills'][:3] if llm_result['extracted_skills'] else []
                print(f"  Skills: {', '.join(skills) if skills else 'None extracted'}")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results['metrics']['failed'] += 1
            
            # Still save with error
            results['processed_candidates'].append({
                'original': candidate,
                'llm_analysis': {'error': str(e)},
                'processing_time_seconds': time.time() - candidate_start,
                'processed_at': datetime.now().isoformat()
            })
        
        # Small delay between candidates
        time.sleep(0.5)
    
    # Calculate final metrics
    batch_time = time.time() - batch_start
    results['metrics']['total_time_seconds'] = round(batch_time, 2)
    results['metrics']['avg_time_per_candidate'] = round(batch_time / len(candidates), 2)
    results['metrics']['end_time'] = datetime.now().isoformat()
    
    return results

def main():
    """Main processing function"""
    print("=" * 80)
    print("HEADHUNTER: 50 Candidate Batch Processing Test")
    print("Using: Ollama with Llama 3.1:8b (Local)")
    print("=" * 80)
    
    # Step 1: Check Ollama connection
    print("\nStep 1: Checking Ollama connection...")
    ollama_client = OllamaAPIClient(model="llama3.1:8b")
    
    if not ollama_client.verify_connection():
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
    print("\nStep 3: Processing batch...")
    results = process_batch(candidates, ollama_client)
    
    # Step 4: Save results
    print("\nStep 4: Saving results...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save detailed results
    output_file = OUTPUT_DIR / f"batch_50_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Results saved to: {output_file}")
    
    # Step 5: Print summary
    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE - SUMMARY")
    print("=" * 80)
    
    metrics = results['metrics']
    print(f"Total candidates: {metrics['total_candidates']}")
    print(f"Successful: {metrics['successful']}")
    print(f"Failed: {metrics['failed']}")
    print(f"Candidates with comments: {metrics['candidates_with_comments']}")
    print(f"Total comments processed: {metrics['total_comments_processed']}")
    print("\nTiming:")
    print(f"  Total time: {metrics['total_time_seconds']} seconds")
    print(f"  Average per candidate: {metrics['avg_time_per_candidate']} seconds")
    
    # Extrapolate to full dataset
    total_candidates = 23594
    estimated_time = (total_candidates / 50) * metrics['total_time_seconds']
    estimated_hours = estimated_time / 3600
    
    print(f"\n📊 Extrapolation to full dataset ({total_candidates:,} candidates):")
    print(f"  Estimated time: {estimated_hours:.1f} hours")
    print(f"  Estimated days (24/7): {estimated_hours/24:.1f} days")
    print(f"  Estimated days (8hr/day): {estimated_hours/8:.1f} work days")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()