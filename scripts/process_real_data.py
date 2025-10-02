#!/usr/bin/env python3
"""
Process real Ella Executive Search database
Direct processing without complex dependencies
"""

import csv
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_DIR = REPO_ROOT / "CSV files/505039_Ella_Executive_Search_CSVs_1"
DEFAULT_RESUME_DIR = REPO_ROOT / "CSV files/505039_Ella_Executive_Search_files_1/resumes"
DEFAULT_OUTPUT_FILE = REPO_ROOT / "scripts/real_candidates_processed.json"

class RealDataProcessor:
    def __init__(self, csv_dir: str, resumes_dir: str):
        self.csv_dir = csv_dir
        self.resumes_dir = resumes_dir
        
    def load_candidates_csv(self, limit: int = None) -> List[Dict[str, Any]]:
        """Load candidates from the main CSV file"""
        candidates_file = os.path.join(self.csv_dir, "Ella_Executive_Search_candidates_2-1.csv")
        
        candidates = []
        try:
            with open(candidates_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if limit and i >= limit:
                        break
                    candidates.append(row)
            print(f"✅ Loaded {len(candidates)} candidates from CSV")
        except Exception as e:
            print(f"❌ Error loading candidates CSV: {e}")
            return []
        
        return candidates
    
    def load_comments_csv(self) -> Dict[str, List[str]]:
        """Load recruiter comments by candidate ID"""
        comments = {}
        comment_files = [
            "Ella_Executive_Search_comments-1.csv",
            "Ella_Executive_Search_comments-3.csv", 
            "Ella_Executive_Search_comments-4.csv",
            "Ella_Executive_Search_comments-7.csv"
        ]
        
        for comment_file in comment_files:
            filepath = os.path.join(self.csv_dir, comment_file)
            if not os.path.exists(filepath):
                continue
                
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        candidate_id = row.get('candidate_id', row.get('id', ''))
                        comment_text = row.get('note', row.get('comment', row.get('text', '')))
                        
                        if candidate_id and comment_text:
                            if candidate_id not in comments:
                                comments[candidate_id] = []
                            comments[candidate_id].append(comment_text)
                            
                print(f"✅ Loaded comments from {comment_file}")
            except Exception as e:
                print(f"⚠️  Error loading {comment_file}: {e}")
        
        print(f"📊 Total candidates with comments: {len(comments)}")
        return comments
    
    def process_candidate_basic(self, candidate_row: Dict[str, Any], comments: List[str] = None) -> Dict[str, Any]:
        """Process a single candidate with basic analysis"""
        
        # Extract basic info
        candidate_id = candidate_row.get('id', '')
        name = candidate_row.get('name', 'Unknown')
        email = candidate_row.get('email', '')
        headline = candidate_row.get('headline', '')
        summary = candidate_row.get('summary', '')
        phone = candidate_row.get('phone', '')
        
        # Simple skill extraction from headline and summary
        combined_text = f"{headline} {summary}".lower()
        technical_skills = []
        
        # Common technical skills to look for
        skill_keywords = [
            'python', 'java', 'javascript', 'react', 'node', 'aws', 'kubernetes',
            'docker', 'typescript', 'go', 'rust', 'c++', 'sql', 'mongodb',
            'microservices', 'api', 'cloud', 'devops', 'machine learning', 'ml',
            'ai', 'data science', 'analytics', 'blockchain', 'cybersecurity'
        ]
        
        for skill in skill_keywords:
            if skill in combined_text:
                technical_skills.append(skill.title())
        
        # Simple experience level detection
        years_experience = 0
        current_level = "Unknown"
        
        if any(term in combined_text for term in ['senior', 'sr.', 'lead']):
            current_level = "Senior"
            years_experience = 7
        elif any(term in combined_text for term in ['principal', 'staff', 'architect']):
            current_level = "Principal"
            years_experience = 10
        elif any(term in combined_text for term in ['director', 'vp', 'head of']):
            current_level = "Director"
            years_experience = 12
        elif any(term in combined_text for term in ['junior', 'jr.', 'intern']):
            current_level = "Junior"
            years_experience = 2
        else:
            current_level = "Mid-level"
            years_experience = 5
        
        # Leadership detection
        has_leadership = any(term in combined_text for term in [
            'manager', 'lead', 'director', 'head', 'team', 'management'
        ])
        
        # Company tier estimation (basic)
        company_tier = "tier_3"  # Default
        if any(company in combined_text for company in [
            'google', 'meta', 'facebook', 'amazon', 'microsoft', 'apple', 'netflix'
        ]):
            company_tier = "tier_1"
        elif any(company in combined_text for company in [
            'uber', 'spotify', 'airbnb', 'stripe', 'shopify', 'twitter'
        ]):
            company_tier = "tier_2"
        
        # Process comments if available
        recruiter_sentiment = "neutral"
        strengths = []
        recommendation = "consider"
        
        if comments:
            comment_text = " ".join(comments).lower()
            
            if any(word in comment_text for word in ['excellent', 'outstanding', 'exceptional']):
                recruiter_sentiment = "very_positive"
                recommendation = "strong_hire"
            elif any(word in comment_text for word in ['good', 'solid', 'competent']):
                recruiter_sentiment = "positive"
                recommendation = "hire"
            elif any(word in comment_text for word in ['concern', 'issue', 'weak']):
                recruiter_sentiment = "negative"
                recommendation = "pass"
            
            # Extract strengths
            if 'leadership' in comment_text:
                strengths.append("Strong leadership skills")
            if 'technical' in comment_text:
                strengths.append("Technical expertise")
            if 'communication' in comment_text:
                strengths.append("Good communication")
        
        # Create structured profile
        profile = {
            "candidate_id": candidate_id,
            "name": name,
            "current_role": headline,
            "current_company": "Unknown",  # Would need parsing
            "resume_analysis": {
                "career_trajectory": {
                    "current_level": current_level,
                    "progression_speed": "steady",
                    "trajectory_type": "technical" if not has_leadership else "leadership"
                },
                "years_experience": years_experience,
                "technical_skills": technical_skills[:10],  # Limit to top 10
                "soft_skills": ["Communication", "Problem-solving"],
                "leadership_scope": {
                    "has_leadership": has_leadership,
                    "team_size": 5 if has_leadership else 0,
                    "leadership_level": "Manager" if has_leadership else "Individual Contributor"
                },
                "company_pedigree": {
                    "tier_level": company_tier,
                    "recent_companies": ["Unknown"]
                },
                "education": {
                    "highest_degree": "Bachelor's",
                    "institutions": ["Unknown"]
                }
            },
            "recruiter_insights": {
                "sentiment": recruiter_sentiment,
                "strengths": strengths if strengths else ["Professional experience"],
                "recommendation": recommendation,
                "key_themes": ["Technical skills", "Experience"]
            },
            "overall_score": 0.75 if recruiter_sentiment == "positive" else 0.85 if recruiter_sentiment == "very_positive" else 0.60,
            "contact_info": {
                "email": email,
                "phone": phone
            },
            "processing_timestamp": datetime.now().isoformat()
        }
        
        return profile
    
    def process_batch(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Process a batch of real candidates"""
        print(f"🚀 Processing {limit} real candidates from Ella Executive Search database")
        print("-" * 60)
        
        # Load data
        candidates = self.load_candidates_csv(limit)
        comments = self.load_comments_csv()
        
        if not candidates:
            print("❌ No candidates loaded")
            return []
        
        processed_candidates = []
        
        for i, candidate_row in enumerate(candidates):
            try:
                candidate_id = candidate_row.get('id', '')
                candidate_comments = comments.get(candidate_id, [])
                
                processed_candidate = self.process_candidate_basic(candidate_row, candidate_comments)
                processed_candidates.append(processed_candidate)
                
                print(f"✅ Processed {i+1}/{len(candidates)}: {processed_candidate['name']}")
                
            except Exception as e:
                print(f"❌ Error processing candidate {i+1}: {e}")
                continue
        
        print(f"\n🎉 Successfully processed {len(processed_candidates)} candidates")
        return processed_candidates

def main():
    """Main processing function"""
    csv_dir = DEFAULT_CSV_DIR
    resumes_dir = DEFAULT_RESUME_DIR

    processor = RealDataProcessor(str(csv_dir), str(resumes_dir))
    
    # Process a reasonable batch for testing
    batch_size = 100  # Start with 100 candidates
    processed_candidates = processor.process_batch(batch_size)
    
    if processed_candidates:
        # Save to JSON
        output_file = DEFAULT_OUTPUT_FILE
        with open(output_file, "w") as f:
            json.dump(processed_candidates, f, indent=2)
        
        print(f"💾 Saved {len(processed_candidates)} processed candidates to {output_file}")
        
        # Show sample
        print("\n📋 Sample processed candidate:")
        print(json.dumps(processed_candidates[0], indent=2))
        
        # Quick stats
        total_with_skills = sum(1 for c in processed_candidates if c['resume_analysis']['technical_skills'])
        total_with_leadership = sum(1 for c in processed_candidates if c['resume_analysis']['leadership_scope']['has_leadership'])
        avg_score = sum(c['overall_score'] for c in processed_candidates) / len(processed_candidates)
        
        print(f"\n📊 Processing Statistics:")
        print(f"   Total candidates: {len(processed_candidates)}")
        print(f"   With technical skills: {total_with_skills}")
        print(f"   With leadership: {total_with_leadership}")
        print(f"   Average score: {avg_score:.2f}")
        
        return output_file
    else:
        print("❌ No candidates were processed successfully")
        return None

if __name__ == "__main__":
    result = main()
    if result:
        print(f"\n✅ Processing complete! Output saved to: {result}")
        print("\n🔄 Next steps:")
        print("1. Upload candidates to Firestore")
        print("2. Generate embeddings")
        print("3. Test search functionality")
    else:
        print("❌ Processing failed")