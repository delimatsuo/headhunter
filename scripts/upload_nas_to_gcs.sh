#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Sync NAS data to GCS buckets for processing
# Usage: ./scripts/upload_nas_to_gcs.sh headhunter-ai-0088 \
#        "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project"

PROJECT_ID="${1:-headhunter-ai-0088}"
NAS_DIR="${2:-}"  # Must be provided

if [[ -z "${NAS_DIR}" ]]; then
  echo "Provide NAS directory as second argument" >&2
  exit 1
fi

echo "Using project: ${PROJECT_ID}"
echo "NAS directory: ${NAS_DIR}"

gcloud config set project "${PROJECT_ID}"

# Buckets
RAW_CSV="gs://${PROJECT_ID}-raw-csv"
RAW_JSON="gs://${PROJECT_ID}-raw-json"
PROFILES="gs://${PROJECT_ID}-profiles"

# Create buckets if missing
gsutil mb -p "${PROJECT_ID}" -l us-central1 "${RAW_CSV}" || true
gsutil mb -p "${PROJECT_ID}" -l us-central1 "${RAW_JSON}" || true
gsutil mb -p "${PROJECT_ID}" -l us-central1 "${PROFILES}" || true

echo "Syncing CSV to ${RAW_CSV}..."
if [[ -d "${NAS_DIR}/CSV" ]]; then
  gsutil -m rsync -r "${NAS_DIR}/CSV" "${RAW_CSV}"
else
  echo "CSV subfolder not found at ${NAS_DIR}/CSV (skipping)" >&2
fi

echo "Syncing JSON set to ${RAW_JSON} (excluding enhanced_analysis & .DS_Store)..."
# Exclude macOS metadata and previously enhanced outputs to avoid huge, unneeded uploads
EXCLUDE_REGEX='(^|/)\.DS_Store$|(^|/)enhanced_analysis/.*'

# On macOS, disable multiprocessing due to known issues; keep multithreading
gsutil -m -o "GSUtil:parallel_process_count=1" rsync -r -x "${EXCLUDE_REGEX}" "${NAS_DIR}" "${RAW_JSON}"

echo "Done."
