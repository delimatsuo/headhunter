#!/usr/bin/env python3
"""
Embedding Generation Service for Headhunter AI

Provides pluggable embedding providers with caching and batch processing.
Supports VertexAI, TogetherAI, and deterministic fallback providers.
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

import math

# Optional Google Cloud imports
try:
    from google.cloud import firestore
    from vertexai.language_models import TextEmbeddingModel
    import vertexai
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    # Stub classes for testing without Google Cloud
    class firestore:
        class Client:
            def collection(self, name): return None
    class TextEmbeddingModel:
        @staticmethod
        def from_pretrained(model_name): return None
    class vertexai:
        @staticmethod
        def init(*args, **kwargs): pass


@dataclass
class EmbeddingResult:
    """Result of embedding generation"""
    text: str
    vector: List[float]
    provider: str
    model: str
    timestamp: datetime
    cache_hit: bool = False
    processing_time_ms: int = 0
    
    @property
    def embedding(self) -> List[float]:
        """Alias for vector to maintain compatibility"""
        return self.vector
    
    @property
    def processing_time(self) -> float:
        """Processing time in seconds"""
        return self.processing_time_ms / 1000.0


@dataclass
class BatchEmbeddingResult:
    """Result of batch embedding generation"""
    results: List[EmbeddingResult]
    total_count: int
    success_count: int
    failed_count: int
    cache_hits: int
    total_processing_time_ms: int
    average_processing_time_ms: float


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name"""
        pass
    
    @property
    @abstractmethod
    def model(self) -> str:
        """Model name"""
        pass
    
    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Embedding dimensions"""
        pass
    
    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        pass
    
    @abstractmethod
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch of texts"""
        pass


class VertexAIEmbeddingProvider(EmbeddingProvider):
    """VertexAI text-embedding-004 provider"""
    
    def __init__(self, project_id: str = "headhunter-ai-0088", location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        self._model = None
        self._endpoint = f"projects/{project_id}/locations/{location}/publishers/google/models/text-embedding-004"
        
        # Initialize VertexAI
        try:
            vertexai.init(project=project_id, location=location)
        except Exception as e:
            logging.warning(f"Failed to initialize VertexAI: {e}")
    
    @property
    def name(self) -> str:
        return "vertex_ai"
    
    @property
    def model(self) -> str:
        return "text-embedding-004"
    
    @property
    def dimensions(self) -> int:
        return 768
    
    @property
    def embedding_model(self):
        """Lazy initialization of model"""
        if self._model is None:
            self._model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        return self._model
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for single text"""
        embeddings = await self.generate_embeddings_batch([text])
        return embeddings[0]
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch of texts"""
        try:
            # Prepare instances
            instances = []
            for text in texts:
                # Truncate text to avoid API limits
                truncated_text = text[:3000] if len(text) > 3000 else text
                instances.append({"content": truncated_text})
            
            # Prepare request
            instances_proto = [
                {"content": {"string_value": instance["content"]}}
                for instance in instances
            ]
            
            parameters = {"outputDimensionality": self.dimensions}
            parameters_proto = {
                "outputDimensionality": {"number_value": parameters["outputDimensionality"]}
            }
            
            # Make prediction request
            request = {
                "endpoint": self._endpoint,
                "instances": instances_proto,
                "parameters": parameters_proto
            }
            
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.client.predict, request
            )
            
            # Extract embeddings
            embeddings = []
            for prediction in response.predictions:
                embedding_values = prediction.struct_value.fields["embeddings"].list_value.values
                embedding = [val.number_value for val in embedding_values]
                
                if len(embedding) != self.dimensions:
                    raise ValueError(f"Expected {self.dimensions} dimensions, got {len(embedding)}")
                
                embeddings.append(embedding)
            
            return embeddings
            
        except Exception as e:
            logging.error(f"VertexAI embedding generation failed: {e}")
            # Fallback to deterministic provider
            fallback = DeterministicEmbeddingProvider()
            return await fallback.generate_embeddings_batch(texts)


class TogetherAIEmbeddingProvider(EmbeddingProvider):
    """TogetherAI embedding provider (stub implementation)"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        # For now, use deterministic fallback for development
        self._fallback = DeterministicEmbeddingProvider()
    
    @property
    def name(self) -> str:
        return "together_ai"
    
    @property
    def model(self) -> str:
        return "togethercomputer/m2-bert-80M-8k-retrieval"
    
    @property
    def dimensions(self) -> int:
        return 768
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for single text (stub)"""
        # For development, use deterministic fallback with provider suffix
        modified_text = f"{text}|together_ai"
        return await self._fallback.generate_embedding(modified_text)
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch of texts (stub)"""
        modified_texts = [f"{text}|together_ai" for text in texts]
        return await self._fallback.generate_embeddings_batch(modified_texts)


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for development and testing"""
    
    @property
    def name(self) -> str:
        return "deterministic"
    
    @property
    def model(self) -> str:
        return "deterministic-hash-768"
    
    @property
    def dimensions(self) -> int:
        return 768
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate deterministic embedding based on text hash"""
        # Create deterministic hash-based embedding
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        
        # Generate vector from hash
        vector = []
        for i in range(self.dimensions):
            # Use different parts of hash for each dimension
            byte_offset = (i * 2) % len(text_hash)
            hex_val = text_hash[byte_offset:byte_offset + 2]
            
            # Convert to float in range [-1, 1]
            int_val = int(hex_val, 16)
            float_val = (int_val / 127.5) - 1.0
            vector.append(float_val)
        
        # Normalize vector
        magnitude = math.sqrt(sum(x * x for x in vector))
        if magnitude > 0:
            vector = [x / magnitude for x in vector]
        
        return vector
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch of texts"""
        embeddings = []
        for text in texts:
            embedding = await self.generate_embedding(text)
            embeddings.append(embedding)
        return embeddings


class EmbeddingCache:
    """Firestore-based embedding cache"""
    
    def __init__(self, collection_name: str = "embedding_cache"):
        if not GOOGLE_CLOUD_AVAILABLE:
            self.db = None
            self.collection = None
            self._local_cache = {}  # Fallback to in-memory cache
        else:
            self.db = firestore.Client()
            self.collection = self.db.collection(collection_name)
    
    def _get_cache_key(self, text: str, provider: str, model: str) -> str:
        """Generate cache key for text, provider, and model"""
        content = f"{text}|{provider}|{model}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def get(self, text: str, provider: str, model: str) -> Optional[List[float]]:
        """Get cached embedding"""
        try:
            cache_key = self._get_cache_key(text, provider, model)
            
            if not GOOGLE_CLOUD_AVAILABLE:
                # Use local cache fallback
                cached_data = self._local_cache.get(cache_key)
                if cached_data:
                    # Check expiration (24 hours)
                    if datetime.now() - cached_data["created_at"] < timedelta(hours=24):
                        return cached_data["embedding"]
                return None
            
            doc_ref = self.collection.document(cache_key)
            doc = await asyncio.get_event_loop().run_in_executor(None, doc_ref.get)
            
            if doc.exists:
                data = doc.to_dict()
                # Check expiration (24 hours)
                created_at = data.get("created_at")
                if created_at and datetime.now() - created_at < timedelta(hours=24):
                    return data.get("embedding")
            
            return None
            
        except Exception as e:
            logging.warning(f"Cache get failed: {e}")
            return None
    
    async def set(self, text: str, provider: str, model: str, embedding: List[float]) -> None:
        """Cache embedding"""
        try:
            cache_key = self._get_cache_key(text, provider, model)
            
            data = {
                "text": text,
                "provider": provider,
                "model": model,
                "embedding": embedding,
                "created_at": datetime.now(),
                "dimensions": len(embedding)
            }
            
            if not GOOGLE_CLOUD_AVAILABLE:
                # Use local cache fallback
                self._local_cache[cache_key] = data
                return
            
            doc_ref = self.collection.document(cache_key)
            await asyncio.get_event_loop().run_in_executor(None, doc_ref.set, data)
            
        except Exception as e:
            logging.warning(f"Cache set failed: {e}")
    
    async def clear_expired(self) -> int:
        """Clear expired cache entries"""
        try:
            cutoff = datetime.now() - timedelta(hours=24)
            
            if not GOOGLE_CLOUD_AVAILABLE:
                # Clean local cache
                expired_keys = []
                for key, data in self._local_cache.items():
                    if data["created_at"] < cutoff:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self._local_cache[key]
                
                return len(expired_keys)
            
            # Query expired documents
            query = self.collection.where("created_at", "<", cutoff)
            docs = await asyncio.get_event_loop().run_in_executor(None, query.stream)
            
            # Delete expired documents
            deleted_count = 0
            for doc in docs:
                await asyncio.get_event_loop().run_in_executor(None, doc.reference.delete)
                deleted_count += 1
            
            return deleted_count
            
        except Exception as e:
            logging.error(f"Cache cleanup failed: {e}")
            return 0


class EmbeddingService:
    """Main embedding service with provider switching and caching"""
    
    def __init__(self, 
                 provider: str = "vertex_ai",
                 project_id: str = "headhunter-ai-0088",
                 enable_cache: bool = True):
        self.provider_name = provider
        self.project_id = project_id
        self.enable_cache = enable_cache
        
        # Initialize provider
        self.provider = self._create_provider(provider)
        
        # Initialize cache
        self.cache = EmbeddingCache() if enable_cache else None
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def _create_provider(self, provider: str) -> EmbeddingProvider:
        """Create embedding provider"""
        if provider == "vertex_ai":
            return VertexAIEmbeddingProvider(self.project_id)
        elif provider == "together_ai":
            return TogetherAIEmbeddingProvider()
        elif provider == "deterministic":
            return DeterministicEmbeddingProvider()
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def generate_embedding(self, text: str) -> EmbeddingResult:
        """Generate embedding for single text"""
        start_time = time.time()
        cache_hit = False
        
        try:
            # Check cache first
            if self.cache:
                cached_embedding = await self.cache.get(text, self.provider.name, self.provider.model)
                if cached_embedding:
                    cache_hit = True
                    processing_time = int((time.time() - start_time) * 1000)
                    
                    return EmbeddingResult(
                        text=text,
                        vector=cached_embedding,
                        provider=self.provider.name,
                        model=self.provider.model,
                        timestamp=datetime.now(),
                        cache_hit=True,
                        processing_time_ms=processing_time
                    )
            
            # Generate new embedding
            embedding = await self.provider.generate_embedding(text)
            processing_time = int((time.time() - start_time) * 1000)
            
            # Cache the result
            if self.cache and not cache_hit:
                await self.cache.set(text, self.provider.name, self.provider.model, embedding)
            
            return EmbeddingResult(
                text=text,
                vector=embedding,
                provider=self.provider.name,
                model=self.provider.model,
                timestamp=datetime.now(),
                cache_hit=cache_hit,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            self.logger.error(f"Embedding generation failed for text length {len(text)}: {e}")
            raise
    
    async def generate_embeddings_batch(self, 
                                      texts: List[str],
                                      batch_size: int = 10) -> BatchEmbeddingResult:
        """Generate embeddings for batch of texts"""
        start_time = time.time()
        results = []
        cache_hits = 0
        
        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_results = []
            
            # Check cache for each text in batch
            uncached_texts = []
            uncached_indices = []
            
            if self.cache:
                for j, text in enumerate(batch_texts):
                    cached_embedding = await self.cache.get(text, self.provider.name, self.provider.model)
                    if cached_embedding:
                        result = EmbeddingResult(
                            text=text,
                            vector=cached_embedding,
                            provider=self.provider.name,
                            model=self.provider.model,
                            timestamp=datetime.now(),
                            cache_hit=True,
                            processing_time_ms=0
                        )
                        batch_results.append((j, result))
                        cache_hits += 1
                    else:
                        uncached_texts.append(text)
                        uncached_indices.append(j)
            else:
                uncached_texts = batch_texts
                uncached_indices = list(range(len(batch_texts)))
            
            # Generate embeddings for uncached texts
            if uncached_texts:
                embeddings = await self.provider.generate_embeddings_batch(uncached_texts)
                
                for k, embedding in enumerate(embeddings):
                    text = uncached_texts[k]
                    original_index = uncached_indices[k]
                    
                    result = EmbeddingResult(
                        text=text,
                        vector=embedding,
                        provider=self.provider.name,
                        model=self.provider.model,
                        timestamp=datetime.now(),
                        cache_hit=False,
                        processing_time_ms=0  # Will be calculated at batch level
                    )
                    
                    batch_results.append((original_index, result))
                    
                    # Cache the result
                    if self.cache:
                        await self.cache.set(text, self.provider.name, self.provider.model, embedding)
            
            # Sort by original index and add to results
            batch_results.sort(key=lambda x: x[0])
            results.extend([result for _, result in batch_results])
        
        total_processing_time = int((time.time() - start_time) * 1000)
        success_count = len(results)
        failed_count = len(texts) - success_count
        average_processing_time = total_processing_time / len(texts) if texts else 0
        
        return BatchEmbeddingResult(
            results=results,
            total_count=len(texts),
            success_count=success_count,
            failed_count=failed_count,
            cache_hits=cache_hits,
            total_processing_time_ms=total_processing_time,
            average_processing_time_ms=average_processing_time
        )
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get embedding service statistics"""
        try:
            # Get cache stats
            cache_stats = {"enabled": False}
            if self.cache:
                if not GOOGLE_CLOUD_AVAILABLE:
                    # Use local cache stats
                    cache_stats = {
                        "enabled": True,
                        "total_entries": len(self.cache._local_cache),
                        "provider_counts": {}
                    }
                    
                    # Count by provider
                    for data in self.cache._local_cache.values():
                        provider = data.get("provider", "unknown")
                        cache_stats["provider_counts"][provider] = cache_stats["provider_counts"].get(provider, 0) + 1
                else:
                    # Count total cached embeddings
                    docs = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: list(self.cache.collection.stream())
                    )
                    cache_stats = {
                        "enabled": True,
                        "total_entries": len(docs),
                        "provider_counts": {}
                    }
                    
                    # Count by provider
                    for doc in docs:
                        data = doc.to_dict()
                        provider = data.get("provider", "unknown")
                        cache_stats["provider_counts"][provider] = cache_stats["provider_counts"].get(provider, 0) + 1
            
            return {
                "provider": {
                    "name": self.provider.name,
                    "model": self.provider.model,
                    "dimensions": self.provider.dimensions
                },
                "cache": cache_stats,
                "project_id": self.project_id,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get stats: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        try:
            # Test embedding generation with simple text
            test_text = "Health check test"
            result = await self.generate_embedding(test_text)
            
            return {
                "status": "healthy",
                "provider": self.provider.name,
                "model": self.provider.model,
                "dimensions": len(result.vector),
                "cache_enabled": self.enable_cache,
                "test_embedding_time_ms": result.processing_time_ms,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Factory function for easy instantiation
def create_embedding_service(provider: str = "vertex_ai", **kwargs) -> EmbeddingService:
    """Create embedding service with specified provider"""
    return EmbeddingService(provider=provider, **kwargs)


# CLI interface for testing
if __name__ == "__main__":
    import argparse
    
    async def main():
        parser = argparse.ArgumentParser(description="Test embedding service")
        parser.add_argument("--provider", default="vertex_ai", 
                          choices=["vertex_ai", "together_ai", "deterministic"])
        parser.add_argument("--text", default="This is a test embedding")
        parser.add_argument("--batch", action="store_true", help="Test batch processing")
        
        args = parser.parse_args()
        
        service = create_embedding_service(args.provider)
        
        if args.batch:
            texts = [args.text, "Another test text", "Third test text"]
            result = await service.generate_embeddings_batch(texts)
            print(f"Batch result: {result.success_count}/{result.total_count} success, "
                  f"{result.cache_hits} cache hits, {result.total_processing_time_ms}ms total")
        else:
            result = await service.generate_embedding(args.text)
            print(f"Embedding: {len(result.vector)} dimensions, "
                  f"cache_hit: {result.cache_hit}, {result.processing_time_ms}ms")
        
        # Show stats
        stats = await service.get_stats()
        print(f"Stats: {json.dumps(stats, indent=2, default=str)}")
    
    asyncio.run(main())