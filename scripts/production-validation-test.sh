#!/usr/bin/env bash
# Production Validation Test Script for Task 78.8
# Tests all 8 Fastify services and API Gateway

# Don't exit on error - we want to see all test results
set +e

PROJECT_ID="headhunter-ai-0088"
REGION="us-central1"
GATEWAY_ENDPOINT="headhunter-api-gateway-production-d735p8t6.uc.gateway.dev"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Initialize counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Service endpoints (using simple arrays for compatibility)
SERVICE_NAMES=(
    "hh-admin-svc-production"
    "hh-eco-svc-production"
    "hh-embed-svc-production"
    "hh-enrich-svc-production"
    "hh-evidence-svc-production"
    "hh-msgs-svc-production"
    "hh-rerank-svc-production"
    "hh-search-svc-production"
)

SERVICE_URLS=(
    "https://hh-admin-svc-production-akcoqbr7sa-uc.a.run.app"
    "https://hh-eco-svc-production-akcoqbr7sa-uc.a.run.app"
    "https://hh-embed-svc-production-akcoqbr7sa-uc.a.run.app"
    "https://hh-enrich-svc-production-akcoqbr7sa-uc.a.run.app"
    "https://hh-evidence-svc-production-akcoqbr7sa-uc.a.run.app"
    "https://hh-msgs-svc-production-akcoqbr7sa-uc.a.run.app"
    "https://hh-rerank-svc-production-akcoqbr7sa-uc.a.run.app"
    "https://hh-search-svc-production-akcoqbr7sa-uc.a.run.app"
)

echo "=========================================="
echo "Production Validation Test Suite"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Gateway: $GATEWAY_ENDPOINT"
echo "Time: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "=========================================="
echo ""

# Function to test endpoint
test_endpoint() {
    local name=$1
    local url=$2
    local endpoint=$3
    local expected_status=${4:-200}

    TESTS_TOTAL=$((TESTS_TOTAL + 1))

    echo -n "Testing $name$endpoint... "

    # Try to get identity token for authenticated requests
    TOKEN=$(gcloud auth print-identity-token 2>/dev/null || echo "")

    if [ -n "$TOKEN" ]; then
        RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $TOKEN" "$url$endpoint" 2>&1)
    else
        RESPONSE=$(curl -s -w "\n%{http_code}" "$url$endpoint" 2>&1)
    fi

    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | sed '$d')

    if [ "$HTTP_CODE" = "$expected_status" ]; then
        echo -e "${GREEN}PASS${NC} (HTTP $HTTP_CODE)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC} (HTTP $HTTP_CODE, expected $expected_status)"
        echo "  Response: $BODY" | head -n 3
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo "=========================================="
echo "Phase 1: Individual Service Health Checks"
echo "=========================================="
echo ""

for i in "${!SERVICE_NAMES[@]}"; do
    service_name="${SERVICE_NAMES[$i]}"
    service_url="${SERVICE_URLS[$i]}"
    echo "--- Testing $service_name ---"
    test_endpoint "$service_name" "$service_url" "/health" 200
    test_endpoint "$service_name" "$service_url" "/ready" 200
    echo ""
done

echo "=========================================="
echo "Phase 2: Service Metrics Endpoints"
echo "=========================================="
echo ""

for i in "${!SERVICE_NAMES[@]}"; do
    service_name="${SERVICE_NAMES[$i]}"
    service_url="${SERVICE_URLS[$i]}"
    echo "--- Testing $service_name metrics ---"
    test_endpoint "$service_name" "$service_url" "/metrics" 200
    echo ""
done

echo "=========================================="
echo "Phase 3: API Gateway Routing Tests"
echo "=========================================="
echo ""

# Test gateway health endpoint
echo "--- Testing API Gateway Health ---"
test_endpoint "API Gateway" "https://$GATEWAY_ENDPOINT" "/health" 200
echo ""

echo "=========================================="
echo "Phase 4: Service-Specific Endpoints"
echo "=========================================="
echo ""

# Test search service specific endpoints
echo "--- Testing hh-search-svc specific endpoints ---"
test_endpoint "search-svc" "${SERVICE_URLS[7]}" "/api/v1/search/health" 200
echo ""

# Test rerank service specific endpoints
echo "--- Testing hh-rerank-svc specific endpoints ---"
test_endpoint "rerank-svc" "${SERVICE_URLS[6]}" "/api/v1/rerank/health" 200
echo ""

echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo ""
echo "Total Tests: $TESTS_TOTAL"
echo -e "Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Failed: ${RED}$TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}Some tests failed. Review above for details.${NC}"
    exit 1
fi
