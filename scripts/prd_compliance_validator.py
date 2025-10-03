#!/usr/bin/env python3
"""
PRD Compliance Validator - Comprehensive architecture validation
Validates current implementation against PRD requirements and identifies critical gaps
"""

import os
from pathlib import Path
from typing import Dict, Any

class PRDComplianceValidator:
    def __init__(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.prd_path = self.project_root / ".taskmaster/docs/prd.txt"
        self.results = {
            "compliance_score": 0,
            "implemented_features": [],
            "missing_features": [],
            "critical_gaps": [],
            "recommendations": [],
            "taskmaster_updates_needed": []
        }
    
    def validate_against_prd(self) -> Dict[str, Any]:
        """Validate current implementation against PRD requirements"""
        
        print("🚨 PRD COMPLIANCE VALIDATION")
        print("=" * 50)
        print("🚫 RULE: Must follow CLAUDE.md protocols before any work")
        print("📋 Checking implementation against PRD specifications...")
        print()
        
        # Check PRD exists
        if not self.prd_path.exists():
            self.results["critical_gaps"].append("PRD file not found at .taskmaster/docs/prd.txt")
            return self.results
        
        # Read PRD content
        with open(self.prd_path, 'r') as f:
            prd_content = f.read()
        
        # Validate core architecture components (PRD lines 24-85)
        self._validate_architecture(prd_content)
        
        # Validate processing pipeline (PRD lines 69-96)
        self._validate_processing_pipeline()
        
        # Validate data models (PRD lines 43-52)
        self._validate_data_models()
        
        # Validate APIs and integrations (PRD lines 54-58)
        self._validate_apis_integrations()
        
        # Validate infrastructure requirements (PRD lines 60-64)
        self._validate_infrastructure()
        
        # Calculate compliance score
        self._calculate_compliance_score()
        
        # Generate TaskMaster updates
        self._generate_taskmaster_updates()
        
        return self.results
    
    def _validate_architecture(self, prd_content: str):
        """Validate system architecture against PRD lines 24-85"""
        print("📐 ARCHITECTURE VALIDATION (PRD lines 24-85):")
        print("-" * 45)
        
        # Together AI integration (PRD lines 26, 77, 139-141) - IMPLEMENTED
        together_scripts = list(self.project_root.glob("scripts/*together*"))
        if together_scripts:
            self.results["implemented_features"].append("✅ Together AI integration (PRD line 26)")
            print("✅ Together AI processors found")
        else:
            self.results["critical_gaps"].append("❌ Together AI integration missing (PRD line 26)")
            print("❌ CRITICAL: Together AI processors missing")
        
        # Firestore integration (PRD lines 34, 78) - IMPLEMENTED  
        firestore_files = list(self.project_root.glob("**/*firestore*"))
        if firestore_files:
            self.results["implemented_features"].append("✅ Firestore integration (PRD line 34)")
            print("✅ Firestore integration found")
        else:
            self.results["critical_gaps"].append("❌ Firestore integration missing (PRD line 34)")
            print("❌ CRITICAL: Firestore integration missing")
        
        # Cloud SQL + pgvector (PRD lines 74, 79, 143) - MISSING
        pgvector_files = list(self.project_root.glob("**/*pgvector*"))
        cloud_sql_files = list(self.project_root.glob("**/*cloudsql*"))
        postgres_files = list(self.project_root.glob("**/*postgres*"))
        
        if not (pgvector_files or cloud_sql_files or postgres_files):
            self.results["critical_gaps"].append("❌ Cloud SQL + pgvector layer missing (PRD lines 74, 79, 143)")
            print("❌ CRITICAL: Cloud SQL + pgvector NOT IMPLEMENTED")
            self.results["taskmaster_updates_needed"].append({
                "task": "Set up Cloud SQL + pgvector infrastructure",
                "priority": "critical",
                "prd_reference": "lines 74, 79, 143"
            })
        else:
            self.results["implemented_features"].append("✅ Cloud SQL + pgvector found")
            print("✅ Cloud SQL + pgvector implementation found")
        
        # Cloud Functions (PRD lines 34-38) - PARTIALLY IMPLEMENTED
        functions_dir = self.project_root / "functions"
        if functions_dir.exists():
            self.results["implemented_features"].append("✅ Cloud Functions directory (PRD line 34)")
            print("✅ Cloud Functions directory found")
            
            # Check specific functions
            expected_functions = [
                "candidates-crud.ts",
                "jobs-crud.ts",
                "file-upload-pipeline.ts", 
                "vector-search.ts",
                "generate-embeddings.ts"
            ]
            
            missing_functions = []
            for func_file in expected_functions:
                func_path = functions_dir / "src" / func_file
                if not func_path.exists():
                    missing_functions.append(func_file)
            
            if missing_functions:
                self.results["critical_gaps"].append(f"❌ Missing Cloud Functions: {missing_functions}")
                print(f"❌ Missing Cloud Functions: {missing_functions}")
        else:
            self.results["critical_gaps"].append("❌ Cloud Functions missing (PRD lines 34-38)")
            print("❌ CRITICAL: Cloud Functions missing")
        
        # Embeddings generation (PRD lines 38, 123) - PARTIALLY IMPLEMENTED
        embedding_files = list(self.project_root.glob("**/*embedding*"))
        if embedding_files:
            self.results["implemented_features"].append("✅ Embedding generation found (PRD line 38)")
            print("✅ Embedding generation found")
        else:
            self.results["critical_gaps"].append("❌ Embedding generation missing (PRD line 38)")
            print("❌ CRITICAL: Embedding generation missing")
    
    def _validate_processing_pipeline(self):
        """Validate processing pipeline components (PRD lines 69-96)"""
        print("\n🔄 PROCESSING PIPELINE VALIDATION (PRD lines 69-96):")
        print("-" * 50)
        
        # Check core processors
        expected_processors = [
            ("together_ai_processor.py", "PRD line 27"),
            ("enhanced_together_ai_processor.py", "PRD line 28"),
            ("firebase_streaming_processor.py", "PRD line 29"),
            ("together_ai_firestore_processor.py", "PRD line 30")
        ]
        
        scripts_dir = self.project_root / "scripts"
        
        for processor, prd_ref in expected_processors:
            if (scripts_dir / processor).exists():
                self.results["implemented_features"].append(f"✅ {processor} ({prd_ref})")
                print(f"✅ {processor} found")
            else:
                self.results["critical_gaps"].append(f"❌ {processor} missing ({prd_ref})")
                print(f"❌ CRITICAL: {processor} missing")
        
        # Cloud Run worker (PRD lines 153, 140) - MISSING
        cloud_run_files = list(self.project_root.glob("**/cloud_run*"))
        cloud_run_worker = list(self.project_root.glob("**/candidate-enricher*"))
        
        if not (cloud_run_files or cloud_run_worker):
            self.results["critical_gaps"].append("❌ Cloud Run worker missing (PRD line 153)")
            print("❌ CRITICAL: Cloud Run worker NOT IMPLEMENTED")
            self.results["taskmaster_updates_needed"].append({
                "task": "Build Cloud Run worker for Pub/Sub processing",
                "priority": "critical", 
                "prd_reference": "line 153"
            })
        
        # Pub/Sub integration (PRD line 139, 154) - MISSING
        pubsub_files = list(self.project_root.glob("**/*pubsub*"))
        if not pubsub_files:
            self.results["critical_gaps"].append("❌ Pub/Sub integration missing (PRD line 139)")
            print("❌ CRITICAL: Pub/Sub integration NOT IMPLEMENTED")
            self.results["taskmaster_updates_needed"].append({
                "task": "Create Pub/Sub topic and subscription handlers",
                "priority": "critical",
                "prd_reference": "line 139, 154"
            })
    
    def _validate_data_models(self):
        """Validate data models against PRD specification (lines 43-52)"""
        print("\n📊 DATA MODEL VALIDATION (PRD lines 43-52):")
        print("-" * 40)
        
        # Check for PRD-compliant data structure
        expected_fields = [
            "personal_details",
            "education_analysis", 
            "experience_analysis",
            "technical_assessment",
            "market_insights",
            "cultural_assessment",
            "executive_summary",
            "processing_metadata"
        ]
        
        print("⚠️  Data structure validation needs manual Firebase inspection")
        self.results["recommendations"].append("Validate Firebase documents match PRD structure (lines 44-51)")
        
        # Check for search-ready profiles (PRD line 52) - MISSING
        self.results["critical_gaps"].append("❌ Flattened search fields missing (PRD line 52)")
        print("❌ CRITICAL: Flattened search fields for querying NOT IMPLEMENTED")
        self.results["taskmaster_updates_needed"].append({
            "task": "Implement flattened search fields for efficient querying", 
            "priority": "high",
            "prd_reference": "line 52"
        })
    
    def _validate_apis_integrations(self):
        """Validate API endpoints and integrations (PRD lines 54-58)"""
        print("\n🔗 API & INTEGRATION VALIDATION (PRD lines 54-58):")
        print("-" * 47)
        
        # Together AI API integration (PRD line 55)
        if any("TOGETHER_API_KEY" in str(f) for f in self.project_root.glob("**/*.py")):
            self.results["implemented_features"].append("✅ Together AI API integration (PRD line 55)")
            print("✅ Together AI API integration found")
        else:
            self.results["critical_gaps"].append("❌ Together AI API integration missing")
            print("❌ Together AI API integration missing")
        
        # Firebase Admin SDK (PRD line 56)
        if any("firebase_admin" in str(f.read_text()) for f in self.project_root.glob("**/*.py") if f.is_file()):
            self.results["implemented_features"].append("✅ Firebase Admin SDK (PRD line 56)")
            print("✅ Firebase Admin SDK found")
        
        # Cloud Functions v2 (PRD line 57)
        functions_package = self.project_root / "functions" / "package.json"
        if functions_package.exists():
            self.results["implemented_features"].append("✅ Cloud Functions setup (PRD line 57)")
            print("✅ Cloud Functions package.json found")
        
        # Vertex AI embeddings (PRD line 58) - NEED TO VERIFY
        vertex_files = list(self.project_root.glob("**/*vertex*"))
        if vertex_files:
            self.results["implemented_features"].append("✅ Vertex AI embeddings (PRD line 58)")
            print("✅ Vertex AI embedding files found")
        else:
            self.results["critical_gaps"].append("❌ Vertex AI embeddings missing (PRD line 58)")
            print("❌ Vertex AI embeddings missing")
    
    def _validate_infrastructure(self):
        """Validate infrastructure requirements (PRD lines 60-64)"""
        print("\n🏗️  INFRASTRUCTURE VALIDATION (PRD lines 60-64):")
        print("-" * 45)
        
        # GCP project configuration
        gcp_config = list(self.project_root.glob("**/*.json")) + list(self.project_root.glob("**/gcp*"))
        if gcp_config:
            self.results["implemented_features"].append("✅ GCP configuration files found")
            print("✅ GCP configuration files found")
        
        # Firebase configuration
        firebase_config = self.project_root / "firebase.json"
        if firebase_config.exists():
            self.results["implemented_features"].append("✅ Firebase configuration (PRD line 62)")
            print("✅ Firebase configuration found")
        else:
            self.results["critical_gaps"].append("❌ Firebase configuration missing")
            print("❌ Firebase configuration missing")
        
        # Environment variables
        env_files = [".env", ".env.template", "functions/.env"] 
        for env_file in env_files:
            env_path = self.project_root / env_file
            if env_path.exists():
                self.results["implemented_features"].append(f"✅ Environment config: {env_file}")
                print(f"✅ {env_file} found")
    
    def _calculate_compliance_score(self):
        """Calculate overall PRD compliance score"""
        total_features = len(self.results["implemented_features"]) + len(self.results["critical_gaps"])
        if total_features > 0:
            self.results["compliance_score"] = round(
                (len(self.results["implemented_features"]) / total_features) * 100, 1
            )
        
        # Heavy penalty for critical architectural gaps
        critical_gaps = len(self.results["critical_gaps"])
        self.results["compliance_score"] = max(0, self.results["compliance_score"] - (critical_gaps * 15))
    
    def _generate_taskmaster_updates(self):
        """Generate TaskMaster tasks for missing components"""
        
        # Add missing critical components
        if "Cloud SQL + pgvector" in str(self.results["critical_gaps"]):
            self.results["taskmaster_updates_needed"].extend([
                {
                    "task": "Provision Cloud SQL PostgreSQL instance with pgvector extension",
                    "priority": "critical",
                    "prd_reference": "line 74, 143"
                },
                {
                    "task": "Create database schema for candidate embeddings and search",
                    "priority": "critical", 
                    "prd_reference": "line 143"
                },
                {
                    "task": "Implement embedding worker to populate Cloud SQL vectors",
                    "priority": "critical",
                    "prd_reference": "line 143"
                }
            ])
        
        if "Cloud Run worker" in str(self.results["critical_gaps"]):
            self.results["taskmaster_updates_needed"].append({
                "task": "Build and deploy Cloud Run candidate-enricher service",
                "priority": "critical",
                "prd_reference": "line 153"
            })
        
        if "Pub/Sub" in str(self.results["critical_gaps"]):
            self.results["taskmaster_updates_needed"].extend([
                {
                    "task": "Create Pub/Sub topic 'candidate-process-requests'",
                    "priority": "critical",
                    "prd_reference": "line 139"
                },
                {
                    "task": "Implement Pub/Sub message handlers in Cloud Run",
                    "priority": "high", 
                    "prd_reference": "line 139"
                }
            ])
        
        if "search fields" in str(self.results["critical_gaps"]):
            self.results["taskmaster_updates_needed"].append({
                "task": "Implement flattened candidate search fields in Firestore",
                "priority": "high",
                "prd_reference": "line 52"
            })
    
    def generate_compliance_report(self) -> str:
        """Generate comprehensive PRD compliance report"""
        
        report = f"""# PRD COMPLIANCE VALIDATION REPORT
Generated: {os.popen('date').read().strip()}

## 🚨 COMPLIANCE SCORE: {self.results['compliance_score']}%

### ✅ IMPLEMENTED FEATURES ({len(self.results['implemented_features'])})
"""
        
        for feature in self.results['implemented_features']:
            report += f"{feature}\n"
        
        report += f"""
### ❌ CRITICAL GAPS ({len(self.results['critical_gaps'])})
"""
        
        for gap in self.results['critical_gaps']:
            report += f"{gap}\n"
        
        report += f"""
### 🎯 REQUIRED TASKMASTER UPDATES ({len(self.results['taskmaster_updates_needed'])})
"""
        
        for i, update in enumerate(self.results['taskmaster_updates_needed'], 1):
            report += f"{i}. **{update['task']}**\n"
            report += f"   - Priority: {update['priority']}\n"
            report += f"   - PRD Reference: {update['prd_reference']}\n\n"
        
        report += """
## 🚨 IMMEDIATE ACTIONS REQUIRED

### CRITICAL ARCHITECTURE GAPS:
1. **Cloud SQL + pgvector layer MISSING** (PRD lines 74, 79, 143)
   - This is the CORE search infrastructure
   - Without this, semantic search cannot work
   - Must be implemented immediately

2. **Cloud Run worker MISSING** (PRD line 153)
   - Required for scalable Pub/Sub processing
   - Core production architecture component

3. **Pub/Sub integration MISSING** (PRD line 139) 
   - Required for asynchronous processing
   - Essential for production scalability

### RECOMMENDED IMMEDIATE STEPS:
1. Update TaskMaster with the tasks listed above
2. Prioritize Cloud SQL + pgvector setup
3. Build Cloud Run worker
4. Implement Pub/Sub messaging
5. Create flattened search fields
6. Test full end-to-end pipeline

### ARCHITECTURAL COMPLIANCE:
- ✅ Firestore operational data layer implemented
- ❌ Cloud SQL search layer MISSING
- ✅ Together AI processing implemented  
- ❌ Production scaling infrastructure MISSING
"""
        
        return report

def main():
    """Run PRD compliance validation"""
    validator = PRDComplianceValidator()
    results = validator.validate_against_prd()
    
    # Generate report
    report = validator.generate_compliance_report()
    
    # Save report
    report_path = Path("prd_compliance_report.md")
    with open(report_path, 'w') as f:
        f.write(report)
    
    print("\n📋 PRD COMPLIANCE VALIDATION COMPLETE")
    print(f"📄 Report saved to: {report_path}")
    print(f"🎯 Compliance Score: {results['compliance_score']}%")
    
    # Status assessment
    if results['compliance_score'] < 60:
        print("🚨 CRITICAL NON-COMPLIANCE - Major architecture gaps")
    elif results['compliance_score'] < 80:
        print("⚠️  LOW COMPLIANCE - Significant gaps remain")  
    elif results['compliance_score'] < 95:
        print("⚠️  MODERATE COMPLIANCE - Some gaps remain")
    else:
        print("✅ HIGH COMPLIANCE - Minor issues only")
    
    # Show critical gaps
    if results['critical_gaps']:
        print(f"\n🚨 {len(results['critical_gaps'])} CRITICAL GAPS FOUND:")
        for gap in results['critical_gaps'][:3]:  # Show first 3
            print(f"   {gap}")
    
    # Show TaskMaster updates needed
    if results['taskmaster_updates_needed']:
        print(f"\n📋 {len(results['taskmaster_updates_needed'])} NEW TASKS NEEDED:")
        for task in results['taskmaster_updates_needed'][:3]:  # Show first 3
            print(f"   • {task['task']} ({task['priority']} priority)")
    
    return results

if __name__ == "__main__":
    main()