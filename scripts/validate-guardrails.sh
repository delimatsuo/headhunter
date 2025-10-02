#!/usr/bin/env bash
# Validate migration guardrails across the entire repository

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}

# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

DEPRECATED_PATH="/Users/delimatsuo/Documents/Coding/headhunter"
CANONICAL_PATH="/Volumes/Extreme Pro/myprojects/headhunter"
EXIT_CODE=0

echo "🔍 Validating migration guardrails..."
echo ""

# Check 1: Search for deprecated path references
echo "[1/5] Checking for deprecated path references..."
if grep -r "$DEPRECATED_PATH" \
  --exclude-dir=node_modules \
  --exclude-dir=.git \
  --exclude-dir=dist \
  --exclude-dir=build \
  --exclude-dir=.venv \
  --exclude='*.log' \
  --exclude='migration-log.txt' \
  --exclude='validate-guardrails.sh' \
  "${REPO_ROOT}" 2>/dev/null; then
  echo "❌ FAIL: Found deprecated path references"
  EXIT_CODE=1
else
  echo "✅ PASS: No deprecated path references found"
fi
echo ""

# Check 2: Verify shell scripts source repo_guard.sh
echo "[2/5] Checking shell scripts for repo guard..."
SCRIPTS_WITHOUT_GUARD=$(find "${REPO_ROOT}/scripts" -name '*.sh' -type f \
  ! -name 'repo_guard.sh' \
  ! -name 'validate-guardrails.sh' \
  -exec grep -L 'source.*repo_guard.sh' {} \; 2>/dev/null || true)

if [ -n "$SCRIPTS_WITHOUT_GUARD" ]; then
  echo "⚠️  WARNING: Scripts without repo guard:"
  echo "$SCRIPTS_WITHOUT_GUARD"
  echo ""
else
  echo "✅ PASS: All scripts source repo_guard.sh"
fi
echo ""

# Check 3: Verify Python scripts use dynamic path resolution
echo "[3/5] Checking Python scripts for dynamic paths..."
PYTHON_WITH_HARDCODED=$(grep -r "sys.path.append.*$DEPRECATED_PATH" \
  --include='*.py' \
  --exclude-dir=node_modules \
  --exclude-dir=.venv \
  "${REPO_ROOT}" 2>/dev/null || true)

if [ -n "$PYTHON_WITH_HARDCODED" ]; then
  echo "❌ FAIL: Found Python files with hardcoded paths:"
  echo "$PYTHON_WITH_HARDCODED"
  EXIT_CODE=1
else
  echo "✅ PASS: No Python files with hardcoded paths"
fi
echo ""

# Check 4: Verify documentation references canonical path
echo "[4/5] Checking documentation for canonical path references..."
DOCS_TO_CHECK=("README.md" "docs/HANDOVER.md" "PRD.md" "ARCHITECTURE.md")
for doc in "${DOCS_TO_CHECK[@]}"; do
  if [ -f "${REPO_ROOT}/${doc}" ]; then
    if grep -q "$CANONICAL_PATH" "${REPO_ROOT}/${doc}"; then
      echo "  ✅ ${doc} references canonical path"
    else
      echo "  ⚠️  ${doc} missing canonical path reference"
    fi
  fi
done
echo ""

# Check 5: Verify pre-commit hook exists
echo "[5/5] Checking for pre-commit hook..."
if [ -f "${REPO_ROOT}/.husky/pre-commit" ] || [ -f "${REPO_ROOT}/.git/hooks/pre-commit" ]; then
  echo "✅ PASS: Pre-commit hook exists"
else
  echo "⚠️  WARNING: No pre-commit hook found"
  echo "   Run: npm install husky --save-dev && npx husky install"
fi
echo ""

# Summary
echo "═══════════════════════════════════════"
if [ $EXIT_CODE -eq 0 ]; then
  echo "✅ All guardrail checks passed"
else
  echo "❌ Some guardrail checks failed"
  echo "   Review the output above and fix issues before tagging release"
fi
echo "═══════════════════════════════════════"

exit $EXIT_CODE
