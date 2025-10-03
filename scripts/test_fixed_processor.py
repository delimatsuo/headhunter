#!/usr/bin/env python3
"""
Test script to verify the fixed high-throughput processor
"""

import json
from high_throughput_processor import HighThroughputProcessor

def test_fixed_processor():
    """Test the fixed processor on 3 candidates"""
    print("🧪 TESTING FIXED HIGH-THROUGHPUT PROCESSOR")
    print("=" * 60)
    
    # Load NAS data
    nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
    
    with open(nas_file, 'r') as f:
        candidates = json.load(f)
    
    # Find 3 unprocessed candidates with good data
    test_candidates = []
    for i, candidate in enumerate(candidates):
        if candidate.get('recruiter_enhanced_analysis'):
            continue
            
        has_name = bool(candidate.get('name'))
        has_data = bool(candidate.get('experience') or candidate.get('education'))
        has_id = bool(candidate.get('id'))
        
        if has_id and has_name and has_data:
            test_candidates.append((i, candidate))
            if len(test_candidates) >= 3:
                break
    
    if not test_candidates:
        print("❌ No suitable test candidates found!")
        return False
    
    print(f"✅ Found {len(test_candidates)} test candidates:")
    for idx, (_, candidate) in enumerate(test_candidates):
        print(f"  {idx+1}. {candidate.get('name', 'Unknown')} (ID: {candidate.get('id')})")
    
    print("\n🚀 Creating processor instance...")
    processor = HighThroughputProcessor()
    
    print("\n🔄 Processing test candidates...")
    success_count = 0
    
    for idx, candidate_data in enumerate(test_candidates):
        list_idx, candidate = candidate_data
        candidate_name = candidate.get('name', 'Unknown')
        print(f"\n📋 Testing candidate {idx+1}/3: {candidate_name}")
        
        # Process single candidate
        result_idx, result_candidate, success = processor.process_candidate_worker(candidate_data)
        
        if success:
            success_count += 1
            print(f"  ✅ Successfully processed {candidate_name}")
            
            # Verify comprehensive data
            analysis = result_candidate.get('recruiter_enhanced_analysis', {}).get('analysis', {})
            
            # Check key fields
            checks = [
                ('personal_details', analysis.get('personal_details')),
                ('education_analysis', analysis.get('education_analysis')),
                ('experience_analysis', analysis.get('experience_analysis')),
                ('technical_assessment', analysis.get('technical_assessment')),
                ('market_insights', analysis.get('market_insights')),
                ('recruiter_recommendations', analysis.get('recruiter_recommendations')),
                ('searchability', analysis.get('searchability')),
                ('executive_summary', analysis.get('executive_summary'))
            ]
            
            print("  📊 Data completeness check:")
            for field_name, field_data in checks:
                if field_data and isinstance(field_data, dict) and any(str(v).strip() for v in field_data.values() if v):
                    print(f"    ✅ {field_name}: Complete")
                else:
                    print(f"    ❌ {field_name}: Missing/Empty")
            
            # Check for specific problematic fields
            primary_skills = analysis.get('technical_assessment', {}).get('primary_skills', [])
            ats_keywords = analysis.get('searchability', {}).get('ats_keywords', [])
            salary_range = analysis.get('market_insights', {}).get('current_market_value', {}).get('estimated_salary_range', '')
            
            print("  🎯 Key field validation:")
            print(f"    Primary skills: {len(primary_skills)} items - {'✅' if primary_skills else '❌'}")
            print(f"    ATS keywords: {len(ats_keywords)} items - {'✅' if ats_keywords else '❌'}")
            print(f"    Salary range: {'✅' if salary_range and salary_range != '' else '❌'}")
            
        else:
            print(f"  ❌ Failed to process {candidate_name}")
    
    print("\n" + "=" * 60)
    print("🏆 TEST RESULTS:")
    print(f"✅ Successful: {success_count}/{len(test_candidates)}")
    print(f"❌ Failed: {len(test_candidates) - success_count}/{len(test_candidates)}")
    
    if success_count == len(test_candidates):
        print("🎉 ALL TESTS PASSED! Fixed processor is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    test_fixed_processor()