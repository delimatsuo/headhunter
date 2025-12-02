
import firebase_admin
from firebase_admin import credentials, firestore
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def count_candidates():
    # Initialize Firebase
    if not firebase_admin._apps:
        try:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {'projectId': 'headhunter-ai-0088'})
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            return

    db = firestore.client()
    
    try:
        # Count documents in 'candidates' collection
        # Note: count() aggregation is more efficient but might not be available in all SDK versions
        # We'll use a stream with select to minimize data transfer
        candidates_ref = db.collection('candidates')
        count = 0
        
        # Using aggregation query if available (most cost effective)
        try:
            aggregate_query = candidates_ref.count()
            results = aggregate_query.get()
            count = results[0][0].value
        except Exception:
            # Fallback to streaming IDs
            docs = candidates_ref.select([]).stream()
            for _ in docs:
                count += 1
                
        logger.info(f"Total Candidates: {count}")
        
        # Cost estimation
        # Input: ~3000 tokens per resume (conservative avg)
        # Output: ~1000 tokens per analysis
        # Gemini 2.5 Flash Pricing: Input $0.10/1M, Output $0.40/1M
        
        input_tokens = count * 3000
        output_tokens = count * 1000
        
        input_cost = (input_tokens / 1_000_000) * 0.10
        output_cost = (output_tokens / 1_000_000) * 0.40
        total_cost = input_cost + output_cost
        
        logger.info(f"Estimated Cost Breakdown:")
        logger.info(f"  Input Tokens: ~{input_tokens:,} (${input_cost:.4f})")
        logger.info(f"  Output Tokens: ~{output_tokens:,} (${output_cost:.4f})")
        logger.info(f"  Total Estimated Cost: ${total_cost:.4f}")
        
    except Exception as e:
        logger.error(f"Error counting candidates: {e}")

if __name__ == "__main__":
    count_candidates()
