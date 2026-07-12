# FileNameStandardizer

An Azure Function that automatically standardizes file names uploaded to Azure Blob Storage. When a blob is uploaded to the landing zone container, the function normalizes its name into a consistent format and copies it to a target container.

## How it works

1. A file is uploaded to `landing-zone/devices/{device_id}/{file_name}`
2. The blob trigger fires and identifies the file name pattern (Android or WhatsApp)
3. The file name is standardized into `YYYY/MM/YYYYMMDDThhmmss_DEVICEID_SEQUENCE.ext`
4. The blob is copied to the `processed` container (or `failed` if the name can't be parsed)

### Supported file name patterns

| Source   | Input example               | Output example                          |
|----------|-----------------------------|-----------------------------------------|
| Android  | `20240707_121110.jpg`       | `2024/07/20240707T121110_DeviceA_0000.jpg` |
| WhatsApp | `IMG-20240721-WA0007.jpg`   | `2024/07/20240721T000000_DeviceA_0007.jpg` |

## Prerequisites

- Python 3.12+
- [Azure Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
- An Azure Storage account

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Infrastructure as Code (Terraform)

Infrastructure provisioning is now Terraform-first.

### What Terraform manages

- Resource group
- Storage account
- Containers: `landing-zone`, `processed`, `failed`
- Linux Function App (Python 3.12)
- Function App system-assigned managed identity
- Storage RBAC assignments for Function identity
- GitHub OIDC app registration, service principal, and federated credential

### First run

```bash
cd infra
terraform init
terraform fmt -recursive
terraform validate
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars
```

See `infra/README.md` for details.

### GitHub Actions secrets for Terraform workflow

The Terraform workflow currently uses the same Azure OIDC secrets already used by the app deploy workflow:

- `AZUREAPPSERVICE_CLIENTID_3C798445C3CF40C9A4AB7F7D4D241594`
- `AZUREAPPSERVICE_TENANTID_C2EB7D27D79F49419DF34E0753F96AE7`
- `AZUREAPPSERVICE_SUBSCRIPTIONID_C3DDD9D8A58B4D4EA90F55DDC66AD397`

You can later migrate to dedicated Terraform-specific secrets after the first rollout.

## Configuration

### `local.settings.json`

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "STORAGE_CONNECTION__blobServiceUri": "https://<account>.blob.core.windows.net/",
    "STORAGE_CONNECTION__queueServiceUri": "https://<account>.queue.core.windows.net/"
  }
}
```

Replace `<account>` with your storage account name.

## Required Azure RBAC roles

The identity running the function (your user locally, or the Function App's managed identity in production) needs the following roles on the storage account:

| Role                              | Purpose                                          |
|-----------------------------------|--------------------------------------------------|
| **Storage Blob Data Contributor** | Read, write, and delete blobs                    |
| **Storage Blob Delegator**        | Generate user delegation SAS tokens for blob copy |
| **Storage Queue Data Contributor** | Blob trigger internal queue management           |

### Assign roles

```bash
ACCOUNT_ID=$(az storage account show -n <account> --query id -o tsv)

# For local development (your user)
USER_ID=$(az ad signed-in-user show --query id -o tsv)
az role assignment create --assignee "$USER_ID" --role "Storage Blob Data Contributor" --scope "$ACCOUNT_ID"
az role assignment create --assignee "$USER_ID" --role "Storage Blob Delegator" --scope "$ACCOUNT_ID"
az role assignment create --assignee "$USER_ID" --role "Storage Queue Data Contributor" --scope "$ACCOUNT_ID"

# For production (Function App managed identity)
PRINCIPAL_ID=$(az functionapp identity show -n <function-app> -g <resource-group> --query principalId -o tsv)
az role assignment create --assignee "$PRINCIPAL_ID" --role "Storage Blob Data Contributor" --scope "$ACCOUNT_ID"
az role assignment create --assignee "$PRINCIPAL_ID" --role "Storage Blob Delegator" --scope "$ACCOUNT_ID"
az role assignment create --assignee "$PRINCIPAL_ID" --role "Storage Queue Data Contributor" --scope "$ACCOUNT_ID"
```

## Running locally

```bash
az login
func host start
```

## Running tests

```bash
pytest tests/
```

## Deployment verification

After infrastructure and app deployment, run a blob-trigger smoke test:

```bash
export STORAGE_ACCOUNT_NAME=<your-storage-account>
./scripts/deployment-smoke-test.sh
```

The script uploads a sample blob to `landing-zone/devices/{device_id}/...` and checks whether the file appears in `processed` or `failed`.

## App deployment target

The deployment workflow is `.github/workflows/cd-deploy-functionapp-dev.yml` (`CD - Deploy Function App (dev)`).
It is wired to run automatically after `.github/workflows/cd-terraform-infra-dev.yml` (`CD - Terraform Infra (dev)`) succeeds for the `main` branch delivery flow.

Expected merge-to-main order is:

1. `CI - Test` runs tests.
2. `CD - Terraform Infra (dev)` runs plan/apply using shared environment variables.
3. `CD - Deploy Function App (dev)` uses the same shared environment variables to deploy code.

To enforce CI as a hard gate before merge, enable branch protection on `main` and require the `CI - Test` check.

You can also trigger it manually and set:

- `runSmokeTest`

## Shared GitHub Variables (environment: dev)

Set these variables in GitHub Environment `dev`:

- `RESOURCE_GROUP_NAME`
- `FUNCTION_APP_NAME`

Both `.github/workflows/cd-terraform-infra-dev.yml` and `.github/workflows/cd-deploy-functionapp-dev.yml` run with `environment: dev` and read these values so infra and app deployment target the same resources.

## Storage containers

| Container      | Purpose                                          |
|----------------|--------------------------------------------------|
| `landing-zone` | Source — upload files here to trigger processing  |
| `processed`    | Target for successfully standardized files       |
| `failed`       | Target for files that couldn't be standardized   |

## Legacy scripts

The shell scripts under `scripts/` are now considered legacy bootstrap helpers. Prefer Terraform in `infra/` for ongoing infrastructure changes.
