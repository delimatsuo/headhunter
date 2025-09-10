# Headhunter AI - Migration Strategy: Local to Cloud

## Overview

This document outlines the complete strategy for migrating your existing local Headhunter AI system to the cloud-based CRUD architecture while maintaining 100% local AI processing.

## Migration Phases

### Phase 1: Assessment & Preparation (Week 1)
**Goal**: Analyze current data and prepare for migration

#### Data Assessment
1. **Inventory Current Data**
   ```bash
   python scripts/assess_current_data.py
   ```
   
   Creates assessment report:
   - Total candidates: 29,138
   - Processed candidates: 109 (with enhanced analysis)
   - Resume files: Count and formats
   - Analysis files: JSON structure review
   - Database size estimation

2. **Data Quality Validation**
   ```python
   # scripts/assess_current_data.py
   import os
   import json
   import glob
   from pathlib import Path
   
   def assess_data_quality():
       assessment = {
           'candidates': {
               'total_count': 0,
               'with_analysis': 0,
               'with_resume_files': 0,
               'data_issues': []
           },
           'files': {
               'resume_files': [],
               'analysis_files': [],
               'corrupted_files': []
           }
       }
       
       # Scan CSV files directory
       csv_files = glob.glob('CSV files/*.csv')
       print(f"Found {len(csv_files)} CSV files")
       
       # Scan enhanced analysis
       analysis_files = glob.glob('scripts/enhanced_analysis/*_enhanced.json')
       assessment['candidates']['with_analysis'] = len(analysis_files)
       
       # Check for missing data
       for file in analysis_files:
           try:
               with open(file, 'r') as f:
                   data = json.load(f)
                   if not data.get('enhanced_analysis'):
                       assessment['candidates']['data_issues'].append(file)
           except Exception as e:
               assessment['files']['corrupted_files'].append((file, str(e)))
       
       return assessment
   ```

3. **Infrastructure Preparation**
   - Set up Firebase project
   - Configure Cloud Storage buckets
   - Deploy initial Cloud Functions
   - Set up monitoring

### Phase 2: Data Migration (Week 2-3)
**Goal**: Migrate all existing data to cloud storage

#### Step 1: Candidate Data Migration
```python
# scripts/migrate_candidates.py
import csv
import json
import asyncio
from firebase_admin import firestore, initialize_app, credentials
from datetime import datetime

class CandidateMigrator:
    def __init__(self, org_id="default_org"):
        cred = credentials.Certificate('.gcp/headhunter-service-key.json')
        initialize_app(cred)
        self.db = firestore.client()
        self.org_id = org_id
        
    async def migrate_from_csv(self, csv_file_path):
        """Migrate candidates from CSV file"""
        migrated_count = 0
        
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            batch = self.db.batch()
            batch_count = 0
            
            for row in reader:
                candidate_data = self.transform_csv_row(row)
                doc_ref = self.db.collection('candidates').document(candidate_data['candidate_id'])
                batch.set(doc_ref, candidate_data)
                
                batch_count += 1
                if batch_count >= 500:  # Firestore batch limit
                    await batch.commit()
                    batch = self.db.batch()
                    batch_count = 0
                    migrated_count += 500
                    print(f"Migrated {migrated_count} candidates...")
            
            # Commit remaining
            if batch_count > 0:
                await batch.commit()
                migrated_count += batch_count
        
        return migrated_count
    
    def transform_csv_row(self, row):
        """Transform CSV row to Firestore document"""
        candidate_id = row.get('candidate_id') or f"migrated_{hash(row.get('name', ''))}"
        
        return {
            'candidate_id': candidate_id,
            'org_id': self.org_id,
            'created_by': 'migration_script',
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
            
            'personal': {
                'name': row.get('name', ''),
                'email': row.get('email'),
                'phone': row.get('phone'),
                'location': row.get('location'),
            },
            
            'documents': {
                'resume_text': row.get('resume_text'),
                'resume_file_name': row.get('resume_file_name'),
            },
            
            'processing': {
                'status': 'migrated',
                'local_analysis_completed': False,
                'migration_source': csv_file_path,
                'migration_date': firestore.SERVER_TIMESTAMP,
            },
            
            'searchable_data': {
                'skills_combined': [],
                'experience_level': 'unknown',
                'industries': [],
                'locations': [row.get('location')] if row.get('location') else [],
            },
            
            'interactions': {
                'views': 0,
                'bookmarks': [],
                'notes': [],
                'status_updates': [{
                    'status': 'migrated',
                    'updated_by': 'migration_script',
                    'updated_at': firestore.SERVER_TIMESTAMP,
                }],
            },
            
            'privacy': {
                'is_public': False,
                'consent_given': True,  # Assume consent for existing data
                'gdpr_compliant': True,
            },
        }
```

#### Step 2: Enhanced Analysis Migration
```python
# scripts/migrate_analysis.py
class AnalysisMigrator:
    def __init__(self):
        self.db = firestore.client()
        
    async def migrate_enhanced_analysis(self, analysis_directory):
        """Migrate existing enhanced analysis files"""
        analysis_files = glob.glob(f"{analysis_directory}/*_enhanced.json")
        migrated_count = 0
        
        for file_path in analysis_files:
            try:
                with open(file_path, 'r') as f:
                    analysis_data = json.load(f)
                
                candidate_id = analysis_data.get('candidate_id')
                if not candidate_id:
                    continue
                
                # Update candidate document with analysis
                doc_ref = self.db.collection('candidates').document(candidate_id)
                doc = doc_ref.get()
                
                if doc.exists:
                    # Transform analysis to new schema
                    transformed_analysis = self.transform_analysis(analysis_data['enhanced_analysis'])
                    
                    doc_ref.update({
                        'analysis': transformed_analysis,
                        'processing.status': 'completed',
                        'processing.local_analysis_completed': True,
                        'processing.last_processed': firestore.SERVER_TIMESTAMP,
                        'searchable_data': self.extract_searchable_data(transformed_analysis),
                        'updated_at': firestore.SERVER_TIMESTAMP,
                    })
                    
                    migrated_count += 1
                    if migrated_count % 50 == 0:
                        print(f"Migrated analysis for {migrated_count} candidates...")
                
            except Exception as e:
                print(f"Error migrating {file_path}: {e}")
                continue
        
        return migrated_count
    
    def transform_analysis(self, old_analysis):
        """Transform old analysis format to new cloud schema"""
        return {
            'career_trajectory': {
                'current_level': old_analysis.get('career_trajectory', {}).get('current_level', 'unknown'),
                'progression_speed': old_analysis.get('career_trajectory', {}).get('progression_speed', 'unknown'),
                'trajectory_type': old_analysis.get('career_trajectory', {}).get('trajectory_type', 'unknown'),
                'years_experience': old_analysis.get('career_trajectory', {}).get('years_experience', 0),
                'velocity': old_analysis.get('career_trajectory', {}).get('velocity', 'unknown'),
            },
            'leadership_scope': old_analysis.get('leadership_scope', {}),
            'company_pedigree': old_analysis.get('company_pedigree', {}),
            'cultural_signals': old_analysis.get('cultural_signals', {}),
            'skill_assessment': old_analysis.get('skill_assessment', {}),
            'recruiter_insights': old_analysis.get('recruiter_insights', {}),
            'search_optimization': old_analysis.get('search_optimization', {}),
            'executive_summary': old_analysis.get('executive_summary', {}),
        }
```

#### Step 3: File Migration to Cloud Storage
```python
# scripts/migrate_files.py
from google.cloud import storage
import os
import mimetypes

class FileMigrator:
    def __init__(self, bucket_name="headhunter-ai-0088-files"):
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(bucket_name)
        
    async def migrate_resume_files(self, local_directory, org_id="default_org"):
        """Migrate resume files to Cloud Storage"""
        migrated_files = 0
        
        for root, dirs, files in os.walk(local_directory):
            for file in files:
                if file.lower().endswith(('.pdf', '.docx', '.doc', '.txt')):
                    local_path = os.path.join(root, file)
                    
                    # Generate candidate ID from filename or path
                    candidate_id = self.extract_candidate_id(file, root)
                    
                    # Create cloud storage path
                    cloud_path = f"organizations/{org_id}/candidates/{candidate_id}/resumes/migrated_{file}"
                    
                    try:
                        # Upload file
                        blob = self.bucket.blob(cloud_path)
                        
                        # Set metadata
                        content_type = mimetypes.guess_type(local_path)[0] or 'application/octet-stream'
                        blob.metadata = {
                            'candidate-id': candidate_id,
                            'org-id': org_id,
                            'migrated-from': local_path,
                            'migration-date': datetime.now().isoformat(),
                        }
                        
                        blob.upload_from_filename(local_path, content_type=content_type)
                        
                        # Update candidate document
                        await self.update_candidate_file_info(candidate_id, cloud_path, file)
                        
                        migrated_files += 1
                        if migrated_files % 10 == 0:
                            print(f"Migrated {migrated_files} files...")
                            
                    except Exception as e:
                        print(f"Error migrating {local_path}: {e}")
                        continue
        
        return migrated_files
```

### Phase 3: System Integration (Week 4)
**Goal**: Integrate local processing with cloud storage

#### Local Processing Integration
```python
# scripts/local_cloud_integration.py
import requests
import json
from typing import Dict, Any

class LocalCloudIntegration:
    def __init__(self, cloud_functions_base_url, webhook_secret):
        self.base_url = cloud_functions_base_url
        self.webhook_secret = webhook_secret
        
    async def setup_webhook_receiver(self):
        """Set up local webhook receiver for cloud processing requests"""
        from flask import Flask, request, jsonify
        
        app = Flask(__name__)
        
        @app.route('/webhook/process-candidate', methods=['POST'])
        def process_candidate_webhook():
            # Verify webhook secret
            if request.headers.get('X-Webhook-Secret') != self.webhook_secret:
                return jsonify({'error': 'Invalid webhook secret'}), 401
            
            data = request.json
            candidate_id = data.get('candidate_id')
            resume_text = data.get('resume_text')
            callback_url = data.get('callback_url')
            processing_id = data.get('processing_id')
            
            # Process with local LLM (existing code)
            analysis_results = self.process_with_ollama(resume_text)
            
            # Send results back to cloud
            self.send_results_to_cloud(callback_url, {
                'candidate_id': candidate_id,
                'processing_id': processing_id,
                'analysis_results': analysis_results
            })
            
            return jsonify({'success': True})
        
        app.run(host='0.0.0.0', port=8080)
    
    def process_with_ollama(self, resume_text: str) -> Dict[str, Any]:
        """Process resume text with local Ollama LLM"""
        from llm_prompts import ResumeAnalyzer
        from recruiter_prompts import RecruiterCommentAnalyzer
        
        # Use existing local processing code
        analyzer = ResumeAnalyzer()
        analysis = analyzer.analyze_full_resume(resume_text)
        
        return {
            'career_trajectory': analysis.career_trajectory,
            'leadership_scope': analysis.leadership_scope,
            'company_pedigree': analysis.company_pedigree,
            'technical_skills': analysis.technical_skills,
            'soft_skills': analysis.soft_skills,
            'cultural_signals': analysis.cultural_signals,
            'years_experience': analysis.years_experience,
            'education_level': analysis.education_level,
            'industry_focus': analysis.industry_focus,
            'notable_achievements': analysis.notable_achievements,
        }
```

### Phase 4: Testing & Validation (Week 5)
**Goal**: Validate migration and test all systems

#### Migration Validation Script
```python
# scripts/validate_migration.py
class MigrationValidator:
    def __init__(self):
        self.db = firestore.client()
        self.storage_client = storage.Client()
        
    async def validate_migration(self):
        """Comprehensive migration validation"""
        report = {
            'candidates': await self.validate_candidates(),
            'files': await self.validate_files(),
            'analysis': await self.validate_analysis(),
            'processing': await self.validate_processing_pipeline(),
        }
        
        return report
    
    async def validate_candidates(self):
        """Validate candidate data migration"""
        candidates_ref = self.db.collection('candidates')
        docs = candidates_ref.stream()
        
        validation_results = {
            'total_migrated': 0,
            'missing_required_fields': [],
            'data_integrity_issues': [],
        }
        
        for doc in docs:
            data = doc.to_dict()
            validation_results['total_migrated'] += 1
            
            # Check required fields
            required_fields = ['candidate_id', 'org_id', 'personal.name']
            for field_path in required_fields:
                if not self.get_nested_field(data, field_path):
                    validation_results['missing_required_fields'].append(
                        (doc.id, field_path)
                    )
        
        return validation_results
```

### Phase 5: Production Cutover (Week 6)
**Goal**: Switch to production cloud system

#### Cutover Plan
1. **Freeze Local System** (Friday evening)
   - Stop all local processing
   - Complete final data sync
   - Backup all local data

2. **Final Migration** (Weekend)
   - Migrate any remaining data
   - Run final validation
   - Update DNS/URLs if needed

3. **Go Live** (Monday morning)
   - Enable cloud system
   - Monitor all services
   - Verify user access

4. **Post-Launch Monitoring** (Week 1)
   - 24/7 monitoring
   - Performance optimization
   - User feedback collection

## Data Mapping

### Old Schema → New Schema
```javascript
// CSV Row → Firestore Document
{
  // Old CSV columns
  "candidate_id": "12345",
  "name": "John Doe",
  "resume_text": "Software Engineer...",
  "recruiter_comments": "Great candidate..."
}

// New Firestore document
{
  "candidate_id": "12345",
  "org_id": "default_org",
  "personal": {
    "name": "John Doe",
    "email": null,
    "phone": null,
    "location": null
  },
  "documents": {
    "resume_text": "Software Engineer...",
    "resume_file_url": null,
    "resume_file_name": null
  },
  "analysis": {
    // Enhanced analysis structure
  },
  "processing": {
    "status": "migrated",
    "local_analysis_completed": false,
    "migration_source": "original_csv_file.csv"
  },
  "searchable_data": {
    "skills_combined": [],
    "experience_level": "unknown",
    "industries": [],
    "locations": []
  },
  "interactions": {
    "views": 0,
    "bookmarks": [],
    "notes": [],
    "status_updates": []
  },
  "privacy": {
    "is_public": false,
    "consent_given": true,
    "gdpr_compliant": true
  }
}
```

## Risk Mitigation

### Data Loss Prevention
1. **Multiple Backups**
   - Local system backup before migration
   - Daily cloud backups during migration
   - Point-in-time snapshots

2. **Rollback Plan**
   - Keep local system functional until validation complete
   - Ability to restore from any backup point
   - Documented rollback procedures

### Performance Issues
1. **Gradual Migration**
   - Migrate in small batches
   - Monitor system performance
   - Scale cloud resources as needed

2. **Load Testing**
   - Test with production data volume
   - Validate response times
   - Test concurrent user scenarios

### Security Concerns
1. **Data Encryption**
   - Encrypt data in transit
   - Use secure service accounts
   - Implement proper access controls

2. **Audit Trail**
   - Log all migration activities
   - Track data lineage
   - Monitor access patterns

## Migration Timeline

### Week 1: Assessment & Preparation
- **Day 1-2**: Data assessment and quality check
- **Day 3-4**: Cloud infrastructure setup
- **Day 5**: Migration scripts development and testing

### Week 2: Initial Migration
- **Day 1-3**: Migrate candidate data from CSV files
- **Day 4-5**: Migrate enhanced analysis files

### Week 3: File Migration
- **Day 1-3**: Migrate resume files to Cloud Storage
- **Day 4-5**: Set up local-cloud integration

### Week 4: Testing & Validation
- **Day 1-3**: Run migration validation scripts
- **Day 4-5**: End-to-end system testing

### Week 5: User Acceptance Testing
- **Day 1-3**: Train users on new system
- **Day 4-5**: User acceptance testing

### Week 6: Production Cutover
- **Friday evening**: Freeze local system
- **Weekend**: Final migration and validation
- **Monday**: Go live with cloud system

## Post-Migration Tasks

### Immediate (Week 1)
- Monitor system performance
- Fix any critical issues
- User support and training

### Short-term (Month 1)
- Optimize performance based on usage patterns
- Implement additional features
- Collect user feedback

### Long-term (Month 2+)
- Advanced analytics and reporting
- ML/AI feature enhancements
- Integration with other systems

## Success Metrics

### Technical Metrics
- **Data Integrity**: 99.9% of data migrated successfully
- **System Availability**: 99.5% uptime
- **Response Times**: < 2 seconds for most operations
- **Error Rate**: < 1% of requests

### Business Metrics
- **User Adoption**: 90% of users actively using new system
- **Feature Usage**: Key features being used regularly
- **User Satisfaction**: > 4/5 rating in user surveys
- **Performance Improvement**: Measurable improvements in workflow efficiency

This migration strategy ensures a smooth transition from your local system to the cloud-based CRUD architecture while maintaining all existing functionality and improving scalability and collaboration capabilities.