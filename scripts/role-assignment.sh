#!/usr/bin/bash
set -euo pipefail

# Assign required RBAC roles for the Function App on the storage account.

USER_ID=$(az ad signed-in-user show --query id -o tsv)
ACCOUNT_ID=$(az storage account show -n mymedia --query id -o tsv)

# List current role assignments
az role assignment list \
  --assignee "$USER_ID" \
  --scope "$ACCOUNT_ID" \
  --output table

# Assign roles
az role assignment create \
  --assignee "$USER_ID" \
  --role "Storage Blob Data Contributor" \
  --scope "$ACCOUNT_ID"

az role assignment create \
  --assignee "$USER_ID" \
  --role "Storage Blob Delegator" \
  --scope "$ACCOUNT_ID"

az role assignment create \
  --assignee "$USER_ID" \
  --role "Storage Queue Data Contributor" \
  --scope "$ACCOUNT_ID"
