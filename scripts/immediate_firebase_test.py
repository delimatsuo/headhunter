#!/usr/bin/env python3
"""
Immediate Firebase test - Generate 3 enhanced profiles for quality review
"""

import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from enhanced_together_ai_processor import EnhancedTogetherAIProcessor

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Generate and upload 3 candidates for immediate quality review"""
    
    print("🎯 IMMEDIATE FIREBASE QUALITY TEST")
    print("=" * 50)
    print("✅ Generating 3 enhanced profiles with interview comments")
    print("✅ Uploading directly to Firebase for quality review")
    print("=" * 50)
    
    # Initialize processor
    processor = EnhancedTogetherAIProcessor()
    
    # Load candidates
    merged_file = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json")
    
    if not merged_file.exists():
        print("❌ Merged candidates file not found")
        return
    
    with open(merged_file, 'r') as f:
        all_candidates = json.load(f)
    
    # Filter for candidates with substantial data and comments
    quality_candidates = []
    for candidate in all_candidates:
        experience_len = len(candidate.get('experience', ''))
        education_len = len(candidate.get('education', ''))
        comments_count = len(candidate.get('comments', []))
        
        # Select candidates with good data and comments
        if (experience_len > 200 or education_len > 100) and comments_count >= 2:
            quality_candidates.append(candidate)
            
            if len(quality_candidates) >= 3:
                break
    
    if not quality_candidates:
        print("❌ No suitable candidates found")
        return
    
    print("📋 SELECTED CANDIDATES FOR QUALITY TEST:")
    print("-" * 45)
    for i, candidate in enumerate(quality_candidates, 1):
        name = candidate.get('name', 'N/A')
        exp_len = len(candidate.get('experience', ''))
        edu_len = len(candidate.get('education', ''))
        comments = len(candidate.get('comments', []))
        
        print(f" {i}. {name}")
        print(f"    📄 Experience: {exp_len} chars")
        print(f"    🎓 Education: {edu_len} chars") 
        print(f"    💬 Comments: {comments} items")
        
        # Show sample interview comment
        if candidate.get('comments'):
            sample_comment = candidate['comments'][0].get('text', '')
            if sample_comment:
                preview = sample_comment[:100] + "..." if len(sample_comment) > 100 else sample_comment
                print(f"    📝 Sample: {preview}")
        print()
    
    # Process with Together AI
    print("🚀 PROCESSING WITH TOGETHER AI...")
    print("-" * 40)
    
    enhanced_profiles = []
    
    for i, candidate in enumerate(quality_candidates, 1):
        name = candidate.get('name', 'N/A')
        print(f"📍 [{i}/3] Processing: {name}")
        
        try:
            # Process candidate
            enhanced_profile = await processor.process_candidate(candidate)
            
            if enhanced_profile and 'enhanced_analysis' in enhanced_profile:
                enhanced_profiles.append(enhanced_profile)
                
                # Show quick preview
                analysis = enhanced_profile['enhanced_analysis']
                rating = analysis.get('executive_summary', {}).get('overall_rating', 'N/A')
                level = analysis.get('career_trajectory', {}).get('current_level', 'N/A')
                
                print(f"   ✅ SUCCESS - Rating: {rating}/100, Level: {level}")
            else:
                print("   ❌ FAILED - No enhanced analysis generated")
                
        except Exception as e:
            print(f"   ❌ FAILED - Error: {e}")
        
        # Small delay
        await asyncio.sleep(1)
    
    # Upload to Firebase
    if enhanced_profiles:
        print(f"\n💾 UPLOADING {len(enhanced_profiles)} PROFILES TO FIREBASE...")
        print("-" * 50)
        
        try:
            # Upload one by one for better error handling
            for profile in enhanced_profiles:
                candidate_id = profile.get('candidate_id', profile.get('id', 'unknown'))
                name = profile.get('name', 'N/A')
                
                # Add timestamp for easy identification
                profile['timestamp'] = datetime.now().isoformat()
                profile['test_batch'] = 'immediate_quality_test'
                
                # Upload to Firestore
                doc_ref = processor.db.collection('enhanced_candidates').document(str(candidate_id))
                doc_ref.set(profile, merge=True)
                
                print(f"   ✅ Uploaded: {name} (ID: {candidate_id})")
            
            print(f"\n🎉 SUCCESS - {len(enhanced_profiles)} PROFILES UPLOADED!")
            print("=" * 50)
            print("🔍 VIEW IN FIREBASE:")
            print("   Console: https://console.firebase.google.com/project/headhunter-ai-0088")
            print("   Collection: enhanced_candidates")
            print("   Filter by: test_batch = 'immediate_quality_test'")
            print()
            print("📊 QUALITY REVIEW CHECKLIST:")
            print("   ✓ Check executive_summary.overall_rating (0-100)")
            print("   ✓ Review recruiter_insights (from interview comments)")
            print("   ✓ Verify cultural_signals (interview-derived)")
            print("   ✓ Examine career_trajectory analysis")
            print("   ✓ Look for anti-hallucination protection")
            
        except Exception as e:
            print(f"❌ FIREBASE UPLOAD FAILED: {e}")
    else:
        print("❌ No profiles to upload")

if __name__ == "__main__":
    asyncio.run(main())