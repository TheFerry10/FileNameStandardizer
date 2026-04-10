#!/usr/bin/bash
set -euo pipefail
az storage account create \
  -n "$FUNC_STORAGE_ACCOUNT" \
  -g "$RESOURCE_GROUP" \
  -l "$REGION" \
  --sku Standard_LRS

az functionapp create \
  -n "$FUNCTION_APP_NAME" \
  -g "$RESOURCE_GROUP" \
  --storage-account "$FUNC_STORAGE_ACCOUNT" \
  --consumption-plan-location "$REGION" \
  --runtime python \
  --runtime-version 3.12 \
  --os-type Linux \
  --functions-version 4

az functionapp identity assign -n "$FUNCTION_APP_NAME" -g "$RESOURCE_GROUP"
