import os

import pytest
from azure.storage.blob import BlobServiceClient

os.environ["AZURE_STORAGE_CONNECTION_STRING"] = (
    "DefaultEndpointsProtocol=http;"
    "AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
    "K1SZFPTOtr/KBHBeksoGMGw==;"
    "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
)
os.environ["STORAGE_CONTAINER"] = "test-container"


@pytest.fixture(scope="session", autouse=True)
def blob_service_client() -> BlobServiceClient:
    return BlobServiceClient.from_connection_string(
        os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    )
