#!/usr/bin/env bash
# Create the drive-migration-complete release tag

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}

# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

TAG_NAME="drive-migration-complete"
RELEASE_NOTES="${REPO_ROOT}/docs/RELEASE_NOTES_drive-migration-complete.md"

echo "🏷️  Creating release tag: ${TAG_NAME}"
echo ""

# Pre-flight checks
echo "[1/5] Running pre-flight checks..."

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
  echo "❌ ERROR: You have uncommitted changes"
  echo "   Please commit or stash changes before creating release tag"
  git status --short
  exit 1
fi
echo "✅ No uncommitted changes"

# Check we're on main/master branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$CURRENT_BRANCH" != "main" && "$CURRENT_BRANCH" != "master" ]]; then
  echo "⚠️  WARNING: Not on main/master branch (current: $CURRENT_BRANCH)"
  read -p "Continue anyway? (y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

# Check if tag already exists
if git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
  echo "❌ ERROR: Tag '$TAG_NAME' already exists"
  echo "   To recreate, first delete it: git tag -d $TAG_NAME"
  exit 1
fi
echo "✅ Tag name available"
echo ""

# Run guardrail validation
echo "[2/5] Validating guardrails..."
if ! "${SCRIPT_DIR}/validate-guardrails.sh"; then
  echo "❌ ERROR: Guardrail validation failed"
  echo "   Fix issues before creating release tag"
  exit 1
fi
echo ""

# Verify release notes exist
echo "[3/5] Checking release notes..."
if [ ! -f "$RELEASE_NOTES" ]; then
  echo "❌ ERROR: Release notes not found at $RELEASE_NOTES"
  exit 1
fi
echo "✅ Release notes found"
echo ""

# Show summary
echo "[4/5] Release summary:"
echo "   Tag name: $TAG_NAME"
echo "   Commit: $(git rev-parse --short HEAD)"
echo "   Branch: $CURRENT_BRANCH"
echo "   Date: $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
echo ""
echo "Release notes preview:"
head -n 20 "$RELEASE_NOTES"
echo "   ... (see full notes in $RELEASE_NOTES)"
echo ""

# Confirm
read -p "Create release tag? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Cancelled"
  exit 0
fi

# Create annotated tag
echo "[5/5] Creating annotated tag..."
TAG_MESSAGE="Release: Drive Migration Complete

This release marks the completion of the repository migration from iCloud Drive
to the canonical Extreme Pro drive location. All guardrails are in place to
prevent future regressions.

Key achievements:
- 100+ shell scripts enforce canonical path via repo_guard.sh
- All Python scripts use dynamic path resolution
- Pre-commit hooks prevent deprecated path references
- Comprehensive validation script for ongoing compliance
- Integration baseline maintained: cacheHitRate=1.0, rerank ≈0ms

See docs/RELEASE_NOTES_drive-migration-complete.md for complete details."

git tag -a "$TAG_NAME" -m "$TAG_MESSAGE"

echo ""
echo "✅ Tag created successfully!"
echo ""
echo "Next steps:"
echo "1. Review the tag: git show $TAG_NAME"
echo "2. Push to remote: git push origin $TAG_NAME"
echo "3. Create GitHub release with release notes"
echo "4. Update Task Master tickets to reference this tag"
echo ""
echo "To undo (before pushing): git tag -d $TAG_NAME"
