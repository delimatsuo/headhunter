#!/bin/bash

echo "🚀 HEADHUNTER CLOUD DEPLOYMENT & TEST"
echo "===================================="

# Set project
gcloud config set project headhunter-ai-0088

echo "📦 Building Cloud Functions..."
cd ../functions
npm run build

if [ $? -eq 0 ]; then
    echo "✅ Build successful"
else
    echo "❌ Build failed"
    exit 1
fi

echo ""
echo "☁️ Deploying Cloud Functions..."
firebase deploy --only functions --project headhunter-ai-0088

if [ $? -eq 0 ]; then
    echo "✅ Deployment successful"
else
    echo "❌ Deployment failed"
    exit 1
fi

echo ""
echo "🧪 Testing with sample candidates..."
cd ../scripts
python cloud_test_batch.py

echo ""
echo "📊 Monitoring results..."
echo "You can now monitor results with:"
echo "  python monitor_results.py --summary      # View summary report"
echo "  python monitor_results.py --live         # Live monitoring dashboard"
echo "  python monitor_results.py --export       # Export all data to JSON"
echo ""
echo "🌐 View results in Firebase Console:"
echo "  https://console.cloud.google.com/firestore/data/enriched_profiles?project=headhunter-ai-0088"
echo ""
echo "🎉 Deployment and test complete!"