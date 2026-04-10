#!/usr/bin/bash

# Create an App Registration
APP_ID=$(az ad app create --display-name "github-deploy-FileNameStandardizer" --query appId -o tsv)

# Create a service principal
az ad sp create --id "$APP_ID"

# Add federated credential for your branch
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-actions-deploy",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:TheFerry10/FileNameStandardizer:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'

# Grant Contributor on the resource group
SP_ID=$(az ad sp show --id "$APP_ID" --query id -o tsv)
RG_ID=$(az group show -n "$RESOURCE_GROUP" --query id -o tsv)
az role assignment create --assignee "$SP_ID" --role Contributor --scope "$RG_ID"
