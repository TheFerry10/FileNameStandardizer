# Terraform Infrastructure

This folder contains the Terraform configuration for provisioning the Azure infrastructure required by the Function App.

## What gets created

- Resource group
- Storage account
- Required blob containers: `landing-zone`, `processed`, `failed`
- Linux Function App (Python 3.12, Consumption plan)
- System-assigned managed identity for the Function App
- Storage RBAC assignments for the Function identity:
  - Storage Blob Data Contributor
  - Storage Blob Delegator
  - Storage Queue Data Contributor
- Entra app registration + service principal for GitHub OIDC
- Federated credential bound to repo/branch
- Contributor role assignment for the GitHub deploy principal on the resource group

## Quick start (local)

```bash
cd infra
terraform init
terraform fmt -recursive
terraform validate
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars
```

## CI/CD behavior

- `.github/workflows/terraform-infra.yml` runs `fmt`, `validate`, `plan`, and `apply` for `infra/` changes.
- After `apply`, the workflow exports `terraform output -json` and uploads an artifact named `terraform-outputs`.

## Required permissions

The identity running Terraform needs permissions to create:

- Azure resources in the target subscription/resource group
- Entra app registrations/service principals/federated credentials
- Azure role assignments

## GitHub secrets

The workflow currently uses the same Azure OIDC secrets as the existing app deployment workflow:

- `AZUREAPPSERVICE_CLIENTID_3C798445C3CF40C9A4AB7F7D4D241594`
- `AZUREAPPSERVICE_TENANTID_C2EB7D27D79F49419DF34E0753F96AE7`
- `AZUREAPPSERVICE_SUBSCRIPTIONID_C3DDD9D8A58B4D4EA90F55DDC66AD397`

After `terraform apply`, you can optionally switch to dedicated Terraform secrets using these outputs:

- `github_actions_client_id`
- `github_actions_tenant_id`
- `github_actions_subscription_id`

You can read outputs with:

```bash
terraform output
```

## Notes

- `dev.tfvars` is intentionally committed as a template for non-sensitive settings.
- Use a remote backend for team workflows and state locking.
- Current Terraform in this repository deploys a Linux Consumption plan (`Y1`) for Blob Trigger workloads.
- If you decide to move to Flex Consumption, plan it as a dedicated migration step because it uses a different Function App resource model.

## Post-deploy smoke test (blob trigger)

Use the helper script to verify trigger and routing behavior after deployment:

```bash
export STORAGE_ACCOUNT_NAME=<your-storage-account>
./scripts/deployment-smoke-test.sh
```

Expected outcomes:

- Exit `0`: blob was standardized and copied to `processed`
- Exit `2`: blob was routed to `failed`
- Exit `3`: no terminal outcome observed in timeout window
