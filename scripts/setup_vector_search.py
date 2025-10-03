#!/usr/bin/env python3
"""
Setup Vertex AI Vector Search infrastructure for candidate profile similarity matching
"""

import sys
import json
from pathlib import Path

def setup_vector_search():
    """Setup Vertex AI Vector Search index and endpoint"""
    project_id = "headhunter-ai-0088"
    region = "us-central1"
    
    print("🔍 Setting up Vertex AI Vector Search for Headhunter AI")
    print("=" * 60)
    
    # Vector Search configuration
    index_config = {
        "displayName": "headhunter-candidate-profiles",
        "description": "Vector search index for candidate profile similarity matching",
        "metadata": {
            "contentsDeltaUri": f"gs://{project_id}-embeddings",
            "config": {
                "dimensions": 768,  # Using text-embedding-004 dimensions
                "approximateNeighborsCount": 150,
                "shardSize": "SHARD_SIZE_SMALL",
                "distanceMeasureType": "COSINE_DISTANCE",
                "algorithmConfig": {
                    "treeAhConfig": {
                        "leafNodeEmbeddingCount": 500,
                        "leafNodesToSearchPercent": 7
                    }
                }
            }
        },
        "indexStats": {},
        "deployedIndexes": []
    }
    
    endpoint_config = {
        "displayName": "headhunter-search-endpoint",
        "description": "Endpoint for candidate profile vector search",
        "network": f"projects/{project_id}/global/networks/default",
        "enablePrivateServiceConnect": False
    }
    
    # Create gcloud commands for setup
    commands = [
        # Create embeddings bucket
        f"gsutil mb -p {project_id} -c STANDARD -l {region} gs://{project_id}-embeddings || echo 'Bucket exists'",
        
        # Create initial embeddings directory structure
        f"echo '[]' | gsutil cp - gs://{project_id}-embeddings/embeddings/initial.json",
        
        # Create Vector Search index
        f"""gcloud ai indexes create \\
            --project={project_id} \\
            --region={region} \\
            --display-name="headhunter-candidate-profiles" \\
            --description="Vector search index for candidate profile similarity matching" \\
            --metadata-file=<(echo '{json.dumps(index_config["metadata"])}')""",
            
        # Create Index Endpoint  
        f"""gcloud ai index-endpoints create \\
            --project={project_id} \\
            --region={region} \\
            --display-name="headhunter-search-endpoint" \\
            --description="Endpoint for candidate profile vector search" \\
            --network="projects/{project_id}/global/networks/default" """
    ]
    
    print("📋 Vector Search Setup Commands:")
    print("-" * 40)
    for i, cmd in enumerate(commands, 1):
        print(f"{i}. {cmd}")
    
    print("\n🔧 Manual Setup Instructions:")
    print("-" * 40)
    print("1. Create embeddings storage bucket:")
    print(f"   gsutil mb -p {project_id} -c STANDARD -l {region} gs://{project_id}-embeddings")
    
    print("\n2. Create Vector Search Index via Console:")
    print(f"   https://console.cloud.google.com/vertex-ai/matching-engine/indexes?project={project_id}")
    print("   - Name: headhunter-candidate-profiles")
    print("   - Region: us-central1")
    print("   - Dimensions: 768")
    print("   - Update method: Streaming")
    print("   - Distance: Cosine")
    print(f"   - Embeddings URI: gs://{project_id}-embeddings")
    
    print("\n3. Create Index Endpoint via Console:")
    print(f"   https://console.cloud.google.com/vertex-ai/matching-engine/index-endpoints?project={project_id}")
    print("   - Name: headhunter-search-endpoint")
    print("   - Region: us-central1")
    print("   - Network: default")
    
    print("\n4. Deploy Index to Endpoint:")
    print("   - After both are created, deploy the index to the endpoint")
    print("   - Set min replicas: 2")
    print("   - Machine type: e2-standard-2")
    
    return True

def create_embeddings_pipeline():
    """Create embeddings generation pipeline configuration"""
    
    pipeline_config = {
        "name": "candidate-profile-embeddings",
        "description": "Generate embeddings for candidate profiles using Vertex AI text embeddings",
        "embedding_model": "text-embedding-004",
        "dimensions": 768,
        "batch_size": 100,
        "fields_to_embed": [
            "resume_analysis.technical_skills",
            "resume_analysis.soft_skills", 
            "resume_analysis.career_trajectory.trajectory_type",
            "resume_analysis.career_trajectory.domain_expertise",
            "resume_analysis.company_pedigree.company_types",
            "recruiter_insights.strengths",
            "recruiter_insights.key_themes",
            "recruiter_insights.competitive_advantages",
            "enrichment.ai_summary",
            "enrichment.career_analysis.trajectory_insights",
            "enrichment.strategic_fit.competitive_positioning"
        ],
        "output_format": {
            "candidate_id": "string",
            "embedding_vector": "float[]",
            "embedding_text": "string", 
            "metadata": {
                "years_experience": "number",
                "current_level": "string",
                "company_tier": "string",
                "overall_score": "number",
                "updated_at": "timestamp"
            }
        }
    }
    
    config_path = Path(__file__).parent / "embeddings_config.json"
    with open(config_path, 'w') as f:
        json.dump(pipeline_config, f, indent=2)
    
    print(f"\n📄 Embeddings pipeline configuration saved to: {config_path}")
    
    return pipeline_config

def create_sample_embeddings():
    """Create sample embeddings for testing"""
    
    sample_profiles = [
        {
            "candidate_id": "sample_001",
            "embedding_text": "Senior Software Engineer with 8+ years Python, machine learning, team leadership at Google and startups",
            "metadata": {
                "years_experience": 8,
                "current_level": "Senior",
                "company_tier": "Tier1", 
                "overall_score": 0.92
            }
        },
        {
            "candidate_id": "sample_002", 
            "embedding_text": "Mid-level Frontend Developer with 5 years React, TypeScript, responsive design experience at tech companies",
            "metadata": {
                "years_experience": 5,
                "current_level": "Mid",
                "company_tier": "Tier2",
                "overall_score": 0.78
            }
        },
        {
            "candidate_id": "sample_003",
            "embedding_text": "Principal Engineer with 12+ years distributed systems, cloud architecture, technical leadership at FAANG companies",
            "metadata": {
                "years_experience": 12,
                "current_level": "Principal", 
                "company_tier": "Tier1",
                "overall_score": 0.95
            }
        }
    ]
    
    samples_path = Path(__file__).parent / "sample_embeddings.json" 
    with open(samples_path, 'w') as f:
        json.dump(sample_profiles, f, indent=2)
    
    print(f"📝 Sample embeddings saved to: {samples_path}")
    
    return sample_profiles

def main():
    """Main setup function"""
    print("🎯 Vertex AI Vector Search Setup")
    print("=" * 40)
    
    # Setup vector search infrastructure
    setup_vector_search()
    
    # Create embeddings pipeline config
    create_embeddings_pipeline()
    
    # Create sample embeddings
    create_sample_embeddings()
    
    print("\n✅ Vector Search setup configuration complete!")
    print("\n📋 Next Steps:")
    print("1. Run the gcloud commands above to create infrastructure")
    print("2. Implement embeddings generation in Cloud Functions")
    print("3. Deploy vector search integration")
    print("4. Test with sample candidate profiles")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)