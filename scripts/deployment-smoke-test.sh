#!/usr/bin/env bash
set -euo pipefail

# Smoke test: upload a sample blob to the trigger path and verify it was routed.
# Optional env vars:
#   STORAGE_ACCOUNT_NAME
#   RESOURCE_GROUP (default: rg-filenamestandardizer-dev)
#   FUNCTION_APP_NAME (default: func-standardizer-dev)
#   DEVICE_ID (default: canary-device)
#   SOURCE_CONTAINER (default: landing-zone)
#   PROCESSED_CONTAINER (default: processed)
#   FAILED_CONTAINER (default: failed)
#   LOCAL_TEST_FILE (default: /tmp/canary-upload.jpg)

RESOURCE_GROUP="${RESOURCE_GROUP:-rg-filenamestandardizer-dev}"
FUNCTION_APP_NAME="${FUNCTION_APP_NAME:-func-standardizer-dev}"
AUTH_MODE="${AUTH_MODE:-login}"
account_key=""

if [[ -z "${STORAGE_ACCOUNT_NAME:-}" ]]; then
  echo "STORAGE_ACCOUNT_NAME not provided; discovering from ${FUNCTION_APP_NAME} app settings"
  conn_string=$(az functionapp config appsettings list \
    --resource-group "$RESOURCE_GROUP" \
    --name "$FUNCTION_APP_NAME" \
    --query "[?name=='AzureWebJobsStorage'].value | [0]" \
    -o tsv)

  if [[ -z "$conn_string" || "$conn_string" == "null" ]]; then
    echo "Unable to resolve AzureWebJobsStorage from Function App settings"
    echo "Set STORAGE_ACCOUNT_NAME explicitly or verify RESOURCE_GROUP/FUNCTION_APP_NAME"
    exit 1
  fi

  STORAGE_ACCOUNT_NAME=$(echo "$conn_string" | sed -n 's/.*AccountName=\([^;]*\).*/\1/p')
  account_key=$(echo "$conn_string" | sed -n 's/.*AccountKey=\([^;]*\).*/\1/p')
fi

if [[ -z "${STORAGE_ACCOUNT_NAME:-}" ]]; then
  echo "Missing STORAGE_ACCOUNT_NAME (auto-discovery failed)"
  exit 1
fi

echo "Using storage account: ${STORAGE_ACCOUNT_NAME}"

if [[ "$AUTH_MODE" == "key" && -z "$account_key" ]]; then
  conn_string=$(az functionapp config appsettings list \
    --resource-group "$RESOURCE_GROUP" \
    --name "$FUNCTION_APP_NAME" \
    --query "[?name=='AzureWebJobsStorage'].value | [0]" \
    -o tsv)
  account_key=$(echo "$conn_string" | sed -n 's/.*AccountKey=\([^;]*\).*/\1/p')
fi

auth_args=(--auth-mode login)
if [[ "$AUTH_MODE" == "key" ]]; then
  auth_args=(--account-key "$account_key")
fi

DEVICE_ID="${DEVICE_ID:-canary-device}"
SOURCE_CONTAINER="${SOURCE_CONTAINER:-landing-zone}"
PROCESSED_CONTAINER="${PROCESSED_CONTAINER:-processed}"
FAILED_CONTAINER="${FAILED_CONTAINER:-failed}"
LOCAL_TEST_FILE="${LOCAL_TEST_FILE:-/tmp/canary-upload.jpg}"
INPUT_NAME="${INPUT_NAME:-20240724_182842.jpg}"
BLOB_PATH="devices/${DEVICE_ID}/${INPUT_NAME}"
EXPECTED_PROCESSED_PREFIX="2024/07/20240724T182842_${DEVICE_ID}_"

if [[ ! -f "$LOCAL_TEST_FILE" ]]; then
  # Create a tiny placeholder file for smoke tests.
  echo "smoke-test" > "$LOCAL_TEST_FILE"
fi

echo "Uploading ${LOCAL_TEST_FILE} to ${SOURCE_CONTAINER}/${BLOB_PATH}"
if ! az storage blob upload \
  "${auth_args[@]}" \
  --account-name "$STORAGE_ACCOUNT_NAME" \
  --container-name "$SOURCE_CONTAINER" \
  --name "$BLOB_PATH" \
  --file "$LOCAL_TEST_FILE" \
  --overwrite; then
  if [[ "$AUTH_MODE" == "login" ]]; then
    echo "Login-based upload failed; retrying with account key from Function App settings"
    conn_string=$(az functionapp config appsettings list \
      --resource-group "$RESOURCE_GROUP" \
      --name "$FUNCTION_APP_NAME" \
      --query "[?name=='AzureWebJobsStorage'].value | [0]" \
      -o tsv)
    account_key=$(echo "$conn_string" | sed -n 's/.*AccountKey=\([^;]*\).*/\1/p')

    if [[ -z "$account_key" ]]; then
      echo "Unable to extract storage account key for fallback authentication"
      exit 1
    fi

    auth_args=(--account-key "$account_key")
    az storage blob upload \
      "${auth_args[@]}" \
      --account-name "$STORAGE_ACCOUNT_NAME" \
      --container-name "$SOURCE_CONTAINER" \
      --name "$BLOB_PATH" \
      --file "$LOCAL_TEST_FILE" \
      --overwrite
  else
    exit 1
  fi
fi

# Give the trigger some time to process on Consumption plans.
ATTEMPTS=5
SLEEP_SECONDS=10

for ((i=1; i<=ATTEMPTS; i++)); do
  echo "Check ${i}/${ATTEMPTS}: looking for processed/failed result"

  if az storage blob list \
    "${auth_args[@]}" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --container-name "$PROCESSED_CONTAINER" \
    --prefix "$EXPECTED_PROCESSED_PREFIX" \
    --query "length([])" \
    -o tsv | grep -qE '^[1-9]'; then
    echo "SUCCESS: Blob processed into ${PROCESSED_CONTAINER}"
    exit 0
  fi

  if az storage blob exists \
    "${auth_args[@]}" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --container-name "$FAILED_CONTAINER" \
    --name "${DEVICE_ID}/${INPUT_NAME}" \
    --query "exists" \
    -o tsv | grep -q '^true$'; then
    echo "WARNING: Blob routed to ${FAILED_CONTAINER}"
    exit 2
  fi

  sleep "$SLEEP_SECONDS"
done

echo "ERROR: No processed/failed result observed within timeout"
exit 3
