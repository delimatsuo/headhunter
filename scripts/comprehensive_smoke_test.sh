#!/usr/bin/env bash
# Comprehensive Production Smoke Test for Headhunter API Gateway
# Tests all 8 services with functional endpoints and proper error handling
#
# Usage: ./scripts/comprehensive_smoke_test.sh [--project-id PROJECT_ID] [--gateway-url URL] [--tenant-id TENANT]

set -euo pipefail

# Constants
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly DEFAULT_PROJECT_ID="headhunter-ai-0088"
readonly DEFAULT_GATEWAY_URL="https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev"
readonly DEFAULT_TENANT_ID="test-tenant"

# Test candidates (loaded in Firestore)
readonly TEST_CANDIDATES=(
  "sarah_chen"
  "marcus_rodriguez"
  "james_thompson"
  "lisa_park"
  "emily_watson"
  "john_smith"
)

# Colors for output
readonly COLOR_GREEN='\033[0;32m'
readonly COLOR_RED='\033[0;31m'
readonly COLOR_YELLOW='\033[1;33m'
readonly COLOR_BLUE='\033[0;34m'
readonly COLOR_CYAN='\033[0;36m'
readonly COLOR_RESET='\033[0m'

# Configuration
PROJECT_ID="${PROJECT_ID:-$DEFAULT_PROJECT_ID}"
GATEWAY_URL="${GATEWAY_URL:-$DEFAULT_GATEWAY_URL}"
TENANT_ID="${TENANT_ID:-$DEFAULT_TENANT_ID}"
API_KEY=""
VERBOSE="${VERBOSE:-false}"

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Test results storage
declare -a TEST_RESULTS

# Parse command line arguments
parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --project-id)
        PROJECT_ID="$2"
        shift 2
        ;;
      --gateway-url)
        GATEWAY_URL="$2"
        shift 2
        ;;
      --tenant-id)
        TENANT_ID="$2"
        shift 2
        ;;
      --api-key)
        API_KEY="$2"
        shift 2
        ;;
      --verbose|-v)
        VERBOSE=true
        shift
        ;;
      --help|-h)
        print_usage
        exit 0
        ;;
      *)
        echo "Unknown argument: $1"
        print_usage
        exit 1
        ;;
    esac
  done
}

print_usage() {
  cat <<EOF
Usage: $0 [OPTIONS]

Comprehensive smoke test for Headhunter API Gateway and all 8 services.

OPTIONS:
  --project-id ID       Google Cloud project ID (default: $DEFAULT_PROJECT_ID)
  --gateway-url URL     API Gateway URL (default: $DEFAULT_GATEWAY_URL)
  --tenant-id TENANT    Tenant ID for multi-tenant tests (default: $DEFAULT_TENANT_ID)
  --api-key KEY         API key (if not provided, will fetch from Secret Manager)
  --verbose, -v         Enable verbose output
  --help, -h            Show this help message

EXAMPLES:
  # Run with defaults
  $0

  # Run with custom project and tenant
  $0 --project-id my-project --tenant-id my-tenant

  # Run with explicit API key
  $0 --api-key "your-api-key-here"

SERVICES TESTED:
  1. hh-admin-svc (7107)    - Admin, scheduler, policy enforcement
  2. hh-embed-svc (7101)    - Profile normalization, embedding generation
  3. hh-search-svc (7102)   - Multi-tenant search with pgvector
  4. hh-rerank-svc (7103)   - Redis-backed scoring and reranking
  5. hh-msgs-svc (7106)     - Notifications and messaging
  6. hh-evidence-svc (7104) - Provenance and audit trails
  7. hh-eco-svc (7105)      - ECO datasets and occupation normalization
  8. hh-enrich-svc (7108)   - Long-running enrichment pipelines

EXIT CODES:
  0 - All tests passed
  1 - One or more tests failed
  2 - Configuration error
EOF
}

log() {
  echo -e "${COLOR_CYAN}[$(date -u +'%Y-%m-%d %H:%M:%S UTC')]${COLOR_RESET} $*"
}

log_info() {
  echo -e "${COLOR_BLUE}ℹ${COLOR_RESET} $*"
}

log_success() {
  echo -e "${COLOR_GREEN}✅${COLOR_RESET} $*"
}

log_error() {
  echo -e "${COLOR_RED}❌${COLOR_RESET} $*" >&2
}

log_warn() {
  echo -e "${COLOR_YELLOW}⚠${COLOR_RESET} $*" >&2
}

log_verbose() {
  if [[ "$VERBOSE" == "true" ]]; then
    echo -e "${COLOR_CYAN}  →${COLOR_RESET} $*"
  fi
}

# Check required commands
check_dependencies() {
  local missing_deps=()

  for cmd in curl jq gcloud python3; do
    if ! command -v "$cmd" &>/dev/null; then
      missing_deps+=("$cmd")
    fi
  done

  if [[ ${#missing_deps[@]} -gt 0 ]]; then
    log_error "Missing required dependencies: ${missing_deps[*]}"
    log_error "Please install them and try again."
    exit 2
  fi
}

# Retrieve API key from Secret Manager
fetch_api_key() {
  if [[ -n "$API_KEY" ]]; then
    log_verbose "Using provided API key"
    return 0
  fi

  log "🔑 Retrieving API key from Secret Manager..."

  if ! API_KEY=$(gcloud secrets versions access latest \
    --secret=api-gateway-key \
    --project="$PROJECT_ID" 2>&1); then
    log_error "Failed to retrieve API key from Secret Manager"
    log_error "Error: $API_KEY"
    log_error "Make sure you have access to secret 'api-gateway-key' in project '$PROJECT_ID'"
    exit 2
  fi

  # Trim whitespace
  API_KEY=$(echo "$API_KEY" | tr -d '[:space:]')

  if [[ -z "$API_KEY" ]]; then
    log_error "API key is empty"
    exit 2
  fi

  log_success "API key retrieved successfully"
}

# Test execution function
run_test() {
  local test_name="$1"
  local method="$2"
  local endpoint="$3"
  local expected_status="$4"
  local data="${5:-}"
  local extra_headers="${6:-}"
  local skip_reason="${7:-}"

  TESTS_RUN=$((TESTS_RUN + 1))

  # Check if test should be skipped
  if [[ -n "$skip_reason" ]]; then
    log_warn "Test $TESTS_RUN: $test_name - SKIPPED ($skip_reason)"
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
    TEST_RESULTS+=("SKIP|$test_name|$skip_reason")
    return
  fi

  echo -n "⏳ Test $TESTS_RUN: $test_name... "

  local start_time
  start_time=$(date +%s)

  # Build curl command
  local curl_args=(
    -s -w '\n%{http_code}'
    -X "$method"
    -H "X-API-Key: $API_KEY"
    -H "X-Tenant-ID: $TENANT_ID"
    -H "X-Request-ID: smoke-test-$TESTS_RUN-$$"
    -H "Content-Type: application/json"
  )

  # Add extra headers if provided
  if [[ -n "$extra_headers" ]]; then
    while IFS= read -r header; do
      curl_args+=(-H "$header")
    done <<< "$extra_headers"
  fi

  # Add data if provided
  if [[ -n "$data" ]]; then
    curl_args+=(-d "$data")
  fi

  curl_args+=("${GATEWAY_URL}${endpoint}")

  # Execute request
  local response
  if ! response=$(curl "${curl_args[@]}" 2>&1); then
    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_error "FAIL (curl error after ${duration}s)"
    log_verbose "Error: $response"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    TEST_RESULTS+=("FAIL|$test_name|curl_error|$duration")
    return 1
  fi

  local end_time
  end_time=$(date +%s)
  local duration=$((end_time - start_time))

  # Extract status code and body
  local status_code
  status_code=$(echo "$response" | tail -n1)
  local body
  body=$(echo "$response" | sed '$d')

  # Validate status code
  if [[ "$status_code" == "$expected_status" ]]; then
    echo -e "${COLOR_GREEN}✅ PASS${COLOR_RESET} (HTTP $status_code, ${duration}s)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    TEST_RESULTS+=("PASS|$test_name|$status_code|$duration")

    if [[ "$VERBOSE" == "true" && -n "$body" ]]; then
      local preview
      preview=$(echo "$body" | head -c 200)
      log_verbose "Response preview: $preview"
    fi
    return 0
  else
    echo -e "${COLOR_RED}❌ FAIL${COLOR_RESET} (Expected $expected_status, got $status_code, ${duration}ms)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    TEST_RESULTS+=("FAIL|$test_name|status_mismatch|$duration|expected_${expected_status}_got_${status_code}")

    if [[ -n "$body" ]]; then
      log_verbose "Response body: $(echo "$body" | head -c 500)"
    fi
    return 1
  fi
}

# Print test section header
print_section() {
  local title="$1"
  echo
  echo -e "${COLOR_BLUE}═══════════════════════════════════════════════════════════${COLOR_RESET}"
  echo -e "${COLOR_BLUE}  $title${COLOR_RESET}"
  echo -e "${COLOR_BLUE}═══════════════════════════════════════════════════════════${COLOR_RESET}"
}

# Gateway health tests
test_gateway_health() {
  print_section "🏥 Gateway Health Checks"

  run_test "Gateway root health" "GET" "/health" 200
  run_test "Gateway readiness" "GET" "/ready" 200
}

# Admin service tests (hh-admin-svc, port 7107)
test_admin_service() {
  print_section "⚙️  Admin Service (hh-admin-svc)"

  run_test "Admin service health" "GET" "/admin/health" 200
  run_test "Admin list snapshots" "GET" "/admin/snapshots" 200
  run_test "Admin tenant policies" "GET" "/admin/policies?tenantId=${TENANT_ID}" 200
}

# Embed service tests (hh-embed-svc, port 7101)
test_embed_service() {
  print_section "🔤 Embed Service (hh-embed-svc)"

  run_test "Embed service health" "GET" "/v1/embeddings/health" 200

  local embed_payload
  embed_payload=$(cat <<EOF
{
  "text": "Senior Python developer with 10 years of experience in cloud infrastructure and AI/ML",
  "model": "text-embedding-004"
}
EOF
)

  run_test "Generate embedding" "POST" "/v1/embeddings/generate" 200 "$embed_payload"

  # Test batch embeddings
  local batch_payload
  batch_payload=$(cat <<EOF
{
  "texts": [
    "Python developer",
    "Cloud architect",
    "Machine learning engineer"
  ],
  "model": "text-embedding-004"
}
EOF
)

  run_test "Generate batch embeddings" "POST" "/v1/embeddings/batch" 200 "$batch_payload"
}

# Search service tests (hh-search-svc, port 7102)
test_search_service() {
  print_section "🔍 Search Service (hh-search-svc)"

  run_test "Search service health" "GET" "/v1/search/health" 200

  # Test semantic search with real test candidate
  local search_payload
  search_payload=$(cat <<EOF
{
  "query": "Senior software engineer with Python and cloud experience",
  "limit": 5,
  "filters": {
    "role_level": ["Senior", "Lead"]
  }
}
EOF
)

  run_test "Semantic search" "POST" "/v1/search" 200 "$search_payload"

  # Test hybrid search (vector + keyword)
  local hybrid_payload
  hybrid_payload=$(cat <<EOF
{
  "query": "machine learning engineer",
  "limit": 3,
  "mode": "hybrid",
  "weights": {
    "semantic": 0.7,
    "keyword": 0.3
  }
}
EOF
)

  run_test "Hybrid search" "POST" "/v1/search/hybrid" 200 "$hybrid_payload"

  # Test candidate retrieval
  run_test "Get candidate by ID" "GET" "/v1/search/candidates/${TEST_CANDIDATES[0]}" 200
}

# Rerank service tests (hh-rerank-svc, port 7103)
test_rerank_service() {
  print_section "🎯 Rerank Service (hh-rerank-svc)"

  run_test "Rerank service health" "GET" "/v1/rerank/health" 200

  # Test reranking with sample candidates
  local rerank_payload
  rerank_payload=$(cat <<EOF
{
  "query": "Python developer with AI experience",
  "candidates": [
    {
      "id": "${TEST_CANDIDATES[0]}",
      "score": 0.85,
      "text": "Senior Python developer with 10 years experience in AI/ML"
    },
    {
      "id": "${TEST_CANDIDATES[1]}",
      "score": 0.78,
      "text": "Full-stack developer with Python and JavaScript expertise"
    },
    {
      "id": "${TEST_CANDIDATES[2]}",
      "score": 0.82,
      "text": "Machine learning engineer specializing in NLP and computer vision"
    }
  ],
  "limit": 3
}
EOF
)

  run_test "Rerank candidates" "POST" "/v1/rerank" 200 "$rerank_payload"

  # Test cache metrics
  run_test "Rerank cache metrics" "GET" "/v1/rerank/metrics" 200
}

# Messages service tests (hh-msgs-svc, port 7106)
test_msgs_service() {
  print_section "📬 Messages Service (hh-msgs-svc)"

  run_test "Messages service health" "GET" "/v1/msgs/health" 200

  # Test skill expansion
  local skill_payload
  skill_payload=$(cat <<EOF
{
  "skill": "Python",
  "context": "software development"
}
EOF
)

  run_test "Expand skill taxonomy" "POST" "/v1/skills/expand" 200 "$skill_payload"

  # Test notification queue
  local notification_payload
  notification_payload=$(cat <<EOF
{
  "type": "candidate_match",
  "tenantId": "${TENANT_ID}",
  "recipientId": "test-recruiter-123",
  "data": {
    "candidateId": "${TEST_CANDIDATES[0]}",
    "jobId": "test-job-456",
    "score": 0.92
  }
}
EOF
)

  run_test "Queue notification" "POST" "/v1/msgs/notify" 202 "$notification_payload"
}

# Evidence service tests (hh-evidence-svc, port 7104)
test_evidence_service() {
  print_section "📋 Evidence Service (hh-evidence-svc)"

  run_test "Evidence service health" "GET" "/v1/evidence/health" 200

  # Test evidence retrieval for test candidate
  run_test "Get candidate evidence" "GET" "/v1/evidence/candidates/${TEST_CANDIDATES[0]}" 200

  # Test provenance trail
  run_test "Get provenance trail" "GET" "/v1/evidence/provenance/${TEST_CANDIDATES[0]}" 200

  # Test audit log
  local audit_query="startDate=2024-01-01&endDate=2025-12-31&limit=10"
  run_test "Query audit logs" "GET" "/v1/evidence/audit?${audit_query}" 200
}

# ECO service tests (hh-eco-svc, port 7105)
test_eco_service() {
  print_section "🏢 ECO Service (hh-eco-svc)"

  run_test "ECO service health" "GET" "/v1/eco/health" 200

  # Test occupation validation
  local validate_payload
  validate_payload=$(cat <<EOF
{
  "title": "Software Engineer",
  "description": "Develops and maintains software applications",
  "skills": ["Python", "Java", "SQL"]
}
EOF
)

  run_test "Validate occupation" "POST" "/v1/eco/validate" 200 "$validate_payload"

  # Test occupation search
  run_test "Search occupations" "GET" "/v1/eco/occupations?query=engineer&limit=5" 200

  # Test occupation normalization
  local normalize_payload
  normalize_payload=$(cat <<EOF
{
  "title": "Senior Full Stack Developer"
}
EOF
)

  run_test "Normalize occupation title" "POST" "/v1/eco/normalize" 200 "$normalize_payload"

  # Test ECO templates
  run_test "Get ECO templates" "GET" "/v1/eco/templates?category=technology" 200
}

# Enrich service tests (hh-enrich-svc, port 7108)
test_enrich_service() {
  print_section "✨ Enrich Service (hh-enrich-svc)"

  run_test "Enrich service health" "GET" "/v1/enrich/health" 200

  # Test profile enrichment
  local enrich_payload
  enrich_payload=$(cat <<EOF
{
  "candidateId": "${TEST_CANDIDATES[0]}",
  "enrichmentType": "full",
  "options": {
    "includeSkills": true,
    "includeCareerTrajectory": true,
    "includeMarketInsights": true
  }
}
EOF
)

  run_test "Enrich candidate profile" "POST" "/v1/enrich/profile" 202 "$enrich_payload"

  # Test enrichment status
  run_test "Check enrichment status" "GET" "/v1/enrich/status/${TEST_CANDIDATES[0]}" 200

  # Test batch enrichment job
  local batch_enrich_payload
  batch_enrich_payload=$(cat <<EOF
{
  "candidateIds": ["${TEST_CANDIDATES[0]}", "${TEST_CANDIDATES[1]}", "${TEST_CANDIDATES[2]}"],
  "enrichmentType": "skills_only",
  "priority": "normal"
}
EOF
)

  run_test "Submit batch enrichment job" "POST" "/v1/enrich/batch" 202 "$batch_enrich_payload"
}

# Integration test: Full candidate search pipeline
test_integration_search_pipeline() {
  print_section "🔗 Integration Test: Full Search Pipeline"

  log_info "Testing end-to-end search flow: embed → search → rerank → evidence"

  local job_description="Looking for a Senior Python Engineer with cloud infrastructure experience, 8+ years in backend development, strong in AWS or GCP, experience with microservices architecture and CI/CD pipelines."

  # Step 1: Generate embedding for job description
  local embed_result
  embed_result=$(curl -s \
    -X POST \
    -H "X-API-Key: $API_KEY" \
    -H "X-Tenant-ID: $TENANT_ID" \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"$job_description\"}" \
    "${GATEWAY_URL}/v1/embeddings/generate")

  if echo "$embed_result" | jq -e '.embedding' >/dev/null 2>&1; then
    log_success "Step 1/4: Embedding generated"
  else
    log_error "Step 1/4: Failed to generate embedding"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    return 1
  fi

  # Step 2: Perform semantic search
  local search_result
  search_result=$(curl -s \
    -X POST \
    -H "X-API-Key: $API_KEY" \
    -H "X-Tenant-ID: $TENANT_ID" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$job_description\", \"limit\": 10}" \
    "${GATEWAY_URL}/v1/search")

  if echo "$search_result" | jq -e '.results | length > 0' >/dev/null 2>&1; then
    local result_count
    result_count=$(echo "$search_result" | jq '.results | length')
    log_success "Step 2/4: Search returned $result_count candidates"
  else
    log_error "Step 2/4: Search returned no results"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    return 1
  fi

  # Step 3: Rerank top candidates
  local top_candidates
  top_candidates=$(echo "$search_result" | jq -c '[.results[0:5] | .[] | {id: .id, score: .score, text: .summary}]')

  local rerank_result
  rerank_result=$(curl -s \
    -X POST \
    -H "X-API-Key: $API_KEY" \
    -H "X-Tenant-ID: $TENANT_ID" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$job_description\", \"candidates\": $top_candidates, \"limit\": 3}" \
    "${GATEWAY_URL}/v1/rerank")

  if echo "$rerank_result" | jq -e '.results | length > 0' >/dev/null 2>&1; then
    local rerank_count
    rerank_count=$(echo "$rerank_result" | jq '.results | length')
    log_success "Step 3/4: Reranked to top $rerank_count candidates"
  else
    log_error "Step 3/4: Rerank failed"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    return 1
  fi

  # Step 4: Fetch evidence for top candidate
  local top_candidate_id
  top_candidate_id=$(echo "$rerank_result" | jq -r '.results[0].id')

  local evidence_result
  evidence_result=$(curl -s \
    -H "X-API-Key: $API_KEY" \
    -H "X-Tenant-ID: $TENANT_ID" \
    "${GATEWAY_URL}/v1/evidence/candidates/${top_candidate_id}")

  if echo "$evidence_result" | jq -e '.evidence' >/dev/null 2>&1; then
    log_success "Step 4/4: Evidence retrieved for candidate $top_candidate_id"
    log_success "✅ Full search pipeline completed successfully"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    return 0
  else
    log_error "Step 4/4: Failed to retrieve evidence"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    return 1
  fi
}

# Generate test report
generate_report() {
  print_section "📊 Test Results Summary"

  local total=$TESTS_RUN
  local pass_rate=0

  if [[ $total -gt 0 ]]; then
    pass_rate=$(awk "BEGIN {printf \"%.1f\", ($TESTS_PASSED / $total) * 100}")
  fi

  echo
  echo -e "  Total tests run:    ${COLOR_CYAN}$total${COLOR_RESET}"
  echo -e "  ${COLOR_GREEN}✅ Passed:${COLOR_RESET}         $TESTS_PASSED"
  echo -e "  ${COLOR_RED}❌ Failed:${COLOR_RESET}         $TESTS_FAILED"
  echo -e "  ${COLOR_YELLOW}⏭  Skipped:${COLOR_RESET}        $TESTS_SKIPPED"
  echo -e "  ${COLOR_BLUE}Pass rate:${COLOR_RESET}         ${pass_rate}%"
  echo

  if [[ $TESTS_FAILED -eq 0 ]]; then
    echo -e "${COLOR_GREEN}═══════════════════════════════════════════════════════════${COLOR_RESET}"
    echo -e "${COLOR_GREEN}  🎉 ALL TESTS PASSED! Production deployment is healthy.${COLOR_RESET}"
    echo -e "${COLOR_GREEN}═══════════════════════════════════════════════════════════${COLOR_RESET}"
    echo
    return 0
  else
    echo -e "${COLOR_RED}═══════════════════════════════════════════════════════════${COLOR_RESET}"
    echo -e "${COLOR_RED}  ❌ SOME TESTS FAILED. Please investigate the failures.${COLOR_RESET}"
    echo -e "${COLOR_RED}═══════════════════════════════════════════════════════════${COLOR_RESET}"
    echo

    # Show failed tests
    echo -e "${COLOR_RED}Failed tests:${COLOR_RESET}"
    for result in "${TEST_RESULTS[@]}"; do
      if [[ "$result" =~ ^FAIL ]]; then
        local test_name
        test_name=$(echo "$result" | cut -d'|' -f2)
        local details
        details=$(echo "$result" | cut -d'|' -f3-)
        echo -e "  ${COLOR_RED}•${COLOR_RESET} $test_name ($details)"
      fi
    done
    echo
    return 1
  fi
}

# Main execution
main() {
  parse_args "$@"

  # Print header
  clear
  echo -e "${COLOR_BLUE}╔═══════════════════════════════════════════════════════════╗${COLOR_RESET}"
  echo -e "${COLOR_BLUE}║                                                           ║${COLOR_RESET}"
  echo -e "${COLOR_BLUE}║     🚀 Headhunter Production Smoke Test Suite 🚀         ║${COLOR_RESET}"
  echo -e "${COLOR_BLUE}║                                                           ║${COLOR_RESET}"
  echo -e "${COLOR_BLUE}╚═══════════════════════════════════════════════════════════╝${COLOR_RESET}"
  echo

  log_info "Project ID:    $PROJECT_ID"
  log_info "Gateway URL:   $GATEWAY_URL"
  log_info "Tenant ID:     $TENANT_ID"
  echo

  # Setup
  check_dependencies
  fetch_api_key

  log "🏁 Starting comprehensive smoke tests..."
  echo

  # Run test suites
  test_gateway_health
  test_admin_service
  test_embed_service
  test_search_service
  test_rerank_service
  test_msgs_service
  test_evidence_service
  test_eco_service
  test_enrich_service

  # Run integration tests
  test_integration_search_pipeline

  # Generate report and exit
  if generate_report; then
    exit 0
  else
    exit 1
  fi
}

# Run main function
main "$@"
