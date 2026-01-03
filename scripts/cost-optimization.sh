#!/bin/bash
# =============================================================================
# Headhunter AI - Cost Optimization Script
# Generated: 2026-01-01
# =============================================================================
#
# This script provides cost optimization commands for the Headhunter AI project.
# Run sections individually based on your needs.
#
# ESTIMATED SAVINGS:
#   - Phase 1 (Quick Wins): ~$80-100/month
#   - Phase 2 (Cleanup): ~$20-40/month
#   - Total potential: ~$100-140/month (20-27% reduction)
#
# =============================================================================

set -e

PROJECT_ID="headhunter-ai-0088"
REGION="us-central1"

echo "=================================================="
echo "  Headhunter AI Cost Optimization Script"
echo "  Project: $PROJECT_ID"
echo "  Region: $REGION"
echo "=================================================="

# -----------------------------------------------------------------------------
# PHASE 1: QUICK WINS (Already Applied)
# -----------------------------------------------------------------------------
phase1_quick_wins() {
    echo ""
    echo "=== PHASE 1: Quick Wins ==="
    echo ""

    # 1. Set min-instances=0 for search service
    echo "1. Setting min-instances=0 for hh-search-svc-production..."
    gcloud run services update hh-search-svc-production \
        --project=$PROJECT_ID \
        --region=$REGION \
        --min-instances=0 \
        --cpu-throttling \
        --quiet
    echo "   ✅ Done - Saves ~$30-50/month"

    # 2. Increase cache TTLs
    echo ""
    echo "2. Increasing cache TTLs..."
    gcloud run services update hh-search-svc-production \
        --project=$PROJECT_ID \
        --region=$REGION \
        --update-env-vars="SEARCH_CACHE_TTL_SECONDS=600" \
        --quiet

    gcloud run services update hh-rerank-svc-production \
        --project=$PROJECT_ID \
        --region=$REGION \
        --update-env-vars="RERANK_CACHE_TTL_SECONDS=900" \
        --quiet
    echo "   ✅ Done - Reduces API calls by ~30-50%"

    echo ""
    echo "Phase 1 Complete! Estimated savings: ~$50-80/month"
}

# -----------------------------------------------------------------------------
# PHASE 2: DELETE UNUSED CLOUD FUNCTIONS
# -----------------------------------------------------------------------------
phase2_cleanup_unused() {
    echo ""
    echo "=== PHASE 2: Delete Unused Cloud Functions ==="
    echo ""
    echo "⚠️  WARNING: This will permanently delete these services."
    echo "    Make sure you don't need them before proceeding."
    echo ""
    read -p "Continue? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "Aborted."
        return
    fi

    # One-time migration functions (no longer needed)
    MIGRATION_FUNCTIONS=(
        "backfillclassifications"
        "backfillllmclassifications"
        "migratecandidates"
        "initagencymodel"
        "getclassificationstats"
        "getllmclassificationstats"
    )

    echo ""
    echo "Deleting one-time migration functions..."
    for func in "${MIGRATION_FUNCTIONS[@]}"; do
        echo "  Deleting $func..."
        gcloud run services delete "$func" \
            --project=$PROJECT_ID \
            --region=$REGION \
            --quiet 2>/dev/null || echo "    (already deleted or not found)"
    done

    # Debug/test functions
    DEBUG_FUNCTIONS=(
        "debugsearch"
        "connectivity-test"
        "inspectcandidate"
    )

    echo ""
    echo "Deleting debug/test functions..."
    for func in "${DEBUG_FUNCTIONS[@]}"; do
        echo "  Deleting $func..."
        gcloud run services delete "$func" \
            --project=$PROJECT_ID \
            --region=$REGION \
            --quiet 2>/dev/null || echo "    (already deleted or not found)"
    done

    echo ""
    echo "Phase 2 Complete! Estimated savings: ~$20-40/month"
}

# -----------------------------------------------------------------------------
# PHASE 3: AGGRESSIVE COST REDUCTION (Use with caution)
# -----------------------------------------------------------------------------
phase3_aggressive() {
    echo ""
    echo "=== PHASE 3: Aggressive Cost Reduction ==="
    echo ""
    echo "⚠️  WARNING: This will stop Cloud SQL and reduce service availability."
    echo "    Use this only if the system is not actively used."
    echo ""
    read -p "Continue? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "Aborted."
        return
    fi

    # Stop Cloud SQL (saves ~$25/month for db-g1-small)
    echo "Stopping Cloud SQL instance..."
    gcloud sql instances patch sql-hh-core \
        --project=$PROJECT_ID \
        --activation-policy=NEVER \
        --quiet
    echo "   ✅ Cloud SQL stopped"

    echo ""
    echo "Phase 3 Complete!"
    echo "To restart Cloud SQL: gcloud sql instances patch sql-hh-core --activation-policy=ALWAYS --quiet"
}

# -----------------------------------------------------------------------------
# STATUS: Check current configuration
# -----------------------------------------------------------------------------
check_status() {
    echo ""
    echo "=== Current Infrastructure Status ==="
    echo ""

    echo "📦 Cloud SQL:"
    gcloud sql instances describe sql-hh-core \
        --project=$PROJECT_ID \
        --format="table(name,settings.tier,settings.activationPolicy,state)" 2>/dev/null || echo "  Not found"

    echo ""
    echo "🗄️ Redis:"
    gcloud redis instances list \
        --project=$PROJECT_ID \
        --region=$REGION \
        --format="table(name,tier,memorySizeGb,state)" 2>/dev/null || echo "  Not found"

    echo ""
    echo "🚀 Fastify Services (min/max instances):"
    gcloud run services list \
        --project=$PROJECT_ID \
        --region=$REGION \
        --filter="metadata.name~hh-.*-production" \
        --format="table(metadata.name,spec.template.metadata.annotations.'autoscaling.knative.dev/minScale',spec.template.metadata.annotations.'autoscaling.knative.dev/maxScale')" 2>/dev/null

    echo ""
    echo "📊 Total Cloud Run Services:"
    gcloud run services list \
        --project=$PROJECT_ID \
        --region=$REGION \
        --format="value(metadata.name)" 2>/dev/null | wc -l | xargs echo "  Count:"
}

# -----------------------------------------------------------------------------
# COST REPORT: Estimate current monthly costs
# -----------------------------------------------------------------------------
cost_report() {
    echo ""
    echo "=== Estimated Monthly Costs ==="
    echo ""
    echo "Based on current configuration:"
    echo ""

    # Check Cloud SQL tier
    SQL_TIER=$(gcloud sql instances describe sql-hh-core --project=$PROJECT_ID --format="value(settings.tier)" 2>/dev/null || echo "unknown")
    SQL_STATE=$(gcloud sql instances describe sql-hh-core --project=$PROJECT_ID --format="value(state)" 2>/dev/null || echo "unknown")

    case $SQL_TIER in
        "db-f1-micro") SQL_COST="~\$10" ;;
        "db-g1-small") SQL_COST="~\$25" ;;
        "db-custom-2-7680") SQL_COST="~\$100" ;;
        *) SQL_COST="unknown" ;;
    esac

    if [[ "$SQL_STATE" != "RUNNABLE" ]]; then
        SQL_COST="\$0 (stopped)"
    fi

    echo "  Cloud SQL ($SQL_TIER): $SQL_COST/month"

    # Check Redis
    REDIS_TIER=$(gcloud redis instances describe redis-skills-us-central1 --project=$PROJECT_ID --region=$REGION --format="value(tier)" 2>/dev/null || echo "none")
    case $REDIS_TIER in
        "BASIC") REDIS_COST="~\$15" ;;
        "STANDARD_HA") REDIS_COST="~\$45" ;;
        "none") REDIS_COST="\$0 (not deployed)" ;;
        *) REDIS_COST="unknown" ;;
    esac
    echo "  Redis ($REDIS_TIER): $REDIS_COST/month"

    # Cloud Run (estimate based on count)
    SERVICE_COUNT=$(gcloud run services list --project=$PROJECT_ID --region=$REGION --format="value(metadata.name)" 2>/dev/null | wc -l)
    echo "  Cloud Run ($SERVICE_COUNT services): ~\$50-100/month (pay per use)"

    echo ""
    echo "  Vertex AI (embeddings): Usage-based"
    echo "  Gemini API (reranking): Usage-based"
    echo ""
    echo "Note: Actual costs depend on usage. Check Cloud Billing for precise numbers."
}

# -----------------------------------------------------------------------------
# HELP
# -----------------------------------------------------------------------------
show_help() {
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  status      Check current infrastructure configuration"
    echo "  cost        Show estimated monthly costs"
    echo "  phase1      Apply quick wins (safe, recommended)"
    echo "  phase2      Delete unused Cloud Functions"
    echo "  phase3      Aggressive reduction (stops Cloud SQL)"
    echo "  all         Run all phases (with confirmations)"
    echo ""
    echo "Examples:"
    echo "  $0 status   # Check current state"
    echo "  $0 phase1   # Apply quick wins"
    echo ""
}

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
case "${1:-help}" in
    status)
        check_status
        ;;
    cost)
        cost_report
        ;;
    phase1)
        phase1_quick_wins
        ;;
    phase2)
        phase2_cleanup_unused
        ;;
    phase3)
        phase3_aggressive
        ;;
    all)
        phase1_quick_wins
        phase2_cleanup_unused
        echo ""
        echo "Phase 3 (aggressive) skipped. Run '$0 phase3' separately if needed."
        ;;
    *)
        show_help
        ;;
esac

echo ""
echo "Done!"
