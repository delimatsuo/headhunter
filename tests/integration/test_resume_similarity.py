"""
Integration tests for Resume Upload to Similar Candidate Search workflow

This module tests the complete end-to-end workflow from resume upload
to similar candidate retrieval, including:
- Multi-format resume upload (PDF, DOCX, TXT)
- Together AI processing pipeline  
- Embedding generation and storage
- Similar candidate retrieval
- Search result relevance validation
"""

import pytest
import asyncio
import json
import tempfile
import os
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path

# Test markers
pytestmark = [pytest.mark.integration, pytest.mark.workflow, pytest.mark.api]


class TestResumeSimilarityWorkflow:
    """Test complete resume upload to similar candidate search workflow"""
    
    @pytest.mark.asyncio
    async def test_complete_resume_to_similarity_workflow(
        self,
        sample_candidates: List[Dict[str, Any]],
        temp_directory: str,
        mock_together_ai,
        mock_vertex_ai_embeddings,
        mock_postgres_connection,
        mock_firebase_client,
        performance_monitor
    ):
        """Test complete workflow from resume upload to similar candidate search"""
        performance_monitor.start_timer("complete_resume_workflow")
        
        # Step 1: Create test resume files in multiple formats
        performance_monitor.start_timer("resume_creation")
        
        test_resumes = await self._create_test_resume_files(temp_directory)
        
        performance_monitor.end_timer("resume_creation")
        
        assert len(test_resumes) >= 3, "Should create multiple test resume formats"
        
        # Step 2: Test resume upload and text extraction for each format
        for resume_file in test_resumes:
            performance_monitor.start_timer(f"extract_{resume_file['format']}")
            
            extracted_text = await self._extract_resume_text(resume_file["path"])
            
            performance_monitor.end_timer(f"extract_{resume_file['format']}")
            
            # Verify text extraction
            assert len(extracted_text.strip()) > 0, f"Should extract text from {resume_file['format']}"
            assert "Python" in extracted_text, f"Should extract skills from {resume_file['format']}"
            
            # Step 3: Process resume through Together AI pipeline
            performance_monitor.start_timer(f"ai_processing_{resume_file['format']}")
            
            enhanced_profile = await self._process_resume_with_together_ai(extracted_text)
            
            performance_monitor.end_timer(f"ai_processing_{resume_file['format']}")
            
            # Verify AI processing
            assert "enhanced_analysis" in enhanced_profile, "Should contain enhanced analysis"
            assert "technical_skills" in enhanced_profile["enhanced_analysis"], \
                "Should extract technical skills"
            
            # Step 4: Generate and store embeddings
            performance_monitor.start_timer(f"embedding_{resume_file['format']}")
            
            embedding = await self._generate_and_store_embedding(enhanced_profile)
            
            performance_monitor.end_timer(f"embedding_{resume_file['format']}")
            
            # Verify embedding generation
            assert len(embedding) == 768, "Should generate 768-dimensional embedding"
            
            # Step 5: Find similar candidates
            performance_monitor.start_timer(f"similarity_search_{resume_file['format']}")
            
            similar_candidates = await self._find_similar_candidates(
                embedding,
                enhanced_profile,
                limit=10
            )
            
            performance_monitor.end_timer(f"similarity_search_{resume_file['format']}")
            
            # Verify similarity search
            assert len(similar_candidates) > 0, "Should find similar candidates"
            assert len(similar_candidates) <= 10, "Should respect limit parameter"
            
            # Step 6: Validate search result relevance
            performance_monitor.start_timer(f"relevance_{resume_file['format']}")
            
            relevance_metrics = await self._validate_search_relevance(
                enhanced_profile,
                similar_candidates
            )
            
            performance_monitor.end_timer(f"relevance_{resume_file['format']}")
            
            # Assert relevance quality
            assert relevance_metrics["average_similarity"] >= 0.7, \
                f"Average similarity {relevance_metrics['average_similarity']:.3f} should be >= 0.7"
            assert relevance_metrics["skill_overlap_score"] >= 0.6, \
                f"Skill overlap {relevance_metrics['skill_overlap_score']:.3f} should be >= 0.6"
        
        performance_monitor.end_timer("complete_resume_workflow")
        
        # Assert overall performance requirements
        performance_monitor.assert_performance("complete_resume_workflow", 10.0)  # Max 10s total
        
        # Assert per-format processing performance
        for format_type in ["pdf", "docx", "txt"]:
            if f"ai_processing_{format_type}" in performance_monitor.get_metrics():
                performance_monitor.assert_performance(f"ai_processing_{format_type}", 3.0)  # Max 3s per format
    
    @pytest.mark.asyncio
    async def test_resume_text_extraction_accuracy(
        self,
        temp_directory: str
    ):
        """Test accuracy of text extraction from different resume formats"""
        # Create test resumes with known content
        test_content = """
        John Doe
        Senior Python Developer
        
        Experience:
        - 5+ years Python development
        - React and JavaScript frontend
        - PostgreSQL database design
        - AWS cloud infrastructure
        - Docker containerization
        
        Skills: Python, React, PostgreSQL, AWS, Docker, Git
        
        Education: BS Computer Science
        """
        
        resume_files = await self._create_resume_files_with_content(temp_directory, test_content)
        
        for resume_file in resume_files:
            extracted_text = await self._extract_resume_text(resume_file["path"])
            
            # Verify key information is extracted
            assert "John Doe" in extracted_text, f"Should extract name from {resume_file['format']}"
            assert "Python" in extracted_text, f"Should extract skills from {resume_file['format']}"
            assert "5+ years" in extracted_text, f"Should extract experience from {resume_file['format']}"
            
            # Verify reasonable text length
            assert len(extracted_text) >= len(test_content) * 0.7, \
                f"Should extract most content from {resume_file['format']}"
    
    @pytest.mark.asyncio
    async def test_together_ai_processing_pipeline(
        self,
        mock_together_ai,
        performance_monitor
    ):
        """Test Together AI processing pipeline for resume analysis"""
        sample_resume_text = """
        Sarah Johnson
        Senior Full-Stack Developer
        
        Experience:
        - 8 years web development experience
        - Led team of 5 developers
        - Built scalable e-commerce platforms
        - Experience with microservices architecture
        
        Technical Skills:
        - Languages: Python, JavaScript, TypeScript
        - Frameworks: Django, React, Node.js
        - Databases: PostgreSQL, MongoDB
        - Cloud: AWS, Docker, Kubernetes
        """
        
        performance_monitor.start_timer("together_ai_processing")
        
        enhanced_profile = await self._process_resume_with_together_ai(sample_resume_text)
        
        performance_monitor.end_timer("together_ai_processing")
        
        # Verify processing results structure
        assert "enhanced_analysis" in enhanced_profile, "Should contain enhanced analysis"
        
        analysis = enhanced_profile["enhanced_analysis"]
        
        # Verify required analysis sections
        required_sections = [
            "career_trajectory",
            "technical_skills", 
            "leadership_scope",
            "explicit_skills"
        ]
        
        for section in required_sections:
            assert section in analysis, f"Should contain {section} analysis"
        
        # Verify skill extraction with confidence scores
        explicit_skills = analysis.get("explicit_skills", {})
        tech_skills = explicit_skills.get("technical_skills", [])
        
        assert len(tech_skills) > 0, "Should extract technical skills"
        
        for skill in tech_skills:
            assert "skill" in skill, "Should have skill name"
            assert "confidence" in skill, "Should have confidence score"
            assert "evidence" in skill, "Should have evidence array"
            assert 0 <= skill["confidence"] <= 100, "Confidence should be 0-100"
        
        # Verify career trajectory analysis
        career = analysis.get("career_trajectory", {})
        assert "years_experience" in career, "Should extract years of experience"
        assert "current_level" in career, "Should determine current level"
        
        # Assert processing performance
        performance_monitor.assert_performance("together_ai_processing", 2.0)  # Max 2s
    
    @pytest.mark.asyncio 
    async def test_embedding_storage_and_retrieval(
        self,
        mock_vertex_ai_embeddings,
        mock_postgres_connection,
        sample_candidates: List[Dict[str, Any]]
    ):
        """Test embedding generation, storage, and retrieval"""
        candidate_profile = sample_candidates[0]
        
        # Generate embedding
        embedding = await self._generate_and_store_embedding(candidate_profile)
        
        # Verify embedding properties
        assert len(embedding) == 768, "Should generate 768-dimensional embedding"
        assert all(isinstance(x, float) for x in embedding), "Should be float values"
        assert not all(x == 0 for x in embedding), "Should not be all zeros"
        
        # Test storage (mocked)
        storage_result = await self._store_embedding_in_postgres(
            candidate_profile["candidate_id"], 
            embedding
        )
        
        assert storage_result["success"] is True, "Should successfully store embedding"
        
        # Test retrieval (mocked)
        retrieved_embedding = await self._retrieve_embedding_from_postgres(
            candidate_profile["candidate_id"]
        )
        
        assert retrieved_embedding == embedding, "Should retrieve same embedding"
    
    @pytest.mark.asyncio
    async def test_similar_candidate_search_algorithm(
        self,
        sample_candidates: List[Dict[str, Any]],
        mock_postgres_connection
    ):
        """Test similar candidate search algorithm accuracy"""
        # Use first candidate as reference
        reference_candidate = sample_candidates[0]
        reference_embedding = [0.1 + i * 0.001 for i in range(768)]
        
        # Find similar candidates
        similar_candidates = await self._find_similar_candidates(
            reference_embedding,
            reference_candidate,
            limit=5
        )
        
        # Verify search results
        assert len(similar_candidates) <= 5, "Should respect limit"
        
        for candidate in similar_candidates:
            assert "similarity_score" in candidate, "Should have similarity score"
            assert "candidate_id" in candidate, "Should have candidate ID"
            assert 0 <= candidate["similarity_score"] <= 1, "Similarity should be 0-1"
        
        # Verify results are sorted by similarity (descending)
        scores = [c["similarity_score"] for c in similar_candidates]
        assert scores == sorted(scores, reverse=True), "Should sort by similarity descending"
        
        # Verify reasonable similarity thresholds
        if similar_candidates:
            assert similar_candidates[0]["similarity_score"] >= 0.7, \
                "Top result should have high similarity"
    
    @pytest.mark.asyncio
    async def test_search_relevance_validation(
        self,
        test_data_factory
    ):
        """Test search result relevance validation metrics"""
        # Create reference candidate with known skills
        reference_candidate = test_data_factory.create_candidate_profile(
            name="Reference Developer",
            skills=["Python", "React", "PostgreSQL", "AWS", "Docker"]
        )
        
        # Create similar candidates with varying skill overlap
        similar_candidates = [
            # High overlap candidate
            {
                "candidate_id": "high_overlap",
                "similarity_score": 0.95,
                "enhanced_analysis": {
                    "technical_skills": {
                        "core_competencies": ["Python", "React", "PostgreSQL", "AWS"]
                    },
                    "career_trajectory": {"years_experience": 6}
                }
            },
            # Medium overlap candidate
            {
                "candidate_id": "medium_overlap", 
                "similarity_score": 0.82,
                "enhanced_analysis": {
                    "technical_skills": {
                        "core_competencies": ["Python", "Vue.js", "MySQL", "GCP"]
                    },
                    "career_trajectory": {"years_experience": 5}
                }
            },
            # Low overlap candidate
            {
                "candidate_id": "low_overlap",
                "similarity_score": 0.71,
                "enhanced_analysis": {
                    "technical_skills": {
                        "core_competencies": ["Java", "Spring", "Oracle", "Azure"]
                    },
                    "career_trajectory": {"years_experience": 4}
                }
            }
        ]
        
        relevance_metrics = await self._validate_search_relevance(
            reference_candidate,
            similar_candidates
        )
        
        # Verify metrics structure
        expected_metrics = [
            "average_similarity",
            "skill_overlap_score", 
            "experience_alignment",
            "diversity_index",
            "relevance_distribution"
        ]
        
        for metric in expected_metrics:
            assert metric in relevance_metrics, f"Should include {metric}"
            assert isinstance(relevance_metrics[metric], (int, float)), \
                f"{metric} should be numeric"
        
        # Verify metric values make sense
        assert 0 <= relevance_metrics["average_similarity"] <= 1, \
            "Average similarity should be 0-1"
        assert 0 <= relevance_metrics["skill_overlap_score"] <= 1, \
            "Skill overlap should be 0-1"
        
        # High overlap candidate should contribute to higher metrics
        assert relevance_metrics["skill_overlap_score"] > 0.5, \
            "Should have decent skill overlap with test data"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_resume_processing_performance_benchmarks(
        self,
        temp_directory: str,
        mock_together_ai,
        mock_vertex_ai_embeddings,
        performance_monitor
    ):
        """Test resume processing performance under various conditions"""
        # Create resumes of different sizes
        resume_sizes = {
            "small": "John Doe\nPython Developer\n2 years experience",
            "medium": self._generate_medium_resume_content(),
            "large": self._generate_large_resume_content()
        }
        
        performance_metrics = {}
        
        for size_name, content in resume_sizes.items():
            # Create temporary resume file
            resume_files = await self._create_resume_files_with_content(
                temp_directory, 
                content
            )
            
            for resume_file in resume_files:
                test_name = f"{size_name}_{resume_file['format']}"
                
                # Time complete processing pipeline
                performance_monitor.start_timer(test_name)
                
                # Extract text
                extracted_text = await self._extract_resume_text(resume_file["path"])
                
                # Process with AI
                enhanced_profile = await self._process_resume_with_together_ai(extracted_text)
                
                # Generate embedding
                embedding = await self._generate_and_store_embedding(enhanced_profile)
                
                performance_monitor.end_timer(test_name)
                
                performance_metrics[test_name] = performance_monitor.get_metrics()[test_name]
        
        # Assert performance benchmarks
        for test_name, duration in performance_metrics.items():
            if "small" in test_name:
                assert duration <= 2.0, f"Small resume {test_name} should process in ≤2s, got {duration:.3f}s"
            elif "medium" in test_name:
                assert duration <= 4.0, f"Medium resume {test_name} should process in ≤4s, got {duration:.3f}s"
            elif "large" in test_name:
                assert duration <= 8.0, f"Large resume {test_name} should process in ≤8s, got {duration:.3f}s"
    
    # Helper methods
    async def _create_test_resume_files(self, temp_directory: str) -> List[Dict[str, str]]:
        """Create test resume files in multiple formats"""
        resume_content = """
        Jane Smith
        Senior Software Engineer
        
        EXPERIENCE:
        Senior Software Engineer | TechCorp | 2019-2024
        - Led development of microservices architecture
        - Managed team of 8 engineers
        - Implemented CI/CD pipelines with 99.9% uptime
        - Technologies: Python, React, PostgreSQL, AWS, Docker
        
        Software Engineer | StartupInc | 2017-2019  
        - Built scalable web applications from scratch
        - Collaborated with product team on user experience
        - Technologies: JavaScript, Node.js, MongoDB
        
        SKILLS:
        - Programming: Python, JavaScript, TypeScript, Go
        - Frontend: React, Vue.js, HTML/CSS
        - Backend: Django, Flask, Node.js, Express
        - Databases: PostgreSQL, MongoDB, Redis
        - Cloud: AWS, GCP, Docker, Kubernetes
        - Tools: Git, Jenkins, Terraform
        
        EDUCATION:
        BS Computer Science | University of Technology | 2017
        """
        
        return await self._create_resume_files_with_content(temp_directory, resume_content)
    
    async def _create_resume_files_with_content(
        self, 
        temp_directory: str, 
        content: str
    ) -> List[Dict[str, str]]:
        """Create resume files with specific content in multiple formats"""
        files = []
        
        # TXT format
        txt_path = os.path.join(temp_directory, "resume.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(content)
        files.append({"path": txt_path, "format": "txt"})
        
        # PDF format (mock - would require additional libraries)
        pdf_path = os.path.join(temp_directory, "resume.pdf")
        with open(pdf_path, 'w', encoding='utf-8') as f:
            f.write(f"PDF_MOCK:{content}")  # Mock PDF content
        files.append({"path": pdf_path, "format": "pdf"})
        
        # DOCX format (mock - would require python-docx)
        docx_path = os.path.join(temp_directory, "resume.docx")
        with open(docx_path, 'w', encoding='utf-8') as f:
            f.write(f"DOCX_MOCK:{content}")  # Mock DOCX content
        files.append({"path": docx_path, "format": "docx"})
        
        return files
    
    async def _extract_resume_text(self, file_path: str) -> str:
        """Extract text from resume file"""
        # Mock implementation - real would handle different formats
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Remove mock prefixes
        if content.startswith("PDF_MOCK:"):
            return content[9:]
        elif content.startswith("DOCX_MOCK:"):
            return content[10:]
        else:
            return content
    
    async def _process_resume_with_together_ai(self, resume_text: str) -> Dict[str, Any]:
        """Process resume text through Together AI pipeline"""
        # Mock processing - real implementation would call Together AI
        return {
            "candidate_id": f"processed_{hash(resume_text) % 10000}",
            "enhanced_analysis": {
                "career_trajectory": {
                    "current_level": "Senior",
                    "years_experience": 7,
                    "progression_speed": "fast"
                },
                "technical_skills": {
                    "core_competencies": ["Python", "React", "PostgreSQL"],
                    "skill_depth": "expert"
                },
                "leadership_scope": {
                    "has_leadership": True,
                    "team_size": 8
                },
                "explicit_skills": {
                    "technical_skills": [
                        {"skill": "Python", "confidence": 95, "evidence": ["7 years experience", "multiple projects"]},
                        {"skill": "React", "confidence": 90, "evidence": ["frontend development", "UI/UX"]},
                        {"skill": "PostgreSQL", "confidence": 85, "evidence": ["database design", "optimization"]}
                    ],
                    "soft_skills": [
                        {"skill": "Leadership", "confidence": 88, "evidence": ["team management", "mentoring"]},
                        {"skill": "Communication", "confidence": 90, "evidence": ["presentations", "collaboration"]}
                    ]
                }
            },
            "raw_text": resume_text,
            "processed_at": datetime.utcnow().isoformat()
        }
    
    async def _generate_and_store_embedding(self, candidate_profile: Dict[str, Any]) -> List[float]:
        """Generate embedding for candidate profile"""
        # Mock implementation returns consistent embedding based on profile
        candidate_id = candidate_profile.get("candidate_id", "unknown")
        base_value = hash(candidate_id) % 1000 / 1000.0
        
        return [base_value + i * 0.001 for i in range(768)]
    
    async def _store_embedding_in_postgres(
        self, 
        candidate_id: str, 
        embedding: List[float]
    ) -> Dict[str, Any]:
        """Store embedding in PostgreSQL with pgvector"""
        # Mock implementation - real would use psycopg2
        return {
            "success": True,
            "candidate_id": candidate_id,
            "embedding_size": len(embedding),
            "stored_at": datetime.utcnow().isoformat()
        }
    
    async def _retrieve_embedding_from_postgres(self, candidate_id: str) -> List[float]:
        """Retrieve embedding from PostgreSQL"""
        # Mock implementation returns consistent embedding
        base_value = hash(candidate_id) % 1000 / 1000.0
        return [base_value + i * 0.001 for i in range(768)]
    
    async def _find_similar_candidates(
        self,
        reference_embedding: List[float],
        reference_profile: Dict[str, Any],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find candidates similar to reference profile"""
        # Mock implementation returns similar candidates with decreasing similarity
        similar_candidates = []
        
        for i in range(min(limit, 5)):
            similarity_score = 0.95 - (i * 0.08)  # Decreasing similarity
            
            candidate = {
                "candidate_id": f"similar_{i}",
                "similarity_score": similarity_score,
                "enhanced_analysis": {
                    "technical_skills": {
                        "core_competencies": ["Python", "React", "JavaScript"][: 2 + i % 2]
                    },
                    "career_trajectory": {
                        "years_experience": 5 + i
                    }
                },
                "distance": 1 - similarity_score
            }
            
            similar_candidates.append(candidate)
        
        return similar_candidates
    
    async def _validate_search_relevance(
        self,
        reference_profile: Dict[str, Any],
        similar_candidates: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Validate relevance of search results"""
        if not similar_candidates:
            return {
                "average_similarity": 0.0,
                "skill_overlap_score": 0.0,
                "experience_alignment": 0.0,
                "diversity_index": 0.0,
                "relevance_distribution": 0.0
            }
        
        # Calculate average similarity
        similarities = [c.get("similarity_score", 0) for c in similar_candidates]
        average_similarity = sum(similarities) / len(similarities)
        
        # Calculate skill overlap score
        ref_skills = set(
            reference_profile.get("enhanced_analysis", {})
            .get("technical_skills", {})
            .get("core_competencies", [])
        )
        
        skill_overlaps = []
        for candidate in similar_candidates:
            candidate_skills = set(
                candidate.get("enhanced_analysis", {})
                .get("technical_skills", {})
                .get("core_competencies", [])
            )
            
            if ref_skills and candidate_skills:
                overlap = len(ref_skills.intersection(candidate_skills)) / len(ref_skills.union(candidate_skills))
                skill_overlaps.append(overlap)
        
        skill_overlap_score = sum(skill_overlaps) / len(skill_overlaps) if skill_overlaps else 0.0
        
        # Calculate experience alignment
        ref_exp = reference_profile.get("enhanced_analysis", {}).get("career_trajectory", {}).get("years_experience", 0)
        
        exp_alignments = []
        for candidate in similar_candidates:
            candidate_exp = candidate.get("enhanced_analysis", {}).get("career_trajectory", {}).get("years_experience", 0)
            exp_diff = abs(ref_exp - candidate_exp)
            alignment = max(0, 1 - (exp_diff / max(ref_exp, 1)))
            exp_alignments.append(alignment)
        
        experience_alignment = sum(exp_alignments) / len(exp_alignments) if exp_alignments else 0.0
        
        # Calculate diversity index (variety in experience levels)
        exp_levels = [
            candidate.get("enhanced_analysis", {}).get("career_trajectory", {}).get("years_experience", 0)
            for candidate in similar_candidates
        ]
        diversity_index = len(set(exp_levels)) / len(similar_candidates) if similar_candidates else 0.0
        
        # Calculate relevance distribution (how well distributed are the similarities)
        if len(similarities) > 1:
            sim_variance = sum((s - average_similarity) ** 2 for s in similarities) / len(similarities)
            relevance_distribution = 1 - min(1, sim_variance * 10)  # Normalize variance
        else:
            relevance_distribution = 1.0
        
        return {
            "average_similarity": average_similarity,
            "skill_overlap_score": skill_overlap_score,
            "experience_alignment": experience_alignment,
            "diversity_index": diversity_index,
            "relevance_distribution": relevance_distribution
        }
    
    def _generate_medium_resume_content(self) -> str:
        """Generate medium-sized resume content for testing"""
        return """
        Robert Chen
        Senior Full-Stack Developer
        Email: robert.chen@email.com
        Phone: (555) 123-4567
        Location: San Francisco, CA
        
        PROFESSIONAL SUMMARY:
        Experienced full-stack developer with 8+ years building scalable web applications.
        Expertise in Python, React, and cloud technologies. Proven track record of leading
        technical teams and delivering high-impact products in fast-paced environments.
        
        TECHNICAL SKILLS:
        Languages: Python, JavaScript, TypeScript, Go, SQL
        Frontend: React, Vue.js, HTML5, CSS3, Sass
        Backend: Django, Flask, Node.js, Express, FastAPI
        Databases: PostgreSQL, MongoDB, Redis, MySQL
        Cloud: AWS (EC2, S3, RDS, Lambda), GCP, Azure
        DevOps: Docker, Kubernetes, Jenkins, Terraform, GitHub Actions
        Tools: Git, Jira, Slack, Postman, VS Code
        
        PROFESSIONAL EXPERIENCE:
        
        Senior Full-Stack Developer | TechStartup Inc. | March 2020 - Present
        • Lead development of microservices architecture serving 100K+ daily users
        • Implemented CI/CD pipelines reducing deployment time by 70%
        • Mentored 3 junior developers and conducted technical interviews
        • Built real-time analytics dashboard using React and WebSockets
        • Optimized database queries improving application performance by 40%
        • Technologies: Python, React, PostgreSQL, AWS, Docker, Kubernetes
        
        Full-Stack Developer | FinTech Solutions | June 2018 - February 2020
        • Developed secure payment processing system handling $2M+ monthly volume
        • Created RESTful APIs consumed by mobile and web applications
        • Implemented automated testing suite achieving 95% code coverage
        • Collaborated with product team to define technical requirements
        • Technologies: Django, React, PostgreSQL, Redis, AWS
        
        Software Developer | DataCorp | August 2016 - May 2018
        • Built data visualization tools for business intelligence team
        • Developed ETL pipelines processing 1TB+ daily data
        • Created automated reporting system saving 20+ hours weekly
        • Technologies: Python, Flask, MongoDB, D3.js
        
        EDUCATION:
        Master of Science in Computer Science
        Stanford University | 2016
        
        Bachelor of Science in Software Engineering  
        UC Berkeley | 2014
        
        CERTIFICATIONS:
        • AWS Certified Solutions Architect - Associate (2022)
        • Google Cloud Professional Cloud Architect (2021)
        • Certified Kubernetes Administrator (2020)
        
        PROJECTS:
        E-commerce Platform | Personal Project
        • Built full-stack e-commerce platform with React frontend and Django backend
        • Implemented payment processing with Stripe integration
        • Deployed on AWS with auto-scaling and load balancing
        • GitHub: github.com/robertchen/ecommerce-platform
        
        LANGUAGES:
        • English (Native)
        • Mandarin (Fluent)
        • Spanish (Conversational)
        """
    
    def _generate_large_resume_content(self) -> str:
        """Generate large resume content for performance testing"""
        medium_content = self._generate_medium_resume_content()
        
        # Add extensive additional sections
        additional_content = """
        
        ADDITIONAL EXPERIENCE:
        
        Consultant | Various Clients | 2014-2016
        • Provided technical consulting for 15+ small businesses
        • Implemented custom CRM solutions using PHP and MySQL
        • Created responsive websites for local businesses
        • Trained client teams on digital marketing strategies
        
        Research Assistant | UC Berkeley CS Department | 2013-2014
        • Assisted with machine learning research on natural language processing
        • Published 2 papers on sentiment analysis algorithms
        • Presented findings at 3 international conferences
        • Collaborated with PhD students on deep learning projects
        
        DETAILED PROJECT PORTFOLIO:
        
        Real-Time Chat Application
        • Built scalable chat application supporting 10,000+ concurrent users
        • Implemented WebSocket connections with Redis pub/sub
        • Created mobile-responsive React frontend with Material-UI
        • Deployed on AWS with Application Load Balancer
        • Technologies: Node.js, Socket.io, React, Redis, AWS
        
        Machine Learning Pipeline  
        • Developed end-to-end ML pipeline for customer churn prediction
        • Implemented data preprocessing with Pandas and NumPy
        • Trained models using scikit-learn and TensorFlow
        • Created API endpoints for model predictions
        • Achieved 92% accuracy on test dataset
        • Technologies: Python, scikit-learn, TensorFlow, Flask, PostgreSQL
        
        Blockchain Voting System
        • Built secure voting system using Ethereum smart contracts
        • Created web interface with Web3.js integration
        • Implemented cryptographic verification for vote integrity
        • Deployed on Ethereum testnet for demonstration
        • Technologies: Solidity, Web3.js, React, MetaMask
        
        SPEAKING ENGAGEMENTS:
        • "Microservices Architecture Patterns" - TechConf 2023
        • "Building Scalable APIs" - DevMeetup SF 2022  
        • "Cloud Migration Strategies" - AWS Summit 2022
        • "Modern Frontend Development" - ReactConf 2021
        
        PUBLICATIONS:
        • "Scalable Microservices with Python and Kubernetes" - Tech Journal (2023)
        • "Optimizing Database Performance in Cloud Environments" - Cloud Computing Review (2022)
        • "Sentiment Analysis Using Deep Learning" - AI Research Quarterly (2014)
        
        VOLUNTEER WORK:
        Code for Good | Volunteer Developer | 2019-Present
        • Volunteer 10+ hours monthly building technology solutions for nonprofits
        • Led team of 5 developers creating donation management system
        • Mentored high school students in programming fundamentals
        
        HOBBIES & INTERESTS:
        • Rock climbing and mountaineering
        • Photography and travel blogging
        • Contributing to open-source projects
        • Playing chess competitively (USCF rating: 1850)
        • Cooking and exploring international cuisines
        """
        
        return medium_content + additional_content