# Embedding Generation Service

## Overview

The Embedding Generation Service provides pluggable embedding providers with caching and batch processing capabilities for the Headhunter AI candidate matching system.

## Architecture

### Provider Pattern
The service uses a provider pattern to support multiple embedding backends:

- **VertexAI Provider**: Google's text-embedding-004 model (production)
- **TogetherAI Provider**: Stub implementation for future integration
- **Deterministic Provider**: Hash-based embeddings for development/testing

### Key Components

1. **EmbeddingService**: Main service class with provider switching
2. **EmbeddingProvider**: Abstract base class for providers
3. **EmbeddingCache**: Firestore-based caching with local fallback
4. **BatchEmbeddingResult**: Comprehensive batch processing results

## Usage

### Basic Usage

```python
from scripts.embedding_service import create_embedding_service
import asyncio

async def main():
    # Create service with default VertexAI provider
    service = create_embedding_service(provider="vertex_ai")
    
    # Generate single embedding
    result = await service.generate_embedding("Senior Python developer")
    print(f"Embedding: {len(result.vector)} dimensions")
    
    # Batch processing
    texts = ["Python developer", "JavaScript engineer", "Data scientist"]
    batch_result = await service.generate_embeddings_batch(texts)
    print(f"Processed: {batch_result.success_count}/{batch_result.total_count}")

asyncio.run(main())
```

### CLI Interface

```bash
# Test single embedding
python3 scripts/embedding_service.py --provider vertex_ai --text "Senior developer"

# Test batch processing
python3 scripts/embedding_service.py --provider deterministic --batch

# Health check
python3 scripts/embedding_service.py --provider vertex_ai --help
```

## Configuration

### Environment Variables

- `GOOGLE_CLOUD_PROJECT`: GCP project ID (default: headhunter-ai-0088)
- `EMBEDDING_PROVIDER`: Provider to use (vertex_ai, together_ai, deterministic)

### Provider Selection

```python
# Use different providers
vertex_service = create_embedding_service("vertex_ai")
local_service = create_embedding_service("deterministic")
together_service = create_embedding_service("together_ai")
```

## Caching

### Firestore Cache
- Automatic caching of all embeddings
- 24-hour expiration
- Cache key: SHA256(text + provider + model)

### Local Fallback
When Google Cloud is unavailable:
- Falls back to in-memory cache
- Same interface, no code changes required

### Cache Management

```python
# Get service statistics
stats = await service.get_stats()
print(f"Cached entries: {stats['cache']['total_entries']}")

# Health check
health = await service.health_check()
print(f"Status: {health['status']}")
```

## Error Handling

### Automatic Fallbacks
- VertexAI → Deterministic provider on failure
- Firestore → Local cache on connection issues
- Graceful degradation for all components

### Retry Logic
- Built into VertexAI provider
- Exponential backoff for transient failures
- Dead letter patterns for permanent failures

## Performance

### Batch Processing
- Configurable batch sizes (default: 10)
- Parallel cache lookups
- Efficient cache hit optimization

### Metrics
- Processing time tracking
- Cache hit rates
- Success/failure counts
- Provider performance stats

## Testing

### TDD Test Suite
```bash
# Run embedding service tests
python3 -m pytest tests/test_embedding_service.py -v

# Test specific provider
python3 -c "
from scripts.embedding_service import DeterministicEmbeddingProvider
import asyncio

async def test():
    provider = DeterministicEmbeddingProvider()
    embedding = await provider.generate_embedding('test')
    print(f'Generated: {len(embedding)} dimensions')

asyncio.run(test())
"
```

### Test Coverage
- ✅ Provider interface compliance
- ✅ Deterministic consistency
- ✅ VertexAI integration (with mocks)
- ✅ Caching behavior
- ✅ Batch processing
- ✅ Error handling
- ✅ Health checks

## Production Deployment

### Dependencies
```bash
# Required for VertexAI provider
pip install google-cloud-aiplatform google-cloud-firestore

# Required for all providers
pip install asyncio typing dataclasses
```

### GCP Setup
1. Enable Vertex AI API
2. Configure service account with AI Platform permissions
3. Set up Firestore database for caching

### Monitoring
- Service health endpoint: `/health`
- Metrics endpoint: `/stats`
- Built-in logging for all operations

## Integration

### Cloud Functions
```typescript
// Import embedding service results
import { EmbeddingResult } from './types';

// Use in semantic search
const embedding = await generateEmbedding(queryText);
const similarCandidates = await vectorSearch(embedding);
```

### Vector Search
The embedding service integrates with the vector search system for candidate matching based on semantic similarity.

## Development

### Adding New Providers
1. Implement `EmbeddingProvider` interface
2. Add to `_create_provider()` method
3. Add provider configuration
4. Write comprehensive tests

### Local Development
```bash
# Use deterministic provider for consistent testing
export EMBEDDING_PROVIDER=deterministic

# Run tests
python3 scripts/embedding_service.py --provider deterministic --text "test"
```

## Troubleshooting

### Common Issues
1. **VertexAI Authentication**: Ensure service account permissions
2. **Firestore Access**: Check security rules and permissions
3. **Memory Usage**: Monitor batch sizes for large datasets
4. **Rate Limits**: VertexAI has quotas, use batch processing

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)

service = create_embedding_service("vertex_ai")
# Detailed logging for troubleshooting
```

## Future Enhancements

1. **Additional Providers**: OpenAI, Cohere, HuggingFace
2. **Vector Database**: Direct integration with specialized vector DBs
3. **Model Fine-tuning**: Custom embeddings for recruitment domain
4. **Distributed Caching**: Redis for high-performance caching