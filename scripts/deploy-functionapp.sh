#!/usr/bin/env bash
set -euo pipefail

# Azure-native deployment for Azure Functions using Core Tools publish.
# Defaults target the Terraform-managed dev environment.
#
# Optional env vars:
#   RESOURCE_GROUP (default: rg-filenamestandardizer-dev)
#   FUNCTION_APP_NAME (default: func-standardizer-dev)
#   RUN_SMOKE_TEST (default: false)
#   DEPLOY_WAIT_ATTEMPTS (default: 12)
#   DEPLOY_WAIT_SECONDS (default: 10)

RESOURCE_GROUP="${RESOURCE_GROUP:-rg-filenamestandardizer-dev}"
FUNCTION_APP_NAME="${FUNCTION_APP_NAME:-func-standardizer-dev}"
RUN_SMOKE_TEST="${RUN_SMOKE_TEST:-false}"
DEPLOY_WAIT_ATTEMPTS="${DEPLOY_WAIT_ATTEMPTS:-12}"
DEPLOY_WAIT_SECONDS="${DEPLOY_WAIT_SECONDS:-10}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd"
    exit 1
  fi
}

require_cmd az
require_cmd func

if [[ ! -f requirements.txt || ! -f function_app.py || ! -f host.json ]]; then
  echo "Run this script from the repository root context; required files missing."
  exit 1
fi

if [[ ! "$DEPLOY_WAIT_ATTEMPTS" =~ ^[0-9]+$ || ! "$DEPLOY_WAIT_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "DEPLOY_WAIT_ATTEMPTS and DEPLOY_WAIT_SECONDS must be integers."
  exit 1
fi

echo "Checking Azure login context..."
az account show >/dev/null

echo "Validating target Function App exists: ${RESOURCE_GROUP}/${FUNCTION_APP_NAME}"
az functionapp show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FUNCTION_APP_NAME" \
  --query "{name:name,state:state,defaultHostName:defaultHostName}" \
  -o table

echo "Deploying with Azure Functions Core Tools (remote build)..."
func azure functionapp publish "$FUNCTION_APP_NAME" --python --build remote

echo "Waiting for function host to load functions..."
for ((i=1; i<=DEPLOY_WAIT_ATTEMPTS; i++)); do
  fn_count=$(az functionapp function list \
    --resource-group "$RESOURCE_GROUP" \
    --name "$FUNCTION_APP_NAME" \
    --query "length([])" \
    -o tsv 2>/dev/null || echo "0")

  if [[ "$fn_count" =~ ^[0-9]+$ ]] && [[ "$fn_count" -gt 0 ]]; then
    echo "Deployment verified: ${fn_count} function(s) loaded."
    az functionapp function list \
      --resource-group "$RESOURCE_GROUP" \
      --name "$FUNCTION_APP_NAME" \
      --query "[].name" \
      -o tsv

    if [[ "$RUN_SMOKE_TEST" == "true" ]]; then
      echo "Running post-deploy smoke test..."
      RESOURCE_GROUP="$RESOURCE_GROUP" FUNCTION_APP_NAME="$FUNCTION_APP_NAME" \
        "$ROOT_DIR/scripts/deployment-smoke-test.sh"
    fi

    exit 0
  fi

  echo "Host not ready yet (${i}/${DEPLOY_WAIT_ATTEMPTS}). Retrying in ${DEPLOY_WAIT_SECONDS}s..."
  sleep "$DEPLOY_WAIT_SECONDS"
done

echo "Deployment finished but function host did not report loaded functions in time."
echo "Check runtime logs: az webapp log tail -g ${RESOURCE_GROUP} -n ${FUNCTION_APP_NAME} --provider application"
exit 2
