#!/usr/bin/env python3
"""
Integration test for quality validation system with LLM processor
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

from llm_processor import LLMProcessor
import tempfile
import csv
import json

def test_integration():
    """Test integration of quality validation with LLM processor"""
    
    # Create sample test data
    test_data = [
        {
            'candidate_id': 'test_001',
            'name': 'John Doe',
            'resume_text': '''
                Senior Software Engineer with 8 years of experience in Python, Django, and React.
                Led a team of 5 developers at Google working on machine learning infrastructure.
                MS Computer Science from Stanford University.
                Contributed to several open-source projects and spoke at PyCon 2023.
            ''',
            'recruiter_comments': '''
                Strong technical skills demonstrated in coding interview.
                Great communication and leadership potential.
                Good cultural fit for our team.
                Ready to start immediately.
            ''',
            'role_level': 'Senior'
        }
    ]
    
    # Create temporary CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=test_data[0].keys())
        writer.writeheader()
        writer.writerows(test_data)
        csv_file = f.name
    
    try:
        print("🧪 Testing LLM Processor with Quality Validation Integration...")
        
        # Initialize processor (this will also initialize the quality validator)
        processor = LLMProcessor(log_level='DEBUG')
        
        # Process the test data
        profiles, stats = processor.process_batch(csv_file, limit=1)
        
        print(f"\n✅ Processing completed successfully!")
        print(f"   - Records processed: {stats.successful}/{stats.total_records}")
        print(f"   - Processing time: {stats.avg_processing_time:.2f}s per record")
        
        if profiles:
            profile = profiles[0]
            print(f"\n📊 Sample Profile Results:")
            print(f"   - Candidate: {profile.name} ({profile.candidate_id})")
            print(f"   - Overall Score: {profile.overall_score:.2f}")
            print(f"   - Recommendation: {profile.recommendation}")
            
            # Check validation results
            if profile.resume_validation:
                print(f"   - Resume Validation: {'✅ PASS' if profile.resume_validation.is_valid else '❌ FAIL'}")
                print(f"     Quality Score: {profile.resume_validation.quality_score:.2f}")
                if profile.resume_validation.fallback_applied:
                    print(f"     Fallback Applied: {profile.resume_validation.fallback_applied}")
            
            if profile.recruiter_validation:
                print(f"   - Recruiter Validation: {'✅ PASS' if profile.recruiter_validation.is_valid else '❌ FAIL'}")
                print(f"     Quality Score: {profile.recruiter_validation.quality_score:.2f}")
                if profile.recruiter_validation.fallback_applied:
                    print(f"     Fallback Applied: {profile.recruiter_validation.fallback_applied}")
        
        print(f"\n🎉 Integration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False
        
    finally:
        # Clean up
        if os.path.exists(csv_file):
            os.unlink(csv_file)

if __name__ == '__main__':
    success = test_integration()
    sys.exit(0 if success else 1)