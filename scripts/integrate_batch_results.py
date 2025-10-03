#!/usr/bin/env python3
"""
Integrate batch processing results back into the main candidate dataset
"""

import json
from pathlib import Path

# Paths
NAS_DIR = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project")
MERGED_FILE = NAS_DIR / "comprehensive_merged_candidates.json"
BATCH_DIR = NAS_DIR / "test_batch_50"
ENHANCED_ANALYSIS_DIR = NAS_DIR / "enhanced_analysis"
BATCH_FILE = ENHANCED_ANALYSIS_DIR / "enhanced_analysis_20250906_192703.json"

def integrate_batch_results():
    """Integrate LLM batch processing results into main dataset"""
    
    print("=" * 80)
    print("INTEGRATING BATCH PROCESSING RESULTS")
    print("=" * 80)
    
    # Load main dataset
    print("Loading main candidate dataset...")
    with open(MERGED_FILE, 'r', encoding='utf-8') as f:
        candidates = json.load(f)
    
    print(f"Loaded {len(candidates):,} candidates from main dataset")
    
    # Load enhanced analysis results
    print("Loading enhanced analysis results...")
    with open(BATCH_FILE, 'r', encoding='utf-8') as f:
        batch_data = json.load(f)
    
    batch_results = batch_data['results']
    print(f"Loaded {len(batch_results)} processed candidates from enhanced analysis")
    
    # Integrate results
    integrated_count = 0
    candidates_dict = {str(c['id']): c for c in candidates}
    
    for result in batch_results:
        candidate_id = result['candidate_id']
        
        if candidate_id in candidates_dict:
            # Add enhanced analysis to the candidate
            candidates_dict[candidate_id]['enhanced_analysis'] = {
                'processing_time': result['processing_time'],
                'analysis': result['enhanced_analysis'],
                'processed_at': batch_data['processing_info']['processed_at'],
                'status': result['status']
            }
            
            # Mark as processed
            candidates_dict[candidate_id]['processing_status'] = 'completed'
            integrated_count += 1
        else:
            print(f"Warning: Candidate {candidate_id} not found in main dataset")
    
    # Convert back to list
    updated_candidates = list(candidates_dict.values())
    
    print(f"Successfully integrated {integrated_count} processed candidates")
    
    # Save updated dataset
    print("Saving updated dataset...")
    with open(MERGED_FILE, 'w', encoding='utf-8') as f:
        json.dump(updated_candidates, f, indent=2, ensure_ascii=False)
    
    # Update statistics
    processed_count = sum(1 for c in updated_candidates if c.get('enhanced_analysis'))
    with_analysis = sum(1 for c in updated_candidates if c.get('enhanced_analysis', {}).get('analysis'))
    
    print("\nUpdated dataset statistics:")
    print(f"  Total candidates: {len(updated_candidates):,}")
    print(f"  With LLM processing: {processed_count:,}")
    print(f"  With analysis data: {with_analysis:,}")
    
    print("\n✅ Integration complete!")
    print(f"Updated dataset saved to: {MERGED_FILE}")
    print("=" * 80)

if __name__ == "__main__":
    integrate_batch_results()