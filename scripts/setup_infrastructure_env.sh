#!/usr/bin/env bash
set -euo pipefail

# shellcheck disable=SC2034

SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENV_FILE="${1:-${PROJECT_ROOT}/.env}"

if [[ -f "${ENV_FILE}" ]]; then
  # Export variables defined in the env file so downstream scripts can see them.
  set -a
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  set +a
else
  echo "Environment file '${ENV_FILE}' not found. Continuing with existing environment variables." >&2
fi

# Defaults for optional variables. These can be overridden via the env file or environment.
export GOOGLE_CLOUD_REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
export GOOGLE_CLOUD_ZONE="${GOOGLE_CLOUD_ZONE:-${GOOGLE_CLOUD_REGION}-b}"
export INFRA_ENVIRONMENT="${INFRA_ENVIRONMENT:-dev}"

export PGVECTOR_INSTANCE_NAME="${PGVECTOR_INSTANCE_NAME:-headhunter-pgvector-${INFRA_ENVIRONMENT}}"
export PGVECTOR_DATABASE_NAME="${PGVECTOR_DATABASE_NAME:-pgvector}" # primary vector DB
export PGVECTOR_APP_USER="${PGVECTOR_APP_USER:-pgvector_app}"
export PGVECTOR_APP_PASSWORD="${PGVECTOR_APP_PASSWORD:-}" # must be provided
export PGVECTOR_SECRET_NAME="${PGVECTOR_SECRET_NAME:-pgvector-dsn-${INFRA_ENVIRONMENT}}"

export ECO_DATABASE_NAME="${ECO_DATABASE_NAME:-eco}" # canonical occupations DB
export ECO_APP_USER="${ECO_APP_USER:-eco_app}"
export ECO_APP_PASSWORD="${ECO_APP_PASSWORD:-}" # must be provided
export ECO_SECRET_NAME="${ECO_SECRET_NAME:-eco-dsn-${INFRA_ENVIRONMENT}}"

export CLOUD_SQL_ADMIN_USER="${CLOUD_SQL_ADMIN_USER:-postgres}"
export CLOUD_SQL_ADMIN_PASSWORD="${CLOUD_SQL_ADMIN_PASSWORD:-}" # must be provided

export CLOUD_SQL_TIER="${CLOUD_SQL_TIER:-db-custom-1-3840}" # shared instance tier
export CLOUD_SQL_DISK_SIZE_GB="${CLOUD_SQL_DISK_SIZE_GB:-100}"
export CLOUD_SQL_DISK_TYPE="${CLOUD_SQL_DISK_TYPE:-PD_SSD}"
export CLOUD_SQL_BACKUP_ENABLED="${CLOUD_SQL_BACKUP_ENABLED:-true}"
export BACKUP_START_TIME="${BACKUP_START_TIME:-03:00}"
export RETAINED_BACKUPS_COUNT="${RETAINED_BACKUPS_COUNT:-15}"
export RETAINED_XLOG_DAYS="${RETAINED_XLOG_DAYS:-14}"
export SHARED_BUFFERS="${SHARED_BUFFERS:-2GB}"
export MAX_CONNECTIONS="${MAX_CONNECTIONS:-200}"

export ECO_REDIS_INSTANCE_NAME="${ECO_REDIS_INSTANCE_NAME:-headhunter-eco-redis-${INFRA_ENVIRONMENT}}"
export ECO_REDIS_REGION="${ECO_REDIS_REGION:-${GOOGLE_CLOUD_REGION}}"
export ECO_REDIS_TIER="${ECO_REDIS_TIER:-STANDARD_HA}"
export ECO_REDIS_SIZE_GB="${ECO_REDIS_SIZE_GB:-1}"
export ECO_REDIS_SECRET_NAME="${ECO_REDIS_SECRET_NAME:-eco-redis-url-${INFRA_ENVIRONMENT}}"

export ECO_SERVICE_ACCOUNT="${ECO_SERVICE_ACCOUNT:-eco-service@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com}"
export PGVECTOR_SERVICE_ACCOUNT="${PGVECTOR_SERVICE_ACCOUNT:-pgvector-service@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com}"

missing=0
require_var() {
  local var_name="$1"
  local description="$2"
  if [[ -z "${!var_name:-}" ]]; then
    echo "[setup_infrastructure_env] Missing required variable: ${var_name} (${description})" >&2
    missing=1
  fi
}

require_var GOOGLE_CLOUD_PROJECT "Target Google Cloud project ID"
require_var PGVECTOR_APP_PASSWORD "Password for pgvector application user"
require_var ECO_APP_PASSWORD "Password for ECO application user"
require_var CLOUD_SQL_ADMIN_PASSWORD "Password for Cloud SQL admin user"
require_var PGVECTOR_SECRET_NAME "Secret name for pgvector DSN"
require_var ECO_SECRET_NAME "Secret name for ECO DSN"
require_var ECO_REDIS_SECRET_NAME "Secret name for ECO Redis connection"

if [[ ${missing} -ne 0 ]]; then
  echo "One or more required environment variables are missing. Please set them in ${ENV_FILE} or export them before rerunning." >&2
  exit 1
fi

cat <<INFO
Infrastructure environment configured:
  Project: ${GOOGLE_CLOUD_PROJECT}
  Region: ${GOOGLE_CLOUD_REGION}
  Cloud SQL instance: ${PGVECTOR_INSTANCE_NAME}
  pgvector DB: ${PGVECTOR_DATABASE_NAME}
  ECO DB: ${ECO_DATABASE_NAME}
  Redis instance: ${ECO_REDIS_INSTANCE_NAME} (${ECO_REDIS_REGION})
INFO
