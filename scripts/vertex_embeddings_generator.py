#!/usr/bin/env python3
"""
VertexAI Embeddings Generator for Semantic Search

Generates embeddings from enhanced candidate profiles using VertexAI text-embedding-004
for semantic similarity search in the recruitment system.
"""

import sys
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass

# Add cloud_run_worker to path for config
sys.path.append('cloud_run_worker')

try:
    from google.cloud import aiplatform
    from vertexai.language_models import TextEmbeddingModel
    import vertexai
    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False
    print("⚠️ VertexAI not available - install google-cloud-aiplatform")

try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class EmbeddingStats:
    total_profiles: int = 0
    embedded: int = 0
    failed: int = 0
    start_time: Optional[datetime] = None
    estimated_cost: float = 0.0

class VertexEmbeddingsGenerator:
    """Generate embeddings from enhanced candidate profiles using VertexAI"""
    
    def __init__(self, project_id: str = "headhunter-ai-0088", location: str = "us-central1"):
        if not VERTEX_AVAILABLE:
            raise ImportError("VertexAI not available - install google-cloud-aiplatform")
        
        self.project_id = project_id
        self.location = location
        self.model_name = "text-embedding-004"
        self.embedding_dimension = 768
        
        # Initialize VertexAI
        try:
            vertexai.init(project=project_id, location=location)
            self.embedding_model = TextEmbeddingModel.from_pretrained(self.model_name)
            logger.info(f"✅ Initialized VertexAI embeddings with {self.model_name}")
        except Exception as e:
            raise Exception(f"Failed to initialize VertexAI: {e}")
        
        # Initialize Firestore
        try:
            self.db = firestore.Client()
            self.use_firestore = True
            logger.info("✅ Connected to Firestore database")
        except Exception as e:
            logger.warning(f"⚠️ Firestore not available: {e}")
            self.db = None
            self.use_firestore = False
        
        # Cost tracking (VertexAI text-embedding-004 pricing)
        self.cost_per_character = 0.00002 / 1000  # $0.00002 per 1K characters
        self.stats = EmbeddingStats()
    
    def extract_searchable_text_from_profile(self, profile: Dict[str, Any]) -> str:
        """Extract comprehensive searchable text from enhanced candidate profile"""
        
        text_parts = []
        
        # Basic information
        if 'name' in profile:
            text_parts.append(f"Name: {profile['name']}")
        
        # Enhanced analysis sections (the rich nested data)
        enhanced_analysis = profile.get('enhanced_analysis', {})
        
        # Career trajectory information
        career_traj = enhanced_analysis.get('career_trajectory_analysis', {})
        if career_traj:
            text_parts.append(f"Current Level: {career_traj.get('current_level', '')}")
            text_parts.append(f"Career Momentum: {career_traj.get('career_momentum', '')}")
            text_parts.append(f"Progression Pattern: {career_traj.get('career_progression_pattern', '')}")
            
            # Promotion velocity details
            promo_vel = career_traj.get('promotion_velocity', {})
            if promo_vel:
                text_parts.append(f"Promotion Speed: {promo_vel.get('speed', '')}")
                text_parts.append(f"Performance Indicator: {promo_vel.get('performance_indicator', '')}")
            
            # Career highlights
            highlights = career_traj.get('trajectory_highlights', [])
            if highlights:
                text_parts.append(f"Career Highlights: {' '.join(highlights)}")
        
        # Company pedigree and experience
        company_ped = enhanced_analysis.get('company_pedigree_analysis', {})
        if company_ped:
            text_parts.append(f"Company Tier: {company_ped.get('current_company_tier', '')}")
            text_parts.append(f"Best Company: {company_ped.get('best_company_worked', '')}")
            text_parts.append(f"Brand Value: {company_ped.get('brand_value', '')}")
            
            # Company trajectory
            comp_traj = company_ped.get('company_trajectory', [])
            for comp in comp_traj:
                if isinstance(comp, dict):
                    text_parts.append(f"Experience at {comp.get('company', '')} as {comp.get('role_level', '')} for {comp.get('years', '')} years")
        
        # Domain expertise and skills
        domain_exp = enhanced_analysis.get('domain_expertise_assessment', {})
        if domain_exp:
            text_parts.append(f"Primary Domain: {domain_exp.get('primary_domain', '')}")
            text_parts.append(f"Expertise Depth: {domain_exp.get('expertise_depth', '')}")
            text_parts.append(f"Years in Domain: {domain_exp.get('years_in_domain', '')}")
            text_parts.append(f"Skills Trajectory: {domain_exp.get('technical_skills_trajectory', '')}")
            text_parts.append(f"Skill Relevance: {domain_exp.get('skill_relevance', '')}")
        
        # Leadership scope
        leadership = enhanced_analysis.get('leadership_scope_evolution', {})
        if leadership:
            text_parts.append(f"Leadership: {leadership.get('current_scope', '')}")
            text_parts.append(f"Max Team Size: {leadership.get('max_team_size_managed', '')}")
            text_parts.append(f"Leadership Growth: {leadership.get('leadership_growth_pattern', '')}")
            text_parts.append(f"Leadership Trajectory: {leadership.get('leadership_trajectory', '')}")
        
        # Performance indicators
        performance = enhanced_analysis.get('performance_indicators', {})
        if performance:
            text_parts.append(f"Performance Tier: {performance.get('estimated_performance_tier', '')}")
            text_parts.append(f"Market Positioning: {performance.get('market_positioning', '')}")
            
            # Key achievements
            achievements = performance.get('key_achievements', [])
            if achievements:
                text_parts.append(f"Key Achievements: {' '.join(achievements)}")
            
            # Competitive advantages
            advantages = performance.get('competitive_advantages', [])
            if advantages:
                text_parts.append(f"Competitive Advantages: {' '.join(advantages)}")
        
        # Cultural indicators
        cultural = enhanced_analysis.get('cultural_indicators', {})
        if cultural:
            text_parts.append(f"Work Environment Preference: {cultural.get('work_environment_preference', '')}")
            text_parts.append(f"Leadership Style: {cultural.get('leadership_style', '')}")
            text_parts.append(f"Team Fit: {cultural.get('team_fit', '')}")
            
            # Cultural values
            values = cultural.get('cultural_values', [])
            if values:
                text_parts.append(f"Cultural Values: {' '.join(values)}")
        
        # Market assessment
        market = enhanced_analysis.get('market_assessment', {})
        if market:
            text_parts.append(f"Salary Positioning: {market.get('salary_positioning', '')}")
            text_parts.append(f"Market Competitiveness: {market.get('market_competitiveness', '')}")
            text_parts.append(f"Ideal Next Role: {market.get('ideal_next_role', '')}")
            text_parts.append(f"Geographic Flexibility: {market.get('geographic_flexibility', '')}")
        
        # Recruiter verdict and insights
        verdict = enhanced_analysis.get('recruiter_verdict', {})
        if verdict:
            text_parts.append(f"Overall Rating: {verdict.get('overall_rating', '')}")
            text_parts.append(f"Recommendation: {verdict.get('recommendation', '')}")
            text_parts.append(f"One Line Pitch: {verdict.get('one_line_pitch', '')}")
            
            # Key selling points
            selling_points = verdict.get('key_selling_points', [])
            if selling_points:
                text_parts.append(f"Key Selling Points: {' '.join(selling_points)}")
            
            # Competitive differentiators
            differentiators = verdict.get('competitive_differentiators', [])
            if differentiators:
                text_parts.append(f"Unique Differentiators: {' '.join(differentiators)}")
            
            # Client fit information
            client_fit = verdict.get('client_fit', {})
            if client_fit:
                best_fit = client_fit.get('best_fit_companies', [])
                if best_fit:
                    text_parts.append(f"Best Fit Companies: {' '.join(best_fit)}")
                
                culture_req = client_fit.get('culture_requirements', [])
                if culture_req:
                    text_parts.append(f"Culture Requirements: {' '.join(culture_req)}")
        
        # Original data if enhanced_analysis is incomplete
        original_data = profile.get('original_data', {})
        if original_data and original_data.get('experience'):
            text_parts.append(f"Experience Details: {original_data['experience']}")
        
        # Join all text parts
        searchable_text = " ".join(filter(None, text_parts))
        
        # Limit text length for embedding API (max ~8000 characters for safety)
        if len(searchable_text) > 8000:
            searchable_text = searchable_text[:8000] + "..."
        
        return searchable_text
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using VertexAI"""
        try:
            # VertexAI embedding generation
            embeddings = self.embedding_model.get_embeddings([text])
            if embeddings and len(embeddings) > 0:
                embedding_vector = embeddings[0].values
                
                # Validate embedding dimension
                if len(embedding_vector) != self.embedding_dimension:
                    logger.warning(f"Unexpected embedding dimension: {len(embedding_vector)}")
                
                return embedding_vector
            else:
                logger.error("No embedding returned from VertexAI")
                return None
        
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    async def process_profile_for_embeddings(self, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single candidate profile and generate embeddings"""
        
        candidate_id = profile.get('candidate_id', 'unknown')
        
        try:
            # Extract searchable text from enhanced profile
            searchable_text = self.extract_searchable_text_from_profile(profile)
            
            if not searchable_text.strip():
                logger.warning(f"No searchable text found for candidate {candidate_id}")
                return None
            
            # Generate embedding
            embedding_vector = await self.generate_embedding(searchable_text)
            
            if embedding_vector is None:
                logger.error(f"Failed to generate embedding for candidate {candidate_id}")
                return None
            
            # Calculate cost
            char_count = len(searchable_text)
            cost = char_count * self.cost_per_character
            self.stats.estimated_cost += cost
            
            # Create embedding document
            embedding_doc = {
                'candidate_id': candidate_id,
                'embedding_vector': embedding_vector,
                'searchable_text': searchable_text,
                'text_length': char_count,
                'metadata': {
                    'model': self.model_name,
                    'dimension': len(embedding_vector),
                    'generated_at': datetime.now().isoformat(),
                    'cost_dollars': cost
                },
                'profile_summary': {
                    'name': profile.get('name', 'Unknown'),
                    'current_level': profile.get('current_level', 'Unknown'),
                    'overall_rating': profile.get('overall_rating', 'Unknown'),
                    'performance_tier': profile.get('performance_tier', 'Unknown')
                }
            }
            
            return embedding_doc
            
        except Exception as e:
            logger.error(f"Error processing profile {candidate_id}: {e}")
            self.stats.failed += 1
            return None
    
    async def get_enhanced_profiles_from_firestore(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch enhanced candidate profiles from Firestore"""
        
        if not self.use_firestore:
            logger.error("Firestore not available")
            return []
        
        try:
            # Fetch enhanced candidates that don't have embeddings yet
            profiles = []
            docs = self.db.collection('enhanced_candidates').limit(limit).stream()
            
            for doc in docs:
                profile_data = doc.to_dict()
                profile_data['candidate_id'] = doc.id
                profiles.append(profile_data)
            
            logger.info(f"✅ Fetched {len(profiles)} profiles from Firestore")
            return profiles
            
        except Exception as e:
            logger.error(f"Error fetching profiles from Firestore: {e}")
            return []
    
    async def save_embeddings_to_firestore(self, embedding_docs: List[Dict[str, Any]]) -> int:
        """Save embeddings to Firestore embeddings collection"""
        
        if not self.use_firestore or not embedding_docs:
            return 0
        
        saved_count = 0
        batch = self.db.batch()
        
        try:
            for embedding_doc in embedding_docs:
                candidate_id = embedding_doc['candidate_id']
                doc_ref = self.db.collection('candidate_embeddings').document(candidate_id)
                batch.set(doc_ref, embedding_doc)
                saved_count += 1
            
            # Commit batch
            batch.commit()
            logger.info(f"✅ Saved {saved_count} embeddings to Firestore")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error saving embeddings to Firestore: {e}")
            return 0
    
    async def generate_embeddings_batch(self, batch_size: int = 20) -> Dict[str, Any]:
        """Generate embeddings for a batch of enhanced candidate profiles"""
        
        logger.info(f"🚀 Starting embedding generation batch (size: {batch_size})")
        self.stats.start_time = datetime.now()
        
        # Fetch enhanced profiles
        profiles = await self.get_enhanced_profiles_from_firestore(limit=batch_size)
        if not profiles:
            logger.warning("No profiles found to process")
            return {'success': False, 'message': 'No profiles found'}
        
        self.stats.total_profiles = len(profiles)
        logger.info(f"📊 Processing {len(profiles)} enhanced candidate profiles")
        
        # Generate embeddings
        embedding_docs = []
        for i, profile in enumerate(profiles):
            print(f"🔄 Generating embedding {i+1}/{len(profiles)}: {profile.get('name', 'Unknown')[:30]}...", end=" ")
            
            embedding_doc = await self.process_profile_for_embeddings(profile)
            if embedding_doc:
                embedding_docs.append(embedding_doc)
                self.stats.embedded += 1
                print("✅")
            else:
                self.stats.failed += 1
                print("❌")
            
            # Small delay to avoid rate limits
            if i < len(profiles) - 1:
                await asyncio.sleep(0.1)
        
        # Save embeddings to Firestore
        if embedding_docs:
            saved_count = await self.save_embeddings_to_firestore(embedding_docs)
            logger.info(f"💾 Saved {saved_count} embeddings to Firestore")
        
        # Calculate stats
        total_time = (datetime.now() - self.stats.start_time).total_seconds()
        success_rate = (self.stats.embedded / self.stats.total_profiles) * 100 if self.stats.total_profiles > 0 else 0
        
        result = {
            'success': True,
            'stats': {
                'total_profiles': self.stats.total_profiles,
                'embedded_successfully': self.stats.embedded,
                'failed': self.stats.failed,
                'success_rate': f"{success_rate:.1f}%",
                'total_time_seconds': total_time,
                'average_time_per_profile': total_time / self.stats.total_profiles if self.stats.total_profiles > 0 else 0,
                'estimated_cost': f"${self.stats.estimated_cost:.6f}",
                'embeddings_dimension': self.embedding_dimension,
                'model': self.model_name
            }
        }
        
        logger.info("🎉 Embedding generation completed!")
        logger.info(f"   - Success rate: {success_rate:.1f}% ({self.stats.embedded}/{self.stats.total_profiles})")
        logger.info(f"   - Total time: {total_time:.2f}s")
        logger.info(f"   - Average per profile: {total_time/self.stats.total_profiles:.2f}s")
        logger.info(f"   - Estimated cost: ${self.stats.estimated_cost:.6f}")
        
        return result

async def main():
    """Test embedding generation"""
    print("🚀 VertexAI Embeddings Generation Test")
    print("=" * 50)
    
    if not VERTEX_AVAILABLE:
        print("❌ VertexAI not available - install google-cloud-aiplatform")
        return 1
    
    try:
        # Initialize embeddings generator
        generator = VertexEmbeddingsGenerator()
        
        # Generate embeddings for batch of profiles
        result = await generator.generate_embeddings_batch(batch_size=10)
        
        if result['success']:
            print("\\n🎉 EMBEDDING GENERATION SUCCESSFUL!")
            print("✅ VertexAI embeddings ready for semantic search")
            print(f"✅ Model: {result['stats']['model']}")
            print(f"✅ Dimensions: {result['stats']['embeddings_dimension']}")
            print(f"✅ Success rate: {result['stats']['success_rate']}")
            return 0
        else:
            print("\\n❌ EMBEDDING GENERATION FAILED!")
            return 1
    
    except Exception as e:
        print(f"\\n❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)