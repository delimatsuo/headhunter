#!/bin/bash
# Run batch enrichment iteratively until all candidates are processed

echo "Starting batch enrichment for candidates without intelligent_analysis..."
echo "Total candidates to enrich: ~1,523"

LAST_DOC_ID=""
TOTAL_PROCESSED=0
BATCH_NUM=0

while true; do
    BATCH_NUM=$((BATCH_NUM + 1))
    echo "=== Batch $BATCH_NUM (LastDocId: ${LAST_DOC_ID:-'start'}) ==="
    
    if [ -n "$LAST_DOC_ID" ]; then
        RESPONSE=$(curl -s "https://batchenrichcandidates-akcoqbr7sa-uc.a.run.app?batchSize=50&startAfter=$LAST_DOC_ID" --max-time 600)
    else
        RESPONSE=$(curl -s "https://batchenrichcandidates-akcoqbr7sa-uc.a.run.app?batchSize=50" --max-time 600)
    fi
    
    echo "Response: $RESPONSE"
    
    # Extract values from JSON response
    PROCESSED=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('processed',0))" 2>/dev/null || echo "0")
    SCANNED=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('scanned',0))" 2>/dev/null || echo "0")
    LAST_DOC_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('lastDocId',''))" 2>/dev/null || echo "")
    
    TOTAL_PROCESSED=$((TOTAL_PROCESSED + PROCESSED))
    
    echo "Batch processed: $PROCESSED, Total so far: $TOTAL_PROCESSED"
    
    # Check if we're done
    if [ "$SCANNED" -eq 0 ] || [ -z "$LAST_DOC_ID" ]; then
        echo "No more candidates to process"
        break
    fi
    
    # Exit after ~30 batches to avoid infinite loop
    if [ $BATCH_NUM -ge 500 ]; then
        echo "Reached batch limit"
        break
    fi
    
    sleep 2
done

echo ""
echo "========================="
echo "Enrichment complete!"
echo "Total processed: $TOTAL_PROCESSED"
echo "========================="
