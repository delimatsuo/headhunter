#!/bin/bash
# Run generateAllEmbeddings multiple times to process all candidates

echo "Starting embedding generation loop..."
echo "Each run processes ~4600 candidates (9 min timeout)"
echo ""

for i in {1..6}; do
    echo "=== Run $i of 6 - Started at $(date) ==="
    curl -s "https://generateallembeddings-akcoqbr7sa-uc.a.run.app" --max-time 600
    echo ""
    echo "=== Run $i completed at $(date) ==="
    echo ""
    sleep 5
done

echo "Embedding generation complete!"
echo "Check logs: gcloud logging read 'resource.labels.service_name=\"generateallembeddings\"' --limit=20"
