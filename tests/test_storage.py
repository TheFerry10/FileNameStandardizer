from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient

from filenamestandardizer import storage


def test_create_container_if_not_exists(blob_service_client: BlobServiceClient) -> None:
    try:
        blob_service_client.create_container("testcontainer")
    except ResourceExistsError:
        pass
    storage.ensure_container(blob_service_client, "testcontainer")
    assert True
