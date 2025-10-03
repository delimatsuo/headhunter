#!/usr/bin/env python3
"""
Comprehensive Workflow Validation Test
Tests the complete headhunter pipeline with 50 candidates and model bake-offs
"""

import asyncio
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import statistics
import pandas as pd

# Import our modules
from embedding_service import EmbeddingService
from llm_processor import LLMProcessor
from together_ai_processor import TogetherAIProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WorkflowValidator:
    """Validates the complete headhunter workflow with comprehensive testing"""
    
    def __init__(self):
        self.results = {
            "workflow_test": {},
            "embedding_bakeoff": {},
            "enhancement_bakeoff": {},
            "performance_metrics": {},
            "cost_analysis": {}
        }
        self.test_data = []
        
    async def load_test_data(self, num_candidates: int = 50) -> List[Dict[str, Any]]:
        """Load test candidates for validation"""
        logger.info(f"Loading {num_candidates} test candidates...")
        
        # Load from multiple sources
        test_files = [
            "tests/sample_candidate_data.csv",
            "scripts/sample_candidates.csv",
            "CSV files/505039_Ella_Executive_Search_CSVs_1"
        ]
        
        candidates = []
        
        for file_path in test_files:
            try:
                if file_path.endswith('.csv'):
                    df = pd.read_csv(file_path)
                    candidates.extend(df.to_dict('records'))
                elif Path(file_path).is_dir():
                    # Load from directory
                    csv_files = list(Path(file_path).glob('*.csv'))
                    for csv_file in csv_files[:3]:  # Limit to first 3 files
                        df = pd.read_csv(csv_file)
                        candidates.extend(df.to_dict('records'))
                        
            except Exception as e:
                logger.warning(f"Could not load {file_path}: {e}")
                continue
        
        # Standardize candidate data format
        standardized = []
        for i, candidate in enumerate(candidates[:num_candidates]):
            standardized_candidate = {
                "candidate_id": candidate.get("candidate_id", f"test_{i:03d}"),
                "name": candidate.get("name", f"Test Candidate {i}"),
                "email": candidate.get("email", f"test{i}@example.com"),
                "resume_text": candidate.get("resume_text", candidate.get("resume", "")),
                "recruiter_comments": candidate.get("recruiter_comments", candidate.get("comments", "")),
                "org_id": "test_org",
                "uploaded_at": datetime.now().isoformat(),
                "status": "pending_enrichment",
                "metadata": {
                    "source": "validation_test",
                    "test_run": datetime.now().isoformat()
                }
            }
            standardized.append(standardized_candidate)
        
        self.test_data = standardized
        logger.info(f"Loaded {len(standardized)} standardized candidates")
        return standardized

    async def test_end_to_end_workflow(self) -> Dict[str, Any]:
        """Test complete workflow with 50 candidates"""
        logger.info("=== STARTING END-TO-END WORKFLOW TEST ===")
        
        start_time = time.time()
        results = {
            "total_candidates": len(self.test_data),
            "successful_enrichments": 0,
            "failed_enrichments": 0,
            "processing_times": [],
            "error_details": [],
            "enrichment_quality_scores": [],
            "storage_success_rate": 0
        }
        
        # Initialize processors
        llm_processor = LLMProcessor()
        embedding_service = EmbeddingService(provider="vertex_ai")
        
        successful_storage = 0
        
        for i, candidate in enumerate(self.test_data):
            candidate_start = time.time()
            logger.info(f"Processing candidate {i+1}/{len(self.test_data)}: {candidate['name']}")
            
            try:
                # Step 1: Extract and process resume text
                if not candidate.get('resume_text'):
                    logger.warning(f"No resume text for {candidate['name']}, skipping")
                    results["failed_enrichments"] += 1
                    continue
                
                # Step 2: AI Enhancement via LLM
                enhancement_result = await self.process_with_llm(candidate, llm_processor)
                if not enhancement_result:
                    results["failed_enrichments"] += 1
                    continue
                
                # Step 3: Generate embeddings
                embedding_result = await self.generate_embeddings(candidate, embedding_service)
                
                # Step 4: Store in Firestore (simulate)
                storage_success = await self.simulate_firestore_storage(candidate, enhancement_result, embedding_result)
                if storage_success:
                    successful_storage += 1
                
                # Calculate quality metrics
                quality_score = self.calculate_quality_score(enhancement_result)
                results["enrichment_quality_scores"].append(quality_score)
                
                processing_time = time.time() - candidate_start
                results["processing_times"].append(processing_time)
                results["successful_enrichments"] += 1
                
                logger.info(f"✅ Processed {candidate['name']} in {processing_time:.2f}s (quality: {quality_score:.2f})")
                
            except Exception as e:
                error_detail = {
                    "candidate_id": candidate["candidate_id"],
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                results["error_details"].append(error_detail)
                results["failed_enrichments"] += 1
                logger.error(f"❌ Failed to process {candidate.get('name', 'Unknown')}: {e}")
        
        # Calculate summary metrics
        total_time = time.time() - start_time
        results["total_processing_time"] = total_time
        results["average_processing_time"] = statistics.mean(results["processing_times"]) if results["processing_times"] else 0
        results["success_rate"] = results["successful_enrichments"] / results["total_candidates"] * 100
        results["storage_success_rate"] = successful_storage / results["total_candidates"] * 100
        results["average_quality_score"] = statistics.mean(results["enrichment_quality_scores"]) if results["enrichment_quality_scores"] else 0
        results["throughput_per_minute"] = results["successful_enrichments"] / (total_time / 60)
        
        logger.info("=== WORKFLOW TEST COMPLETE ===")
        logger.info(f"Success Rate: {results['success_rate']:.1f}%")
        logger.info(f"Average Processing Time: {results['average_processing_time']:.2f}s")
        logger.info(f"Throughput: {results['throughput_per_minute']:.1f} candidates/minute")
        logger.info(f"Average Quality Score: {results['average_quality_score']:.2f}/10")
        
        self.results["workflow_test"] = results
        return results

    async def process_with_llm(self, candidate: Dict[str, Any], processor: LLMProcessor) -> Optional[Dict[str, Any]]:
        """Process candidate with LLM for enhancement"""
        try:
            # Prepare input data
            input_data = {
                "name": candidate["name"],
                "resume_text": candidate["resume_text"],
                "recruiter_comments": candidate.get("recruiter_comments", ""),
                "role_level": candidate.get("role_level", "Unknown")
            }
            
            # Process with local LLM (Ollama)
            result = await processor.process_candidate(input_data)
            return result
            
        except Exception as e:
            logger.error(f"LLM processing failed for {candidate['name']}: {e}")
            return None

    async def generate_embeddings(self, candidate: Dict[str, Any], embedding_service: EmbeddingService) -> Optional[Dict[str, Any]]:
        """Generate embeddings for candidate"""
        try:
            # Combine text for embedding
            combined_text = f"{candidate['name']} {candidate.get('resume_text', '')} {candidate.get('recruiter_comments', '')}"
            
            embedding_result = await embedding_service.generate_embedding(combined_text)
            
            return {
                "embedding": embedding_result.embedding,
                "dimensions": len(embedding_result.embedding),
                "provider": embedding_result.provider,
                "processing_time": embedding_result.processing_time
            }
            
        except Exception as e:
            logger.error(f"Embedding generation failed for {candidate['name']}: {e}")
            return None

    async def simulate_firestore_storage(self, candidate: Dict[str, Any], enhancement: Dict[str, Any], embedding: Dict[str, Any]) -> bool:
        """Simulate storing data in Firestore"""
        try:
            # In a real test, this would connect to Firestore
            # For now, just validate data structure
            storage_data = {
                "candidate_id": candidate["candidate_id"],
                "original_data": candidate,
                "enhanced_profile": enhancement,
                "embedding_data": embedding,
                "processed_at": datetime.now().isoformat()
            }
            
            # Validate required fields
            required_fields = ["candidate_id", "enhanced_profile", "embedding_data"]
            for field in required_fields:
                if field not in storage_data or not storage_data[field]:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Storage simulation failed: {e}")
            return False

    def calculate_quality_score(self, enhancement_result: Dict[str, Any]) -> float:
        """Calculate quality score for enhancement result"""
        score = 0.0
        max_score = 10.0
        
        try:
            # Check for required fields (2 points each)
            required_fields = ["career_trajectory", "skill_assessment", "cultural_signals", "executive_summary"]
            for field in required_fields:
                if field in enhancement_result and enhancement_result[field]:
                    score += 2.0
            
            # Check for data richness (1 point each)
            if enhancement_result.get("executive_summary", {}).get("overall_rating", 0) > 0:
                score += 1.0
            
            if len(enhancement_result.get("skill_assessment", {}).get("technical_skills", {}).get("core_competencies", [])) >= 3:
                score += 1.0
            
            return min(score, max_score)
            
        except Exception:
            return 0.0

    async def embedding_model_bakeoff(self) -> Dict[str, Any]:
        """Compare different embedding models"""
        logger.info("=== STARTING EMBEDDING MODEL BAKE-OFF ===")
        
        models_to_test = [
            {"provider": "vertex_ai", "model": "text-embedding-004"},
            {"provider": "together_ai", "model": "togethercomputer/m2-bert-80M-8k-retrieval"},
            {"provider": "deterministic", "model": "hash-based"}  # For consistency testing
        ]
        
        test_candidates = self.test_data[:10]  # Use first 10 for speed
        results = {}
        
        for model_config in models_to_test:
            provider = model_config["provider"]
            logger.info(f"Testing embedding provider: {provider}")
            
            try:
                embedding_service = EmbeddingService(provider=provider)
                model_results = {
                    "provider": provider,
                    "model": model_config["model"],
                    "processing_times": [],
                    "embedding_dimensions": [],
                    "success_rate": 0,
                    "errors": []
                }
                
                successful = 0
                
                for candidate in test_candidates:
                    start_time = time.time()
                    try:
                        text = f"{candidate['name']} {candidate.get('resume_text', '')}"
                        result = await embedding_service.generate_embedding(text)
                        
                        processing_time = time.time() - start_time
                        model_results["processing_times"].append(processing_time)
                        model_results["embedding_dimensions"].append(len(result.embedding))
                        successful += 1
                        
                    except Exception as e:
                        model_results["errors"].append(str(e))
                
                model_results["success_rate"] = (successful / len(test_candidates)) * 100
                model_results["avg_processing_time"] = statistics.mean(model_results["processing_times"]) if model_results["processing_times"] else 0
                model_results["avg_dimensions"] = statistics.mean(model_results["embedding_dimensions"]) if model_results["embedding_dimensions"] else 0
                
                results[provider] = model_results
                logger.info(f"✅ {provider}: {model_results['success_rate']:.1f}% success, {model_results['avg_processing_time']:.3f}s avg")
                
            except Exception as e:
                logger.error(f"❌ Failed to test {provider}: {e}")
                results[provider] = {"error": str(e)}
        
        self.results["embedding_bakeoff"] = results
        return results

    async def enhancement_model_bakeoff(self) -> Dict[str, Any]:
        """Compare different enhancement models"""
        logger.info("=== STARTING ENHANCEMENT MODEL BAKE-OFF ===")
        
        # Models to test (would need API keys configured)
        models_to_test = [
            {"name": "ollama_llama", "processor": "llm_processor"},
            {"name": "together_ai_llama", "processor": "together_ai_processor"},
            # {"name": "claude_sonnet", "processor": "claude_processor"},  # Would need implementation
            # {"name": "gpt4", "processor": "openai_processor"}  # Would need implementation
        ]
        
        test_candidates = self.test_data[:5]  # Use first 5 for speed
        results = {}
        
        for model_config in models_to_test:
            model_name = model_config["name"]
            logger.info(f"Testing enhancement model: {model_name}")
            
            try:
                # Initialize processor based on type
                if model_config["processor"] == "llm_processor":
                    processor = LLMProcessor()
                elif model_config["processor"] == "together_ai_processor":
                    processor = TogetherAIProcessor()
                else:
                    logger.warning(f"Processor {model_config['processor']} not implemented, skipping")
                    continue
                
                model_results = {
                    "model_name": model_name,
                    "processing_times": [],
                    "quality_scores": [],
                    "success_rate": 0,
                    "errors": []
                }
                
                successful = 0
                
                for candidate in test_candidates:
                    start_time = time.time()
                    try:
                        # Process candidate
                        if hasattr(processor, 'process_candidate'):
                            result = await processor.process_candidate({
                                "name": candidate["name"],
                                "resume_text": candidate.get("resume_text", ""),
                                "recruiter_comments": candidate.get("recruiter_comments", "")
                            })
                        else:
                            # Fallback for different processor interfaces
                            result = await processor.enrich_candidate(candidate)
                        
                        processing_time = time.time() - start_time
                        quality_score = self.calculate_quality_score(result)
                        
                        model_results["processing_times"].append(processing_time)
                        model_results["quality_scores"].append(quality_score)
                        successful += 1
                        
                    except Exception as e:
                        model_results["errors"].append(str(e))
                        logger.warning(f"Model {model_name} failed for {candidate['name']}: {e}")
                
                model_results["success_rate"] = (successful / len(test_candidates)) * 100
                model_results["avg_processing_time"] = statistics.mean(model_results["processing_times"]) if model_results["processing_times"] else 0
                model_results["avg_quality_score"] = statistics.mean(model_results["quality_scores"]) if model_results["quality_scores"] else 0
                
                results[model_name] = model_results
                logger.info(f"✅ {model_name}: {model_results['success_rate']:.1f}% success, quality: {model_results['avg_quality_score']:.1f}/10")
                
            except Exception as e:
                logger.error(f"❌ Failed to test {model_name}: {e}")
                results[model_name] = {"error": str(e)}
        
        self.results["enhancement_bakeoff"] = results
        return results

    def analyze_costs(self) -> Dict[str, Any]:
        """Analyze costs for different model combinations"""
        logger.info("=== COST ANALYSIS ===")
        
        # Estimated costs per 1000 candidates (based on typical pricing)
        cost_estimates = {
            "embedding_models": {
                "vertex_ai": {"cost_per_1k": 0.025, "description": "Google Text Embedding 004"},
                "together_ai": {"cost_per_1k": 0.008, "description": "Together AI M2-BERT"},
                "deterministic": {"cost_per_1k": 0.000, "description": "Hash-based (free)"}
            },
            "enhancement_models": {
                "ollama_llama": {"cost_per_1k": 0.000, "description": "Local Ollama (free)"},
                "together_ai_llama": {"cost_per_1k": 2.00, "description": "Together AI Llama 3.1 8B"},
                "claude_sonnet": {"cost_per_1k": 15.00, "description": "Claude 3.5 Sonnet"},
                "gpt4": {"cost_per_1k": 30.00, "description": "GPT-4"}
            }
        }
        
        # Calculate combinations
        combinations = []
        for embed_name, embed_cost in cost_estimates["embedding_models"].items():
            for enhance_name, enhance_cost in cost_estimates["enhancement_models"].items():
                total_cost = embed_cost["cost_per_1k"] + enhance_cost["cost_per_1k"]
                combinations.append({
                    "embedding_model": embed_name,
                    "enhancement_model": enhance_name,
                    "cost_per_1k_candidates": total_cost,
                    "cost_per_10k_candidates": total_cost * 10,
                    "monthly_cost_estimate": total_cost * 30  # Assuming 30k candidates/month
                })
        
        # Sort by cost
        combinations.sort(key=lambda x: x["cost_per_1k_candidates"])
        
        cost_analysis = {
            "cost_estimates": cost_estimates,
            "model_combinations": combinations,
            "recommendations": {
                "lowest_cost": combinations[0],
                "best_value": None,  # Would be determined by quality/cost ratio
                "highest_quality": None  # Would be determined by bake-off results
            }
        }
        
        self.results["cost_analysis"] = cost_analysis
        return cost_analysis

    def generate_report(self) -> str:
        """Generate comprehensive validation report"""
        report = []
        report.append("# HEADHUNTER WORKFLOW VALIDATION REPORT")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("=" * 50)
        
        # Workflow Test Results
        if "workflow_test" in self.results:
            wf = self.results["workflow_test"]
            report.append("\n## END-TO-END WORKFLOW TEST")
            report.append(f"• Total Candidates Tested: {wf.get('total_candidates', 0)}")
            report.append(f"• Success Rate: {wf.get('success_rate', 0):.1f}%")
            report.append(f"• Average Processing Time: {wf.get('average_processing_time', 0):.2f}s")
            report.append(f"• Throughput: {wf.get('throughput_per_minute', 0):.1f} candidates/minute")
            report.append(f"• Average Quality Score: {wf.get('average_quality_score', 0):.2f}/10")
            report.append(f"• Storage Success Rate: {wf.get('storage_success_rate', 0):.1f}%")
        
        # Embedding Bake-off Results
        if "embedding_bakeoff" in self.results:
            report.append("\n## EMBEDDING MODEL BAKE-OFF")
            for provider, results in self.results["embedding_bakeoff"].items():
                if "error" not in results:
                    report.append(f"• {provider.upper()}:")
                    report.append(f"  - Success Rate: {results.get('success_rate', 0):.1f}%")
                    report.append(f"  - Avg Processing Time: {results.get('avg_processing_time', 0):.3f}s")
                    report.append(f"  - Avg Dimensions: {results.get('avg_dimensions', 0):.0f}")
        
        # Enhancement Bake-off Results
        if "enhancement_bakeoff" in self.results:
            report.append("\n## ENHANCEMENT MODEL BAKE-OFF")
            for model, results in self.results["enhancement_bakeoff"].items():
                if "error" not in results:
                    report.append(f"• {model.upper()}:")
                    report.append(f"  - Success Rate: {results.get('success_rate', 0):.1f}%")
                    report.append(f"  - Avg Processing Time: {results.get('avg_processing_time', 0):.2f}s")
                    report.append(f"  - Avg Quality Score: {results.get('avg_quality_score', 0):.1f}/10")
        
        # Cost Analysis
        if "cost_analysis" in self.results:
            ca = self.results["cost_analysis"]
            report.append("\n## COST ANALYSIS")
            report.append("Top 3 Most Cost-Effective Combinations:")
            for i, combo in enumerate(ca["model_combinations"][:3], 1):
                report.append(f"{i}. {combo['embedding_model']} + {combo['enhancement_model']}")
                report.append(f"   Cost: ${combo['cost_per_1k_candidates']:.2f}/1k candidates")
        
        return "\n".join(report)

    async def save_results(self, filename: str = None):
        """Save validation results to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"validation_results_{timestamp}.json"
        
        filepath = Path("scripts") / filename
        
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # Also save the report
        report_file = filepath.with_suffix('.md')
        with open(report_file, 'w') as f:
            f.write(self.generate_report())
        
        logger.info(f"Results saved to {filepath}")
        logger.info(f"Report saved to {report_file}")

async def main():
    """Run complete validation suite"""
    validator = WorkflowValidator()
    
    try:
        # Load test data
        await validator.load_test_data(num_candidates=50)
        
        # Run all validation tests
        await validator.test_end_to_end_workflow()
        await validator.embedding_model_bakeoff()
        await validator.enhancement_model_bakeoff()
        validator.analyze_costs()
        
        # Generate and save results
        await validator.save_results()
        
        # Print summary
        print("\n" + "="*60)
        print("VALIDATION COMPLETE!")
        print("="*60)
        print(validator.generate_report())
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())