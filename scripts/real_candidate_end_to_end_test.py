#!/usr/bin/env python3
"""
REAL CANDIDATE END-TO-END TEST

Uses actual candidate data from Ella Executive Search CSV files.
NO MOCK DATA - Only real candidate profiles with resumes and recruiter comments.
"""

import csv
import asyncio
import time
from typing import Dict, List, Any, Optional
import sys
import os

# Add cloud_run_worker to path
sys.path.append('cloud_run_worker')
from config import Config

# Add scripts to path for existing processors
from enhanced_together_ai_processor import EnhancedTogetherAIProcessor

class RealCandidateEndToEndTest:
    """Test with REAL candidate data - no mocks allowed"""
    
    def __init__(self):
        print("🚨 REAL CANDIDATE END-TO-END TEST")
        print("=" * 60)
        print("⚠️  Using ACTUAL candidate data from CSV files")
        print("⚠️  NO MOCK DATA - Only real profiles")
        print("=" * 60)
        
        self.config = Config()
        self.processor = EnhancedTogetherAIProcessor()
        
        # Real CSV file paths
        self.csv_files = [
            'CSV files/505039_Ella_Executive_Search_CSVs_1/Ella_Executive_Search_candidates_1-1.csv',
            'CSV files/505039_Ella_Executive_Search_CSVs_1/Ella_Executive_Search_candidates_2-1.csv'
        ]
        
        self.comments_file = 'CSV files/505039_Ella_Executive_Search_CSVs_1/Ella_Executive_Search_comments-2.csv'
        
        # Load real comments for context
        self.comments = self._load_real_comments()
        
    def _load_real_comments(self) -> Dict[str, List[str]]:
        """Load actual recruiter comments from CSV"""
        comments = {}
        
        if not os.path.exists(self.comments_file):
            print(f"⚠️ Comments file not found: {self.comments_file}")
            return {}
            
        try:
            with open(self.comments_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    candidate_id = row.get('candidate_id')
                    comment_body = row.get('body', '').strip()
                    
                    if candidate_id and comment_body:
                        if candidate_id not in comments:
                            comments[candidate_id] = []
                        comments[candidate_id].append(comment_body)
                        
            print(f"✅ Loaded {len(comments)} candidates with real recruiter comments")
            return comments
            
        except Exception as e:
            print(f"⚠️ Error loading comments: {e}")
            return {}
    
    def _extract_real_candidates(self, csv_file: str, max_candidates: int = 5) -> List[Dict[str, Any]]:
        """Extract REAL candidate data from CSV - no mocking"""
        
        print(f"📂 Loading real candidates from: {csv_file}")
        
        if not os.path.exists(csv_file):
            print(f"❌ File not found: {csv_file}")
            return []
            
        candidates = []
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for i, row in enumerate(reader):
                    if i >= max_candidates:
                        break
                        
                    # Only process candidates with real data
                    candidate_id = row.get('id', '').strip()
                    name = row.get('name', '').strip()
                    email = row.get('email', '').strip()
                    
                    if not candidate_id or not name:
                        continue
                        
                    # Get real recruiter comments for this candidate
                    real_comments = self.comments.get(candidate_id, [])
                    comments_text = '; '.join(real_comments) if real_comments else 'No recruiter comments available'
                    
                    # Extract real profile data
                    candidate = {
                        'candidate_id': f'real_{candidate_id}',  # Mark as real data
                        'name': name,
                        'email': email,
                        'headline': row.get('headline', '').strip(),
                        'summary': row.get('summary', '').strip(),
                        'education': row.get('education', '').strip(),
                        'experience': row.get('experience', '').strip(),
                        'skills': row.get('skills', '').strip(),
                        'social_profiles': row.get('social_profiles', '').strip(),
                        'job': row.get('job', '').strip(),
                        'stage': row.get('stage', '').strip(),
                        'created_at': row.get('created_at', '').strip(),
                        'recruiter_comments': comments_text,
                        'source': 'Real Ella Executive Search Data'
                    }
                    
                    candidates.append(candidate)
                    print(f"   ✅ Real candidate: {name} (ID: {candidate_id})")
                    
        except Exception as e:
            print(f"❌ Error reading CSV: {e}")
            return []
            
        print(f"📊 Extracted {len(candidates)} REAL candidates")
        return candidates
    
    async def test_real_candidate_processing(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process ONE real candidate through the full AI pipeline"""
        
        candidate_id = candidate['candidate_id']
        name = candidate['name']
        
        print(f"🔄 Processing REAL candidate: {name} ({candidate_id})")
        print(f"   📧 Email: {candidate.get('email', 'N/A')}")
        print(f"   💼 Job: {candidate.get('job', 'N/A')}")
        print(f"   📝 Stage: {candidate.get('stage', 'N/A')}")
        print(f"   💬 Comments: {candidate.get('recruiter_comments', 'N/A')[:100]}...")
        
        start_time = time.time()
        
        try:
            # Create resume text from real data
            resume_parts = []
            
            if candidate.get('headline'):
                resume_parts.append(f"Professional Headline: {candidate['headline']}")
                
            if candidate.get('summary'):
                resume_parts.append(f"Summary: {candidate['summary']}")
                
            if candidate.get('experience'):
                resume_parts.append(f"Experience: {candidate['experience']}")
                
            if candidate.get('education'):
                resume_parts.append(f"Education: {candidate['education']}")
                
            if candidate.get('skills'):
                resume_parts.append(f"Skills: {candidate['skills']}")
                
            resume_text = '\n\n'.join(resume_parts) if resume_parts else f"Real candidate: {name}"
            
            # Process through AI with real data
            enhanced_profile = await self.processor.process_candidate({
                'candidate_id': candidate_id,
                'name': name,
                'current_title': candidate.get('job', 'Software Engineer'),
                'recruiter_comments': candidate.get('recruiter_comments', ''),
                'raw_data': {
                    'resume_text': resume_text,
                    'linkedin_profile': candidate.get('social_profiles', ''),
                    'email': candidate.get('email', ''),
                    'stage': candidate.get('stage', ''),
                    'created_at': candidate.get('created_at', '')
                }
            })
            
            processing_time = time.time() - start_time
            
            if enhanced_profile:
                print(f"   ✅ SUCCESS: {processing_time:.2f}s")
                
                # Show real analysis results
                analysis = enhanced_profile.get('enhanced_analysis', {})
                career = analysis.get('career_trajectory_analysis', {})
                summary = analysis.get('executive_summary', {})
                
                print(f"   📊 Current Level: {career.get('current_level', 'N/A')}")
                print(f"   🎯 Overall Rating: {summary.get('overall_rating', 'N/A')}")
                print(f"   📝 One-line Pitch: {summary.get('one_line_pitch', 'N/A')[:80]}...")
                
                return enhanced_profile
            else:
                print("   ❌ FAILED: No enhanced profile generated")
                return None
                
        except Exception as e:
            processing_time = time.time() - start_time
            print(f"   💥 ERROR after {processing_time:.2f}s: {e}")
            return None
    
    async def run_end_to_end_test(self, num_candidates: int = 5):
        """Run complete end-to-end test with REAL candidate data"""
        
        print("\n🚀 STARTING REAL END-TO-END TEST")
        print(f"📊 Processing {num_candidates} REAL candidates")
        print("-" * 50)
        
        # Load real candidates from first CSV file
        real_candidates = self._extract_real_candidates(
            self.csv_files[0], 
            max_candidates=num_candidates
        )
        
        if not real_candidates:
            print("❌ No real candidates loaded - test cannot proceed")
            return
            
        print(f"\n🔄 Processing {len(real_candidates)} real candidates through AI pipeline:")
        print("-" * 50)
        
        results = {
            'successful': [],
            'failed': [],
            'total_time': 0,
            'total_cost': 0
        }
        
        for i, candidate in enumerate(real_candidates, 1):
            print(f"\n📍 [{i}/{len(real_candidates)}] {candidate['name']}")
            
            result = await self.test_real_candidate_processing(candidate)
            
            if result:
                results['successful'].append(result)
                # Estimate cost (simplified)
                results['total_cost'] += 0.0005
            else:
                results['failed'].append(candidate)
        
        # Final results
        total_processed = len(results['successful']) + len(results['failed'])
        success_rate = (len(results['successful']) / total_processed) * 100 if total_processed > 0 else 0
        
        print("\n" + "=" * 60)
        print("🎯 REAL CANDIDATE END-TO-END TEST RESULTS")
        print("=" * 60)
        print(f"✅ Successfully processed: {len(results['successful'])}/{total_processed} ({success_rate:.1f}%)")
        print(f"❌ Failed: {len(results['failed'])}")
        print(f"💰 Estimated cost: ${results['total_cost']:.4f}")
        
        if results['successful']:
            print("\n📋 SAMPLE REAL CANDIDATE ANALYSIS:")
            sample = results['successful'][0]
            print(f"   👤 Name: {sample['name']}")
            
            analysis = sample.get('enhanced_analysis', {})
            career = analysis.get('career_trajectory_analysis', {})
            leadership = analysis.get('leadership_scope', {})
            summary = analysis.get('executive_summary', {})
            
            print(f"   📊 Current Level: {career.get('current_level', 'N/A')}")
            print(f"   👥 Leadership: {leadership.get('has_leadership', 'N/A')}")
            print(f"   🎯 Rating: {summary.get('overall_rating', 'N/A')}")
            print(f"   📝 Pitch: {summary.get('one_line_pitch', 'N/A')}")
            
        if results['failed']:
            print("\n⚠️ FAILED CANDIDATES:")
            for failed in results['failed']:
                print(f"   - {failed['name']} ({failed['candidate_id']})")
                
        # Save results to Firestore for review
        if results['successful']:
            print(f"\n💾 Uploading {len(results['successful'])} real profiles to Firestore...")
            await self._save_to_firestore(results['successful'])
        
        return results
    
    async def _save_to_firestore(self, profiles: List[Dict[str, Any]]):
        """Save real candidate profiles to Firestore"""
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
            
            # Initialize Firebase (reuse existing instance if available)
            try:
                db = firestore.client()
            except:
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred)
                db = firestore.client()
            
            saved_count = 0
            for profile in profiles:
                doc_id = profile['candidate_id']
                doc_ref = db.collection('enhanced_candidates').document(doc_id)
                doc_ref.set(profile)
                saved_count += 1
                
            print(f"✅ Saved {saved_count} real profiles to Firestore")
            print("🔍 Check collection: enhanced_candidates")
            print("📋 Document IDs start with: real_[candidate_id]")
            
        except Exception as e:
            print(f"❌ Error saving to Firestore: {e}")

async def main():
    """Run the REAL candidate end-to-end test"""
    
    tester = RealCandidateEndToEndTest()
    
    print("🚨 This test uses REAL candidate data from your CSV files")
    print("🚨 Processing will take time and cost money (Together AI API)")
    print("🚨 Results will be uploaded to Firestore for review")
    
    # Run with 5 real candidates
    await tester.run_end_to_end_test(num_candidates=5)
    
    print("\n✅ REAL END-TO-END TEST COMPLETED")
    print("🔍 Review results in Firestore console:")
    print("   Collection: enhanced_candidates")
    print("   Look for documents starting with: real_")

if __name__ == "__main__":
    asyncio.run(main())