#!/usr/bin/env python3
"""
Quick Validation Test - Tests key components with available data
"""

import asyncio
import csv
import json
import time
import logging
from datetime import datetime
from pathlib import Path
import subprocess
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuickValidator:
    """Quick validation of key components"""
    
    def __init__(self):
        self.results = {}
        
    def test_ollama_availability(self) -> bool:
        """Test if Ollama is running and available"""
        logger.info("Testing Ollama availability...")
        try:
            # Test if Ollama is running
            result = subprocess.run(['curl', '-s', 'http://localhost:11434/api/tags'], 
                                   capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                models = json.loads(result.stdout)
                logger.info(f"✅ Ollama is running with {len(models.get('models', []))} models")
                return True
            else:
                logger.warning("❌ Ollama is not responding")
                return False
        except Exception as e:
            logger.warning(f"❌ Ollama test failed: {e}")
            return False
    
    def test_embedding_service(self) -> Dict[str, Any]:
        """Test embedding service with different providers"""
        logger.info("Testing Embedding Service...")
        
        results = {}
        test_text = "Senior Software Engineer with 5 years experience in Python and React"
        
        # Test deterministic provider (should always work)
        try:
            from embedding_service import EmbeddingService
            
            service = EmbeddingService(provider="deterministic")
            start_time = time.time()
            result = asyncio.run(service.generate_embedding(test_text))
            processing_time = time.time() - start_time
            
            results["deterministic"] = {
                "success": True,
                "dimensions": len(result.embedding),
                "processing_time": processing_time,
                "provider": result.provider
            }
            logger.info(f"✅ Deterministic embedding: {len(result.embedding)} dimensions in {processing_time:.3f}s")
            
        except Exception as e:
            results["deterministic"] = {"success": False, "error": str(e)}
            logger.error(f"❌ Deterministic embedding failed: {e}")
        
        # Test VertexAI if credentials available
        try:
            service = EmbeddingService(provider="vertex_ai")
            start_time = time.time()
            result = asyncio.run(service.generate_embedding(test_text))
            processing_time = time.time() - start_time
            
            results["vertex_ai"] = {
                "success": True,
                "dimensions": len(result.embedding),
                "processing_time": processing_time,
                "provider": result.provider
            }
            logger.info(f"✅ VertexAI embedding: {len(result.embedding)} dimensions in {processing_time:.3f}s")
            
        except Exception as e:
            results["vertex_ai"] = {"success": False, "error": str(e)}
            logger.warning(f"⚠️ VertexAI embedding failed (expected if no credentials): {e}")
        
        return results
    
    def test_llm_processing(self) -> Dict[str, Any]:
        """Test LLM processing with sample data"""
        logger.info("Testing LLM Processing...")
        
        sample_candidate = {
            "name": "Sarah Chen",
            "resume_text": """Sarah Chen - Senior Software Engineer
            
Experience:
Senior Software Engineer | Google (2019-Present)
- Led architecture redesign improving performance by 40%
- Mentored 8 junior engineers, 5 promoted to senior roles
- Built distributed systems serving 100M+ users daily

Software Engineer | Microsoft (2016-2019)
- Developed cloud-native applications using Azure
- Implemented CI/CD pipelines reducing deployment time by 60%

Education:
MS Computer Science | Stanford University (2016)
BS Computer Science | UC Berkeley (2014)

Skills: Python, Java, React, TypeScript, AWS, Kubernetes, System Design""",
            "recruiter_comments": "Excellent technical leader with strong mentoring skills. Great culture fit for senior engineering roles.",
            "role_level": "Senior"
        }
        
        results = {}
        
        # Test with Ollama if available
        if self.test_ollama_availability():
            try:
                from llm_processor import LLMProcessor
                
                processor = LLMProcessor()
                start_time = time.time()
                
                # Use synchronous processing for testing
                result = processor.process_single_record(sample_candidate)
                processing_time = time.time() - start_time
                
                results["ollama_llama"] = {
                    "success": True,
                    "processing_time": processing_time,
                    "has_career_trajectory": "career_trajectory" in result,
                    "has_skills": "skill_assessment" in result,
                    "has_summary": "executive_summary" in result,
                    "overall_rating": result.get("executive_summary", {}).get("overall_rating", 0)
                }
                logger.info(f"✅ Ollama processing completed in {processing_time:.2f}s")
                
            except Exception as e:
                results["ollama_llama"] = {"success": False, "error": str(e)}
                logger.error(f"❌ Ollama processing failed: {e}")
        
        # Test Together AI if available
        try:
            # Would need Together AI processor implementation
            logger.info("⚠️ Together AI processing test skipped (not implemented)")
            results["together_ai"] = {"success": False, "error": "Not implemented"}
            
        except Exception as e:
            results["together_ai"] = {"success": False, "error": str(e)}
        
        return results
    
    def test_data_quality(self) -> Dict[str, Any]:
        """Test quality of available data"""
        logger.info("Testing data quality...")
        
        results = {"files_found": [], "candidate_count": 0, "data_quality": {}}
        
        # Check for test data files
        test_files = [
            "tests/sample_candidate_data.csv",
            "scripts/sample_candidates.csv",
            "CSV files"
        ]
        
        total_candidates = 0
        
        for file_path in test_files:
            try:
                if file_path.endswith('.csv') and Path(file_path).exists():
                    with open(file_path, 'r') as f:
                        reader = csv.DictReader(f)
                        candidates = list(reader)
                        total_candidates += len(candidates)
                        results["files_found"].append({
                            "file": file_path,
                            "count": len(candidates),
                            "fields": list(candidates[0].keys()) if candidates else []
                        })
                        logger.info(f"✅ Found {len(candidates)} candidates in {file_path}")
                        
                elif Path(file_path).is_dir():
                    csv_files = list(Path(file_path).glob('*.csv'))
                    dir_count = 0
                    for csv_file in csv_files:
                        try:
                            with open(csv_file, 'r') as f:
                                reader = csv.DictReader(f)
                                candidates = list(reader)
                                dir_count += len(candidates)
                        except:
                            continue
                    
                    if dir_count > 0:
                        total_candidates += dir_count
                        results["files_found"].append({
                            "directory": file_path,
                            "csv_files": len(csv_files),
                            "count": dir_count
                        })
                        logger.info(f"✅ Found {dir_count} candidates in {len(csv_files)} CSV files in {file_path}")
                        
            except Exception as e:
                logger.warning(f"Could not read {file_path}: {e}")
        
        results["candidate_count"] = total_candidates
        
        # Assess data quality
        if total_candidates >= 50:
            results["data_quality"]["sufficient_for_testing"] = True
            results["data_quality"]["recommendation"] = "Sufficient data for comprehensive testing"
        elif total_candidates >= 10:
            results["data_quality"]["sufficient_for_testing"] = True
            results["data_quality"]["recommendation"] = "Limited data - suitable for basic testing"
        else:
            results["data_quality"]["sufficient_for_testing"] = False
            results["data_quality"]["recommendation"] = "Insufficient data - need more test candidates"
        
        logger.info(f"Total candidates available: {total_candidates}")
        
        return results
    
    def test_firebase_connection(self) -> Dict[str, Any]:
        """Test Firebase/Firestore connection"""
        logger.info("Testing Firebase connection...")
        
        try:
            from google.cloud import firestore
            
            # Try to initialize client (may fail without credentials)
            db = firestore.Client()
            
            # Simple test - list collections (may fail without permissions)
            collections = list(db.collections())
            
            return {
                "success": True,
                "collections_found": len(collections),
                "status": "Connected"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "status": "No credentials or connection failed"
            }
    
    def run_mini_workflow_test(self) -> Dict[str, Any]:
        """Run a mini end-to-end test with 3 candidates"""
        logger.info("Running mini workflow test...")
        
        # Sample candidates for testing
        test_candidates = [
            {
                "name": "Test Engineer 1",
                "resume_text": "Software Engineer with 3 years Python experience",
                "recruiter_comments": "Strong technical skills"
            },
            {
                "name": "Test Manager 2", 
                "resume_text": "Engineering Manager with 7 years experience leading teams",
                "recruiter_comments": "Excellent leadership potential"
            },
            {
                "name": "Test Senior 3",
                "resume_text": "Senior Developer with expertise in React and Node.js",
                "recruiter_comments": "Great problem solver"
            }
        ]
        
        results = {
            "candidates_tested": len(test_candidates),
            "successful_enrichments": 0,
            "successful_embeddings": 0,
            "processing_times": [],
            "errors": []
        }
        
        for i, candidate in enumerate(test_candidates):
            logger.info(f"Processing test candidate {i+1}: {candidate['name']}")
            start_time = time.time()
            
            try:
                # Test embedding generation
                from embedding_service import EmbeddingService
                embedding_service = EmbeddingService(provider="deterministic")
                
                text = f"{candidate['name']} {candidate['resume_text']}"
                embedding_result = asyncio.run(embedding_service.generate_embedding(text))
                
                if len(embedding_result.embedding) > 0:
                    results["successful_embeddings"] += 1
                
                # Test LLM processing (if Ollama available)
                if self.test_ollama_availability():
                    from llm_processor import LLMProcessor
                    processor = LLMProcessor()
                    
                    enhancement = processor.process_single_record(candidate)
                    if enhancement and "executive_summary" in enhancement:
                        results["successful_enrichments"] += 1
                
                processing_time = time.time() - start_time
                results["processing_times"].append(processing_time)
                
                logger.info(f"✅ Processed {candidate['name']} in {processing_time:.2f}s")
                
            except Exception as e:
                error_msg = f"Failed to process {candidate['name']}: {e}"
                results["errors"].append(error_msg)
                logger.error(f"❌ {error_msg}")
        
        # Calculate summary
        results["embedding_success_rate"] = (results["successful_embeddings"] / len(test_candidates)) * 100
        results["enrichment_success_rate"] = (results["successful_enrichments"] / len(test_candidates)) * 100
        results["avg_processing_time"] = sum(results["processing_times"]) / len(results["processing_times"]) if results["processing_times"] else 0
        
        return results
    
    def generate_summary_report(self) -> str:
        """Generate summary report"""
        report = []
        report.append("# QUICK VALIDATION SUMMARY")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("=" * 50)
        
        # System checks
        report.append("\n## SYSTEM STATUS")
        report.append(f"• Ollama Available: {'✅' if self.results.get('ollama_available', False) else '❌'}")
        
        # Data quality
        if "data_quality" in self.results:
            dq = self.results["data_quality"]
            report.append(f"• Test Data Available: {dq.get('candidate_count', 0)} candidates")
            report.append(f"• Sufficient for Testing: {'✅' if dq.get('data_quality', {}).get('sufficient_for_testing', False) else '❌'}")
        
        # Embedding tests
        if "embedding_tests" in self.results:
            et = self.results["embedding_tests"]
            report.append("\n## EMBEDDING SERVICES")
            for provider, result in et.items():
                status = '✅' if result.get('success', False) else '❌'
                report.append(f"• {provider}: {status}")
        
        # LLM tests
        if "llm_tests" in self.results:
            lt = self.results["llm_tests"]
            report.append("\n## LLM PROCESSING")
            for model, result in lt.items():
                status = '✅' if result.get('success', False) else '❌'
                report.append(f"• {model}: {status}")
        
        # Mini workflow
        if "mini_workflow" in self.results:
            mw = self.results["mini_workflow"]
            report.append("\n## MINI WORKFLOW TEST")
            report.append(f"• Candidates Tested: {mw.get('candidates_tested', 0)}")
            report.append(f"• Embedding Success Rate: {mw.get('embedding_success_rate', 0):.1f}%")
            report.append(f"• Enrichment Success Rate: {mw.get('enrichment_success_rate', 0):.1f}%")
            report.append(f"• Avg Processing Time: {mw.get('avg_processing_time', 0):.2f}s")
        
        return "\n".join(report)

def main():
    """Run quick validation"""
    validator = QuickValidator()
    
    logger.info("🚀 Starting Quick Validation Test...")
    
    # Run all tests
    validator.results["ollama_available"] = validator.test_ollama_availability()
    validator.results["data_quality"] = validator.test_data_quality()
    validator.results["embedding_tests"] = validator.test_embedding_service()
    validator.results["llm_tests"] = validator.test_llm_processing()
    validator.results["firebase_test"] = validator.test_firebase_connection()
    validator.results["mini_workflow"] = validator.run_mini_workflow_test()
    
    # Generate report
    print("\n" + "="*60)
    print("QUICK VALIDATION COMPLETE!")
    print("="*60)
    print(validator.generate_summary_report())
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"scripts/quick_validation_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump(validator.results, f, indent=2, default=str)
    
    logger.info(f"Results saved to {results_file}")

if __name__ == "__main__":
    main()