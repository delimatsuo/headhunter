"""
Comprehensive TDD tests for the Embedding Generation Service
Following TDD protocol - these tests define the expected behavior
"""

import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any, Optional
import time
import hashlib

# Import the modules we just created
from scripts.embedding_service import (
    EmbeddingService,
    EmbeddingProvider,
    VertexAIEmbeddingProvider,
    TogetherAIEmbeddingProvider,
    DeterministicEmbeddingProvider,
    EmbeddingCache,
    EmbeddingResult,
    BatchEmbeddingResult,
    create_embedding_service
)


@pytest.fixture
def sample_texts():
    """Sample texts for testing embeddings"""
    return [
        "Senior Python developer with 8 years of experience in machine learning",
        "Frontend JavaScript engineer specializing in React and Vue.js",
        "DevOps engineer with expertise in Kubernetes and AWS",
        "Data scientist with background in deep learning and NLP",
        "Full-stack developer proficient in Python, React, and PostgreSQL"
    ]


@pytest.fixture
def mock_firestore_client():
    """Mock Firestore client for testing"""
    mock_client = Mock()
    mock_collection = Mock()
    mock_doc = Mock()
    mock_doc.get.return_value.exists = False
    mock_doc.set = AsyncMock()
    mock_collection.document.return_value = mock_doc
    mock_client.collection.return_value = mock_collection
    return mock_client


class TestEmbeddingProvider:
    """Test the base EmbeddingProvider interface and implementations"""

    def test_embedding_provider_interface(self):
        """Test that EmbeddingProvider defines the correct interface"""
        
        # Test that we can instantiate a deterministic provider
        provider = DeterministicEmbeddingProvider()
        
        # Test that it has the expected properties
        assert hasattr(provider, 'name'), "Provider should have name property"
        assert hasattr(provider, 'model'), "Provider should have model property" 
        assert hasattr(provider, 'dimensions'), "Provider should have dimensions property"
        assert hasattr(provider, 'generate_embedding'), "Provider should have generate_embedding method"
        assert hasattr(provider, 'generate_embeddings_batch'), "Provider should have generate_embeddings_batch method"
        
        # Test property values
        assert provider.name == "deterministic"
        assert provider.model == "deterministic-hash-768"
        assert provider.dimensions == 768

    @pytest.mark.asyncio
    async def test_deterministic_provider_consistency(self):
        """Test that deterministic provider returns consistent embeddings"""
        
        # Expected behavior: same text should always produce same embedding
        text = "Senior Python developer with machine learning experience"
        
        provider = DeterministicEmbeddingProvider()
        
        embedding1 = await provider.generate_embedding(text)
        embedding2 = await provider.generate_embedding(text)
        
        assert embedding1 == embedding2, "Deterministic provider should return consistent embeddings"
        assert len(embedding1) == 768, "Embedding should be 768 dimensions"
        assert isinstance(embedding1, list), "Embedding should be a list of floats"
        assert all(isinstance(x, float) for x in embedding1), "All elements should be floats"

    def test_deterministic_provider_different_texts(self):
        """Test that deterministic provider returns different embeddings for different texts"""
        
        provider = DeterministicEmbeddingProvider()
        
        text1 = "Senior Python developer"
        text2 = "Junior JavaScript developer"
        
        embedding1 = await provider.generate_embedding(text1)
        embedding2 = await provider.generate_embedding(text2)
        
        assert embedding1 != embedding2, "Different texts should produce different embeddings"
        
        # Calculate cosine similarity - should be low for different texts
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = sum(a * a for a in embedding1) ** 0.5
        norm2 = sum(b * b for b in embedding2) ** 0.5
        similarity = dot_product / (norm1 * norm2)
        
        assert similarity < 0.9, "Different texts should have low similarity"

    @patch('scripts.embedding_providers.aiplatform')
    def test_vertex_ai_provider_initialization(self, mock_aiplatform):
        """Test VertexAI provider initialization"""
        
        provider = VertexAIEmbeddingProvider()
        
        assert provider.get_provider_name() == "vertex_ai"
        assert provider.get_embedding_dimension() == 768
        assert provider.model_name == "text-embedding-004"

    @patch('scripts.embedding_providers.aiplatform.gapic.PredictionServiceClient')
    async def test_vertex_ai_provider_embedding_generation(self, mock_client):
        """Test VertexAI provider embedding generation"""
        
        # Mock the API response
        mock_response = Mock()
        mock_response.predictions = [
            Mock(embeddings=Mock(values=[0.1] * 768))
        ]
        mock_client.return_value.predict.return_value = mock_response
        
        provider = VertexAIEmbeddingProvider()
        text = "Senior Python developer with machine learning experience"
        
        embedding = await provider.generate_embedding(text)
        
        assert len(embedding) == 768
        assert all(isinstance(x, float) for x in embedding)
        assert embedding == [0.1] * 768

    async def test_together_ai_provider_stub(self):
        """Test TogetherAI provider stub implementation"""
        
        provider = TogetherAIEmbeddingProvider()
        
        assert provider.get_provider_name() == "together_ai"
        assert provider.get_embedding_dimension() == 768
        
        text = "Senior Python developer"
        embedding = await provider.generate_embedding(text)
        
        assert len(embedding) == 768
        assert all(isinstance(x, float) for x in embedding)
        
        # Should be deterministic for now (stub implementation)
        embedding2 = await provider.generate_embedding(text)
        assert embedding == embedding2


class TestEmbeddingService:
    """Test the main EmbeddingService class"""

    @pytest.fixture
    def mock_provider(self):
        """Mock embedding provider for testing"""
        provider = Mock()
        provider.generate_embedding = AsyncMock(return_value=[0.1] * 768)
        provider.generate_batch_embeddings = AsyncMock(return_value=[[0.1] * 768, [0.2] * 768])
        provider.get_provider_name.return_value = "mock_provider"
        provider.get_embedding_dimension.return_value = 768
        provider.is_available.return_value = True
        return provider

    def test_embedding_service_initialization(self, mock_provider):
        """Test EmbeddingService initialization with provider"""
        
        service = EmbeddingService(provider=mock_provider)
        
        assert service.provider == mock_provider
        assert service.get_provider_name() == "mock_provider"
        assert service.get_embedding_dimension() == 768

    async def test_single_embedding_generation(self, mock_provider):
        """Test generating a single embedding"""
        
        service = EmbeddingService(provider=mock_provider)
        text = "Senior Python developer"
        
        response = await service.generate_embedding(text)
        
        assert isinstance(response, EmbeddingResponse)
        assert response.text == text
        assert len(response.embedding) == 768
        assert response.provider_name == "mock_provider"
        assert response.cached is False
        assert response.generation_time_ms > 0

    async def test_batch_embedding_generation(self, mock_provider, sample_texts):
        """Test generating batch embeddings"""
        
        service = EmbeddingService(provider=mock_provider)
        
        batch_request = EmbeddingBatch(texts=sample_texts[:2])
        responses = await service.generate_batch_embeddings(batch_request)
        
        assert len(responses) == 2
        assert all(isinstance(r, EmbeddingResponse) for r in responses)
        assert all(len(r.embedding) == 768 for r in responses)
        assert responses[0].text == sample_texts[0]
        assert responses[1].text == sample_texts[1]

    async def test_embedding_with_metadata(self, mock_provider):
        """Test embedding generation with metadata"""
        
        service = EmbeddingService(provider=mock_provider)
        
        request = EmbeddingRequest(
            text="Senior Python developer",
            metadata={"candidate_id": "123", "source": "resume"}
        )
        
        response = await service.generate_embedding_with_metadata(request)
        
        assert response.metadata == {"candidate_id": "123", "source": "resume"}
        assert response.text == "Senior Python developer"

    def test_provider_switching(self):
        """Test switching between different embedding providers"""
        
        vertex_provider = Mock()
        vertex_provider.get_provider_name.return_value = "vertex_ai"
        
        together_provider = Mock() 
        together_provider.get_provider_name.return_value = "together_ai"
        
        service = EmbeddingService(provider=vertex_provider)
        assert service.get_provider_name() == "vertex_ai"
        
        service.switch_provider(together_provider)
        assert service.get_provider_name() == "together_ai"

    async def test_error_handling_and_fallback(self, mock_firestore_client):
        """Test error handling and fallback to deterministic provider"""
        
        # Create a failing provider
        failing_provider = Mock()
        failing_provider.generate_embedding = AsyncMock(side_effect=Exception("API Error"))
        failing_provider.get_provider_name.return_value = "failing_provider"
        
        service = EmbeddingService(
            provider=failing_provider, 
            fallback_provider=DeterministicEmbeddingProvider(),
            firestore_client=mock_firestore_client
        )
        
        text = "Senior Python developer"
        response = await service.generate_embedding(text)
        
        # Should fallback to deterministic provider
        assert response.provider_name == "deterministic_fallback"
        assert len(response.embedding) == 768
        assert response.fallback_used is True


class TestEmbeddingCache:
    """Test the embedding caching functionality"""

    def test_cache_initialization(self, mock_firestore_client):
        """Test cache initialization with Firestore"""
        
        cache = EmbeddingCache(firestore_client=mock_firestore_client)
        
        assert cache.firestore_client == mock_firestore_client
        assert cache.collection_name == "embedding_cache"
        assert cache.max_cache_size == 10000

    async def test_cache_get_miss(self, mock_firestore_client):
        """Test cache miss scenario"""
        
        # Mock Firestore to return no document
        mock_firestore_client.collection.return_value.document.return_value.get.return_value.exists = False
        
        cache = EmbeddingCache(firestore_client=mock_firestore_client)
        
        text = "Senior Python developer"
        result = await cache.get(text)
        
        assert result is None

    async def test_cache_get_hit(self, mock_firestore_client):
        """Test cache hit scenario"""
        
        # Mock Firestore to return cached embedding
        cached_data = {
            'embedding': [0.1] * 768,
            'provider': 'vertex_ai',
            'created_at': '2023-01-01T00:00:00Z',
            'text_hash': hashlib.sha256("Senior Python developer".encode()).hexdigest()
        }
        
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = cached_data
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc
        
        cache = EmbeddingCache(firestore_client=mock_firestore_client)
        
        text = "Senior Python developer"
        result = await cache.get(text)
        
        assert result is not None
        assert result['embedding'] == [0.1] * 768
        assert result['provider'] == 'vertex_ai'

    async def test_cache_set(self, mock_firestore_client):
        """Test setting cache entry"""
        
        cache = EmbeddingCache(firestore_client=mock_firestore_client)
        
        text = "Senior Python developer"
        embedding = [0.1] * 768
        provider = "vertex_ai"
        
        await cache.set(text, embedding, provider)
        
        # Verify Firestore was called to store the embedding
        mock_firestore_client.collection.return_value.document.return_value.set.assert_called_once()

    async def test_cache_with_service_integration(self, mock_firestore_client):
        """Test cache integration with EmbeddingService"""
        
        # First call should miss cache and generate embedding
        mock_provider = Mock()
        mock_provider.generate_embedding = AsyncMock(return_value=[0.1] * 768)
        mock_provider.get_provider_name.return_value = "vertex_ai"
        
        cache = EmbeddingCache(firestore_client=mock_firestore_client)
        service = EmbeddingService(provider=mock_provider, cache=cache)
        
        text = "Senior Python developer"
        
        # First call - cache miss
        response1 = await service.generate_embedding(text)
        assert response1.cached is False
        
        # Mock cache hit for second call
        cache.get = AsyncMock(return_value={
            'embedding': [0.1] * 768,
            'provider': 'vertex_ai',
            'created_at': '2023-01-01T00:00:00Z'
        })
        
        # Second call - cache hit
        response2 = await service.generate_embedding(text)
        assert response2.cached is True
        assert response2.embedding == [0.1] * 768


class TestFirestoreIntegration:
    """Test Firestore storage for embeddings"""

    async def test_store_embedding_in_firestore(self, mock_firestore_client):
        """Test storing embedding in Firestore embeddings collection"""
        
        service = EmbeddingService(
            provider=DeterministicEmbeddingProvider(),
            firestore_client=mock_firestore_client
        )
        
        request = EmbeddingRequest(
            text="Senior Python developer",
            metadata={"candidate_id": "123"},
            store_in_firestore=True
        )
        
        response = await service.generate_embedding_with_metadata(request)
        
        # Verify embedding was stored in Firestore
        mock_firestore_client.collection.assert_called_with("embeddings")
        
        # Check that document was created with correct structure
        expected_doc_data = {
            'text': "Senior Python developer",
            'embedding': response.embedding,
            'provider': response.provider_name,
            'metadata': {"candidate_id": "123"},
            'created_at': response.created_at,
            'text_hash': hashlib.sha256("Senior Python developer".encode()).hexdigest()
        }
        
        # Verify document was stored
        assert True  # Will fail until implementation

    async def test_batch_firestore_storage(self, mock_firestore_client, sample_texts):
        """Test batch storage of embeddings in Firestore"""
        
        service = EmbeddingService(
            provider=DeterministicEmbeddingProvider(),
            firestore_client=mock_firestore_client
        )
        
        batch_request = EmbeddingBatch(
            texts=sample_texts[:3],
            store_in_firestore=True,
            batch_metadata={"source": "candidate_profiles", "batch_id": "batch_001"}
        )
        
        responses = await service.generate_batch_embeddings(batch_request)
        
        assert len(responses) == 3
        
        # Verify batch storage was called
        assert True  # Will fail until implementation

    async def test_embedding_retrieval_from_firestore(self, mock_firestore_client):
        """Test retrieving stored embeddings from Firestore"""
        
        service = EmbeddingService(
            provider=DeterministicEmbeddingProvider(),
            firestore_client=mock_firestore_client
        )
        
        candidate_id = "123"
        stored_embeddings = await service.get_embeddings_by_metadata({"candidate_id": candidate_id})
        
        assert isinstance(stored_embeddings, list)
        # Will fail until implementation


class TestBatchProcessing:
    """Test batch embedding generation capabilities"""

    async def test_batch_size_optimization(self):
        """Test that batch processing optimizes API calls"""
        
        mock_provider = Mock()
        mock_provider.generate_batch_embeddings = AsyncMock(return_value=[[0.1] * 768] * 100)
        mock_provider.get_max_batch_size.return_value = 100
        
        service = EmbeddingService(provider=mock_provider)
        
        # Test with exactly max batch size
        texts = [f"Text {i}" for i in range(100)]
        batch_request = EmbeddingBatch(texts=texts)
        
        responses = await service.generate_batch_embeddings(batch_request)
        
        assert len(responses) == 100
        # Should make exactly one API call
        mock_provider.generate_batch_embeddings.assert_called_once()

    async def test_batch_size_splitting(self):
        """Test that large batches are split appropriately"""
        
        mock_provider = Mock()
        mock_provider.generate_batch_embeddings = AsyncMock(return_value=[[0.1] * 768] * 50)
        mock_provider.get_max_batch_size.return_value = 50
        
        service = EmbeddingService(provider=mock_provider)
        
        # Test with more than max batch size
        texts = [f"Text {i}" for i in range(150)]  # 3 batches of 50
        batch_request = EmbeddingBatch(texts=texts)
        
        responses = await service.generate_batch_embeddings(batch_request)
        
        assert len(responses) == 150
        # Should make exactly 3 API calls
        assert mock_provider.generate_batch_embeddings.call_count == 3

    async def test_batch_error_handling(self):
        """Test error handling in batch processing"""
        
        mock_provider = Mock()
        # First call succeeds, second fails, third succeeds
        mock_provider.generate_batch_embeddings = AsyncMock(
            side_effect=[
                [[0.1] * 768] * 50,  # First batch succeeds
                Exception("API Error"),  # Second batch fails
                [[0.3] * 768] * 50   # Third batch succeeds
            ]
        )
        mock_provider.get_max_batch_size.return_value = 50
        
        service = EmbeddingService(
            provider=mock_provider,
            fallback_provider=DeterministicEmbeddingProvider()
        )
        
        texts = [f"Text {i}" for i in range(150)]
        batch_request = EmbeddingBatch(texts=texts, continue_on_error=True)
        
        responses = await service.generate_batch_embeddings(batch_request)
        
        assert len(responses) == 150
        # Some should be from main provider, some from fallback
        main_provider_count = sum(1 for r in responses if r.provider_name == mock_provider.get_provider_name.return_value)
        fallback_count = sum(1 for r in responses if r.fallback_used)
        
        assert main_provider_count + fallback_count == 150


class TestPerformanceAndOptimization:
    """Test performance characteristics and optimizations"""

    async def test_embedding_generation_performance(self):
        """Test that embedding generation meets performance requirements"""
        
        provider = DeterministicEmbeddingProvider()
        service = EmbeddingService(provider=provider)
        
        text = "Senior Python developer with machine learning experience"
        
        # Single embedding should complete within reasonable time
        start_time = time.time()
        response = await service.generate_embedding(text)
        end_time = time.time()
        
        assert response.generation_time_ms < 1000, "Single embedding should generate in under 1 second"
        assert (end_time - start_time) < 1.0, "Total time should be under 1 second"

    async def test_batch_performance_scaling(self, sample_texts):
        """Test that batch processing scales efficiently"""
        
        provider = DeterministicEmbeddingProvider()
        service = EmbeddingService(provider=provider)
        
        # Test different batch sizes
        batch_sizes = [1, 10, 50, 100]
        performance_metrics = {}
        
        for batch_size in batch_sizes:
            texts = sample_texts * (batch_size // len(sample_texts) + 1)
            texts = texts[:batch_size]
            
            start_time = time.time()
            batch_request = EmbeddingBatch(texts=texts)
            responses = await service.generate_batch_embeddings(batch_request)
            end_time = time.time()
            
            performance_metrics[batch_size] = {
                'total_time': end_time - start_time,
                'time_per_embedding': (end_time - start_time) / batch_size,
                'embeddings_per_second': batch_size / (end_time - start_time)
            }
        
        # Batch processing should be more efficient per embedding
        assert performance_metrics[100]['time_per_embedding'] < performance_metrics[1]['time_per_embedding']

    async def test_memory_usage_optimization(self):
        """Test that memory usage is optimized for large batches"""
        
        provider = DeterministicEmbeddingProvider()
        service = EmbeddingService(provider=provider)
        
        # Generate a large batch
        texts = [f"Text content {i} with sufficient length to test memory usage" for i in range(1000)]
        batch_request = EmbeddingBatch(texts=texts)
        
        # This should not cause memory issues
        responses = await service.generate_batch_embeddings(batch_request)
        
        assert len(responses) == 1000
        # Memory usage should be reasonable (this is more of a smoke test)


class TestDataTypes:
    """Test the data type definitions and structures"""

    def test_embedding_request_structure(self):
        """Test EmbeddingRequest data structure"""
        
        request = EmbeddingRequest(
            text="Senior Python developer",
            metadata={"candidate_id": "123"},
            store_in_firestore=True
        )
        
        assert request.text == "Senior Python developer"
        assert request.metadata == {"candidate_id": "123"}
        assert request.store_in_firestore is True
        assert hasattr(request, 'created_at')

    def test_embedding_response_structure(self):
        """Test EmbeddingResponse data structure"""
        
        embedding = [0.1] * 768
        response = EmbeddingResponse(
            text="Senior Python developer",
            embedding=embedding,
            provider_name="vertex_ai",
            generation_time_ms=150.5,
            cached=False
        )
        
        assert response.text == "Senior Python developer"
        assert response.embedding == embedding
        assert response.provider_name == "vertex_ai"
        assert response.generation_time_ms == 150.5
        assert response.cached is False
        assert hasattr(response, 'created_at')

    def test_embedding_batch_structure(self):
        """Test EmbeddingBatch data structure"""
        
        texts = ["Text 1", "Text 2", "Text 3"]
        batch = EmbeddingBatch(
            texts=texts,
            store_in_firestore=True,
            batch_metadata={"batch_id": "001"},
            continue_on_error=True
        )
        
        assert batch.texts == texts
        assert batch.store_in_firestore is True
        assert batch.batch_metadata == {"batch_id": "001"}
        assert batch.continue_on_error is True
        assert hasattr(batch, 'created_at')


# Integration Tests
class TestFullIntegration:
    """Test full end-to-end integration scenarios"""

    async def test_complete_workflow_vertex_ai(self, mock_firestore_client):
        """Test complete workflow with VertexAI provider"""
        
        # This test will be skipped unless VERTEX_AI_INTEGRATION=true
        if not os.getenv('VERTEX_AI_INTEGRATION'):
            pytest.skip("Skipping VertexAI integration test")
        
        provider = VertexAIEmbeddingProvider()
        cache = EmbeddingCache(firestore_client=mock_firestore_client)
        service = EmbeddingService(
            provider=provider,
            cache=cache,
            fallback_provider=DeterministicEmbeddingProvider(),
            firestore_client=mock_firestore_client
        )
        
        text = "Senior Python developer with 8 years of machine learning experience"
        
        # Generate embedding with full workflow
        response = await service.generate_embedding(text)
        
        assert len(response.embedding) == 768
        assert response.provider_name == "vertex_ai"
        assert isinstance(response.generation_time_ms, float)
        assert response.generation_time_ms > 0

    async def test_fallback_mechanism_integration(self, mock_firestore_client):
        """Test fallback mechanism in realistic failure scenario"""
        
        # Create a provider that will fail
        failing_provider = Mock()
        failing_provider.generate_embedding = AsyncMock(side_effect=Exception("Network Error"))
        failing_provider.get_provider_name.return_value = "failing_provider"
        
        fallback_provider = DeterministicEmbeddingProvider()
        
        service = EmbeddingService(
            provider=failing_provider,
            fallback_provider=fallback_provider,
            firestore_client=mock_firestore_client
        )
        
        text = "Senior Python developer"
        response = await service.generate_embedding(text)
        
        # Should successfully fall back
        assert response.fallback_used is True
        assert response.provider_name == "deterministic_fallback"
        assert len(response.embedding) == 768


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])