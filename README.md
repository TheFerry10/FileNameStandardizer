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

## Storage containers

| Container      | Purpose                                          |
|----------------|--------------------------------------------------|
| `landing-zone` | Source — upload files here to trigger processing  |
| `processed`    | Target for successfully standardized files       |
| `failed`       | Target for files that couldn't be standardized   |
