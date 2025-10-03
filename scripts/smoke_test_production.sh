#!/bin/bash
# Production Smoke Tests for API Gateway and Cloud Run Services

set -e

PROJECT_ID="headhunter-ai-0088"
GATEWAY_URL="https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get API key
echo "🔑 Retrieving API key from Secret Manager..."
API_KEY=$(gcloud secrets versions access latest --secret=api-gateway-key --project=$PROJECT_ID)
echo "✅ API key retrieved"
echo

# Test counter
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test function
test_endpoint() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local expected_status="$4"
    local data="$5"

    TESTS_RUN=$((TESTS_RUN + 1))

    echo -n "⏳ Test $TESTS_RUN: $name... "

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" -H "X-API-Key: $API_KEY" "$GATEWAY_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" \
            -H "X-API-Key: $API_KEY" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$GATEWAY_URL$endpoint")
    fi

    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$status_code" -eq "$expected_status" ]; then
        echo -e "${GREEN}✅ PASS${NC} (HTTP $status_code)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        if [ ! -z "$body" ]; then
            echo "   Response: $(echo $body | head -c 100)"
        fi
    else
        echo -e "${RED}❌ FAIL${NC} (Expected $expected_status, got $status_code)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        echo "   Response: $body"
    fi
    echo
}

# Run tests
echo "🚀 Running Production Smoke Tests"
echo "=" | sed 's/.*/&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&/'
echo

# Health check (no auth required)
echo "📍 Testing Health Endpoints"
echo "---"
test_endpoint "Gateway Health Check" "GET" "/health" 200

# Admin service (if exposed)
test_endpoint "Admin Service Health" "GET" "/admin/health" 200

# Embeddings service
echo "📍 Testing Embeddings Service"
echo "---"
test_endpoint "Generate Embedding" "POST" "/v1/embeddings/generate" 200 \
    '{"text": "Senior Python developer with 5 years experience"}'

# Search service (if candidates exist)
echo "📍 Testing Search Service"
echo "---"
test_endpoint "Search Candidates" "POST" "/v1/search" 200 \
    '{"query": "Python developer", "tenantId": "test-tenant", "limit": 5}'

# Summary
echo "=" | sed 's/.*/&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&/'
echo "📊 Test Results:"
echo "   Total: $TESTS_RUN"
echo -e "   ${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "   ${RED}Failed: $TESTS_FAILED${NC}"
echo

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All smoke tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Check logs above.${NC}"
    exit 1
fi
