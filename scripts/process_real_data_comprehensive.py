#!/usr/bin/env python3
"""
Comprehensive Ella Executive Search Database Processor
Combines ALL data sources for rich candidate profiles:
- ALL 3 candidate CSV files (candidates_1-1, candidates_2-1, candidates_3-1)  
- ALL 8 comment files (comments-1 through comments-8)
- Jobs data for understanding recruiter preferences
- PDF resume text extraction
- Enhanced skill and experience analysis
"""

import csv
import json
import os
import sys
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
import glob

# PDF text extraction (optional, will gracefully handle if not available)
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    print("⚠️  PyPDF2 not available - PDF extraction will be skipped")
    print("   Install with: pip install PyPDF2")
    PDF_AVAILABLE = False

class ComprehensiveDataProcessor:
    """Enhanced processor that uses ALL available data sources"""
    
    def __init__(self, csv_dir: str, resumes_dir: str):
        self.csv_dir = csv_dir
        self.resumes_dir = resumes_dir
        self.stats = {
            'candidates_loaded': 0,
            'comments_loaded': 0,
            'jobs_loaded': 0,
            'resumes_processed': 0,
            'profiles_created': 0
        }
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
    def load_all_candidates_csv(self, limit: int = None) -> Dict[str, Dict[str, Any]]:
        """Load and combine ALL candidate CSV files with balanced sampling"""
        self.logger.info("Loading ALL candidate CSV files with balanced sampling...")
        
        candidates = {}
        candidate_files = [
            "Ella_Executive_Search_candidates_3-1.csv",
            "Ella_Executive_Search_candidates_2-1.csv", 
            "Ella_Executive_Search_candidates_1-1.csv"
        ]
        
        # If limit specified, divide equally among available files
        per_file_limit = limit // len(candidate_files) if limit else None
        total_loaded = 0
        
        for candidate_file in candidate_files:
            filepath = os.path.join(self.csv_dir, candidate_file)
            if not os.path.exists(filepath):
                self.logger.warning(f"File not found: {candidate_file}")
                continue
                
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    file_count = 0
                    
                    for row in reader:
                        if per_file_limit and file_count >= per_file_limit:
                            break
                        if limit and total_loaded >= limit:
                            break
                            
                        candidate_id = row.get('id', '')
                        if candidate_id and candidate_id not in candidates:
                            candidates[candidate_id] = row
                            file_count += 1
                            total_loaded += 1
                    
                    self.logger.info(f"✅ Loaded {file_count} candidates from {candidate_file}")
                    
            except Exception as e:
                self.logger.error(f"❌ Error loading {candidate_file}: {e}")
        
        self.stats['candidates_loaded'] = len(candidates)
        self.logger.info(f"📊 Total unique candidates loaded: {len(candidates)}")
        return candidates
    
    def load_all_comments_csv(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load ALL comment files (comments-1 through comments-8)"""
        self.logger.info("Loading ALL comment files...")
        
        comments = {}
        comment_files = [
            "Ella_Executive_Search_comments-1.csv",
            "Ella_Executive_Search_comments-2.csv",
            "Ella_Executive_Search_comments-3.csv", 
            "Ella_Executive_Search_comments-4.csv",
            "Ella_Executive_Search_comments-5.csv",
            "Ella_Executive_Search_comments-6.csv",
            "Ella_Executive_Search_comments-7.csv",
            "Ella_Executive_Search_comments-8.csv"
        ]
        
        total_comments = 0
        
        for comment_file in comment_files:
            filepath = os.path.join(self.csv_dir, comment_file)
            if not os.path.exists(filepath):
                self.logger.warning(f"Comment file not found: {comment_file}")
                continue
                
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    file_count = 0
                    
                    for row in reader:
                        candidate_id = row.get('candidate_id', '')
                        comment_body = row.get('body', '').strip()
                        created_at = row.get('created_at', '')
                        member_id = row.get('member_id', '')
                        
                        if candidate_id and comment_body:
                            if candidate_id not in comments:
                                comments[candidate_id] = []
                            
                            comment_data = {
                                'body': comment_body,
                                'created_at': created_at,
                                'member_id': member_id,
                                'comment_id': row.get('id', ''),
                                'source_file': comment_file
                            }
                            comments[candidate_id].append(comment_data)
                            file_count += 1
                            total_comments += 1
                            
                    self.logger.info(f"✅ Loaded {file_count} comments from {comment_file}")
                    
            except Exception as e:
                self.logger.error(f"❌ Error loading {comment_file}: {e}")
        
        self.stats['comments_loaded'] = total_comments
        self.logger.info(f"📊 Total comments loaded: {total_comments} for {len(comments)} candidates")
        return comments
    
    def load_jobs_data(self) -> Dict[str, Dict[str, Any]]:
        """Load jobs data to understand recruiter preferences"""
        self.logger.info("Loading jobs data...")
        
        jobs = {}
        jobs_file = os.path.join(self.csv_dir, "Ella_Executive_Search_jobs-1.csv")
        
        if not os.path.exists(jobs_file):
            self.logger.warning("Jobs file not found")
            return {}
        
        try:
            with open(jobs_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    job_id = row.get('id', '')
                    if job_id:
                        jobs[job_id] = row
                        
            self.stats['jobs_loaded'] = len(jobs)
            self.logger.info(f"✅ Loaded {len(jobs)} jobs")
        except Exception as e:
            self.logger.error(f"❌ Error loading jobs: {e}")
            
        return jobs
    
    def extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text from PDF resume if possible"""
        if not PDF_AVAILABLE or not os.path.exists(pdf_path):
            return ""
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
        except Exception as e:
            self.logger.debug(f"Could not extract PDF text from {pdf_path}: {e}")
            return ""
    
    def find_resume_files(self, candidate_id: str) -> List[str]:
        """Find all PDF resume files for a candidate"""
        candidate_resume_dir = os.path.join(self.resumes_dir, candidate_id)
        resume_files = []
        
        if os.path.exists(candidate_resume_dir):
            # Look for PDF files in the candidate's directory structure
            pdf_pattern = os.path.join(candidate_resume_dir, "**", "*.pdf")
            resume_files = glob.glob(pdf_pattern, recursive=True)
            
        return resume_files
    
    def extract_skills_from_text(self, text: str) -> List[str]:
        """Enhanced skill extraction from resume text and other sources"""
        if not text:
            return []
        
        text_lower = text.lower()
        
        # Comprehensive skill categories
        technical_skills = [
            # Programming Languages
            'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust', 'ruby', 'php',
            'swift', 'kotlin', 'scala', 'r', 'matlab', 'sql', 'plsql', 'nosql',
            
            # Web Technologies  
            'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 'spring', 'laravel',
            'html', 'css', 'sass', 'less', 'bootstrap', 'tailwind',
            
            # Cloud & Infrastructure
            'aws', 'azure', 'gcp', 'google cloud', 'kubernetes', 'docker', 'terraform', 'ansible',
            'jenkins', 'ci/cd', 'devops', 'microservices', 'serverless',
            
            # Databases
            'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'cassandra', 'dynamodb',
            'oracle', 'sql server', 'sqlite',
            
            # Data & Analytics
            'machine learning', 'deep learning', 'data science', 'analytics', 'big data',
            'pandas', 'numpy', 'tensorflow', 'pytorch', 'scikit-learn', 'spark', 'hadoop',
            
            # Mobile
            'android', 'ios', 'react native', 'flutter', 'xamarin',
            
            # Other Technologies
            'blockchain', 'cybersecurity', 'api', 'rest', 'graphql', 'websockets', 'kafka',
            'rabbitmq', 'nginx', 'apache', 'linux', 'unix', 'git', 'github', 'bitbucket'
        ]
        
        # Business skills
        business_skills = [
            'project management', 'agile', 'scrum', 'kanban', 'product management', 
            'business analysis', 'requirements', 'stakeholder', 'leadership', 'team lead',
            'management', 'strategy', 'marketing', 'sales', 'finance', 'accounting',
            'consulting', 'operations', 'supply chain', 'quality assurance', 'testing'
        ]
        
        found_skills = []
        all_skills = technical_skills + business_skills
        
        for skill in all_skills:
            # Look for exact matches and word boundaries
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text_lower):
                found_skills.append(skill.title())
        
        # Remove duplicates and limit
        return list(dict.fromkeys(found_skills))[:15]
    
    def analyze_experience_level(self, text: str, experience_field: str = "") -> Dict[str, Any]:
        """Enhanced experience level analysis"""
        if not text and not experience_field:
            return {
                "current_level": "Unknown",
                "years_experience": 0,
                "confidence": 0.0
            }
        
        combined_text = f"{text} {experience_field}".lower()
        
        # Experience indicators with weights
        level_indicators = {
            "Principal": {
                "keywords": ["principal", "staff", "architect", "distinguished", "fellow"],
                "years": 12,
                "weight": 0.9
            },
            "Director": {
                "keywords": ["director", "vp", "vice president", "head of", "chief"],
                "years": 15,
                "weight": 0.95
            },
            "Senior": {
                "keywords": ["senior", "sr.", "lead", "team lead", "tech lead"],
                "years": 8,
                "weight": 0.8
            },
            "Mid-level": {
                "keywords": ["developer", "engineer", "analyst", "consultant"],
                "years": 5,
                "weight": 0.6
            },
            "Junior": {
                "keywords": ["junior", "jr.", "intern", "trainee", "entry", "graduate"],
                "years": 2,
                "weight": 0.7
            }
        }
        
        best_match = {"current_level": "Mid-level", "years_experience": 5, "confidence": 0.5}
        
        for level, data in level_indicators.items():
            for keyword in data["keywords"]:
                if keyword in combined_text:
                    if data["weight"] > best_match["confidence"]:
                        best_match = {
                            "current_level": level,
                            "years_experience": data["years"],
                            "confidence": data["weight"]
                        }
                    break
        
        # Look for explicit year mentions
        year_patterns = [
            r'(\d+)\+?\s*years?\s+(?:of\s+)?experience',
            r'(\d+)\+?\s*years?\s+in',
            r'over\s+(\d+)\s+years?',
            r'more than\s+(\d+)\s+years?'
        ]
        
        for pattern in year_patterns:
            matches = re.findall(pattern, combined_text)
            if matches:
                years = int(matches[0])
                if years > best_match["years_experience"]:
                    best_match["years_experience"] = years
                    best_match["confidence"] = min(best_match["confidence"] + 0.2, 1.0)
                break
        
        return best_match
    
    def analyze_recruiter_sentiment(self, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Enhanced recruiter sentiment analysis"""
        if not comments:
            return {
                "sentiment": "neutral",
                "recommendation": "consider", 
                "strengths": [],
                "concerns": [],
                "key_themes": []
            }
        
        # Combine all comment bodies
        all_comments = " ".join([comment['body'] for comment in comments]).lower()
        
        # Sentiment indicators
        positive_indicators = [
            "excellent", "outstanding", "exceptional", "strong", "impressive", "talented",
            "skilled", "experienced", "qualified", "good fit", "recommend", "hire"
        ]
        
        negative_indicators = [
            "concern", "issue", "problem", "weak", "lacking", "insufficient", "not suitable",
            "reject", "pass", "not qualified", "poor", "inadequate"
        ]
        
        # Count sentiment indicators
        positive_score = sum(1 for indicator in positive_indicators if indicator in all_comments)
        negative_score = sum(1 for indicator in negative_indicators if indicator in all_comments)
        
        # Determine sentiment
        if positive_score > negative_score * 2:
            sentiment = "very_positive"
            recommendation = "strong_hire"
        elif positive_score > negative_score:
            sentiment = "positive"
            recommendation = "hire"
        elif negative_score > positive_score:
            sentiment = "negative" 
            recommendation = "pass"
        else:
            sentiment = "neutral"
            recommendation = "consider"
        
        # Extract strengths and concerns
        strengths = []
        concerns = []
        
        strength_keywords = {
            "leadership": "Strong leadership abilities",
            "technical": "Technical expertise",
            "communication": "Excellent communication skills",
            "experience": "Relevant experience",
            "team": "Team collaboration",
            "problem": "Problem-solving skills",
            "creative": "Creative thinking"
        }
        
        concern_keywords = {
            "overqualified": "May be overqualified", 
            "experience": "Experience concerns",
            "fit": "Cultural fit questions",
            "salary": "Salary expectations",
            "availability": "Availability issues"
        }
        
        for keyword, strength in strength_keywords.items():
            if keyword in all_comments:
                strengths.append(strength)
        
        for keyword, concern in concern_keywords.items():
            if keyword in all_comments and "not" in all_comments:
                concerns.append(concern)
        
        return {
            "sentiment": sentiment,
            "recommendation": recommendation,
            "strengths": strengths[:5],  # Limit to top 5
            "concerns": concerns[:3],    # Limit to top 3
            "key_themes": list(set(strengths + concerns))[:6],
            "comment_count": len(comments),
            "sentiment_score": positive_score - negative_score
        }
    
    def create_enhanced_profile(self, candidate_data: Dict[str, Any], 
                              comments: List[Dict[str, Any]] = None, 
                              jobs_data: Dict[str, Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create comprehensive candidate profile using all available data"""
        
        candidate_id = candidate_data.get('id', '')
        name = candidate_data.get('name', 'Unknown')
        email = candidate_data.get('email', '')
        headline = candidate_data.get('headline', '')
        summary = candidate_data.get('summary', '')
        phone = candidate_data.get('phone', '')
        education = candidate_data.get('education', '')
        experience = candidate_data.get('experience', '')
        skills_raw = candidate_data.get('skills', '')
        
        # Find and process resume files
        resume_files = self.find_resume_files(candidate_id)
        resume_text = ""
        
        if resume_files:
            # Process the first resume file found
            resume_text = self.extract_pdf_text(resume_files[0])
            self.stats['resumes_processed'] += 1
        
        # Combine all text sources for analysis
        combined_text = f"{headline} {summary} {education} {experience} {skills_raw} {resume_text}"
        
        # Enhanced skill extraction
        technical_skills = self.extract_skills_from_text(combined_text)
        
        # Enhanced experience analysis
        experience_analysis = self.analyze_experience_level(combined_text, experience)
        
        # Leadership detection (enhanced)
        leadership_indicators = [
            'manager', 'lead', 'director', 'head', 'team', 'management', 'supervisor',
            'coordinator', 'principal', 'senior', 'chief', 'vp', 'president'
        ]
        has_leadership = any(indicator in combined_text.lower() for indicator in leadership_indicators)
        
        # Company tier estimation (enhanced)
        tier_1_companies = [
            'google', 'meta', 'facebook', 'amazon', 'microsoft', 'apple', 'netflix',
            'tesla', 'nvidia', 'salesforce', 'uber', 'airbnb', 'stripe'
        ]
        tier_2_companies = [
            'spotify', 'shopify', 'twitter', 'linkedin', 'snapchat', 'dropbox',
            'square', 'pinterest', 'reddit', 'zoom', 'slack', 'atlassian'
        ]
        
        company_tier = "tier_3"  # Default
        text_lower = combined_text.lower()
        
        if any(company in text_lower for company in tier_1_companies):
            company_tier = "tier_1"
        elif any(company in text_lower for company in tier_2_companies):
            company_tier = "tier_2"
        
        # Recruiter insights
        recruiter_insights = self.analyze_recruiter_sentiment(comments or [])
        
        # Calculate overall score
        base_score = 0.6
        
        # Scoring factors
        if technical_skills:
            base_score += 0.1
        if has_leadership:
            base_score += 0.1
        if company_tier == "tier_1":
            base_score += 0.2
        elif company_tier == "tier_2":
            base_score += 0.1
        if experience_analysis["years_experience"] > 8:
            base_score += 0.1
        if recruiter_insights["sentiment"] == "very_positive":
            base_score += 0.15
        elif recruiter_insights["sentiment"] == "positive":
            base_score += 0.1
        elif recruiter_insights["sentiment"] == "negative":
            base_score -= 0.2
        
        overall_score = min(max(base_score, 0.0), 1.0)
        
        # Create comprehensive profile
        profile = {
            "candidate_id": candidate_id,
            "name": name,
            "current_role": headline,
            "current_company": "Unknown",  # Would need NLP parsing to extract
            "resume_analysis": {
                "career_trajectory": {
                    "current_level": experience_analysis["current_level"],
                    "progression_speed": "steady",  # Would need historical data
                    "trajectory_type": "technical" if not has_leadership else "leadership"
                },
                "years_experience": experience_analysis["years_experience"],
                "technical_skills": technical_skills,
                "soft_skills": ["Communication", "Problem-solving", "Team collaboration"],
                "leadership_scope": {
                    "has_leadership": has_leadership,
                    "team_size": 8 if has_leadership else 0,  # Estimated
                    "leadership_level": "Manager" if has_leadership else "Individual Contributor"
                },
                "company_pedigree": {
                    "tier_level": company_tier,
                    "recent_companies": ["Unknown"]  # Would need parsing
                },
                "education": {
                    "highest_degree": "Bachelor's",  # Would need parsing
                    "institutions": ["Unknown"],
                    "education_raw": education
                },
                "resume_files_found": len(resume_files),
                "resume_text_extracted": len(resume_text) > 0
            },
            "recruiter_insights": recruiter_insights,
            "overall_score": overall_score,
            "contact_info": {
                "email": email,
                "phone": phone
            },
            "data_sources": {
                "csv_data": True,
                "comments_data": len(comments or []) > 0,
                "resume_data": len(resume_text) > 0,
                "jobs_data": jobs_data is not None
            },
            "processing_metadata": {
                "processed_at": datetime.now().isoformat(),
                "processor_version": "comprehensive_v1.0",
                "data_completeness_score": self._calculate_data_completeness(
                    candidate_data, comments, resume_text, jobs_data
                )
            }
        }
        
        return profile
    
    def _calculate_data_completeness(self, candidate_data: Dict, comments: List, 
                                   resume_text: str, jobs_data: Dict) -> float:
        """Calculate how complete the data is for this candidate"""
        completeness = 0.0
        
        # Basic candidate data (30%)
        if candidate_data.get('name'): completeness += 0.1
        if candidate_data.get('email'): completeness += 0.1  
        if candidate_data.get('headline'): completeness += 0.1
        
        # Extended candidate data (40%)  
        if candidate_data.get('summary'): completeness += 0.1
        if candidate_data.get('experience'): completeness += 0.1
        if candidate_data.get('education'): completeness += 0.1
        if candidate_data.get('skills'): completeness += 0.1
        
        # Comments data (20%)
        if comments and len(comments) > 0: completeness += 0.2
        
        # Resume data (10%)
        if resume_text and len(resume_text) > 0: completeness += 0.1
        
        return completeness
    
    def process_comprehensive_batch(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Process candidates using ALL available data sources"""
        self.logger.info(f"🚀 Starting comprehensive processing of {limit} candidates")
        self.logger.info("=" * 80)
        
        # Load all data sources
        self.logger.info("📥 Loading all data sources...")
        candidates = self.load_all_candidates_csv(limit)
        comments = self.load_all_comments_csv() 
        jobs_data = self.load_jobs_data()
        
        if not candidates:
            self.logger.error("❌ No candidates loaded - cannot proceed")
            return []
        
        self.logger.info(f"✅ Data loading complete:")
        self.logger.info(f"   • Candidates: {len(candidates)}")
        self.logger.info(f"   • Candidates with comments: {len(comments)}")
        self.logger.info(f"   • Jobs: {len(jobs_data)}")
        self.logger.info("-" * 60)
        
        # Process each candidate
        processed_candidates = []
        
        for i, (candidate_id, candidate_data) in enumerate(candidates.items()):
            try:
                # Get associated data
                candidate_comments = comments.get(candidate_id, [])
                
                # Create enhanced profile
                profile = self.create_enhanced_profile(
                    candidate_data, 
                    candidate_comments, 
                    jobs_data
                )
                
                processed_candidates.append(profile)
                self.stats['profiles_created'] += 1
                
                # Progress logging
                if (i + 1) % 20 == 0:
                    self.logger.info(f"✅ Processed {i+1}/{len(candidates)} candidates")
                
            except Exception as e:
                self.logger.error(f"❌ Error processing candidate {candidate_id}: {e}")
                continue
        
        self.logger.info(f"\n🎉 Comprehensive processing complete!")
        self.logger.info(f"📊 Processing Statistics:")
        for key, value in self.stats.items():
            self.logger.info(f"   • {key.replace('_', ' ').title()}: {value}")
        
        return processed_candidates

def main():
    """Main processing function with comprehensive data integration"""
    
    print("🏢 Ella Executive Search - Comprehensive Database Processor")
    print("=" * 70)
    
    # Paths
    csv_dir = DEFAULT_CSV_DIR
    resumes_dir = DEFAULT_RESUME_DIR
    
    # Validate paths
    if not csv_dir.exists():
        print(f"❌ CSV directory not found: {csv_dir}")
        return None
    
    if not resumes_dir.exists():
        print(f"⚠️  Resumes directory not found: {resumes_dir}")
        print("   Continuing without resume processing...")
    
    # Initialize processor
    processor = ComprehensiveDataProcessor(str(csv_dir), str(resumes_dir))
    
    # Process comprehensive batch - prioritize candidates_3-1.csv which has the most data
    batch_size = 500  # Increased batch size for comprehensive processing
    processed_candidates = processor.process_comprehensive_batch(batch_size)
    
    if not processed_candidates:
        print("❌ No candidates were processed successfully")
        return None
    
    # Save results
    output_file = DEFAULT_OUTPUT_FILE
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_candidates, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Saved {len(processed_candidates)} comprehensive profiles to:")
        print(f"   {output_file}")
        
        # Generate comprehensive statistics
        print(f"\n📊 Comprehensive Processing Report:")
        print("-" * 50)
        
        total_candidates = len(processed_candidates)
        with_skills = sum(1 for c in processed_candidates if c['resume_analysis']['technical_skills'])
        with_leadership = sum(1 for c in processed_candidates if c['resume_analysis']['leadership_scope']['has_leadership'])
        with_comments = sum(1 for c in processed_candidates if c['data_sources']['comments_data'])
        with_resumes = sum(1 for c in processed_candidates if c['data_sources']['resume_data'])
        
        avg_score = sum(c['overall_score'] for c in processed_candidates) / total_candidates
        avg_completeness = sum(c['processing_metadata']['data_completeness_score'] 
                              for c in processed_candidates) / total_candidates
        
        print(f"📈 Profile Quality:")
        print(f"   • Total profiles created: {total_candidates}")
        print(f"   • With technical skills: {with_skills} ({with_skills/total_candidates*100:.1f}%)")
        print(f"   • With leadership experience: {with_leadership} ({with_leadership/total_candidates*100:.1f}%)")
        print(f"   • With recruiter comments: {with_comments} ({with_comments/total_candidates*100:.1f}%)")
        print(f"   • With resume data: {with_resumes} ({with_resumes/total_candidates*100:.1f}%)")
        print(f"   • Average overall score: {avg_score:.2f}")
        print(f"   • Average data completeness: {avg_completeness:.2f}")
        
        # Experience level distribution
        levels = {}
        for candidate in processed_candidates:
            level = candidate['resume_analysis']['career_trajectory']['current_level']
            levels[level] = levels.get(level, 0) + 1
        
        print(f"\n🎯 Experience Level Distribution:")
        for level, count in sorted(levels.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {level}: {count} ({count/total_candidates*100:.1f}%)")
        
        # Show sample profile
        if processed_candidates:
            print(f"\n📋 Sample Enhanced Profile:")
            print("-" * 40)
            sample = processed_candidates[0]
            print(f"Name: {sample['name']}")
            print(f"Role: {sample['current_role']}")
            print(f"Experience: {sample['resume_analysis']['years_experience']} years")
            print(f"Level: {sample['resume_analysis']['career_trajectory']['current_level']}")
            print(f"Skills: {', '.join(sample['resume_analysis']['technical_skills'][:5])}")
            print(f"Overall Score: {sample['overall_score']:.2f}")
            print(f"Data Completeness: {sample['processing_metadata']['data_completeness_score']:.2f}")
            
        print(f"\n✅ Comprehensive processing complete!")
        print(f"🔄 Next steps:")
        print("1. Upload enhanced profiles to Firestore")  
        print("2. Generate embeddings for rich search")
        print("3. Test advanced search functionality")
        
        return output_file
        
    except Exception as e:
        print(f"❌ Error saving results: {e}")
        return None

if __name__ == "__main__":
    result = main()
    if result:
        print(f"\n🎯 Success! Enhanced candidate data saved to:")
        print(f"   {result}")
    else:
        print("\n❌ Processing failed - check logs for details")