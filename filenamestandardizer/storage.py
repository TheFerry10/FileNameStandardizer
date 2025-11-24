from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient


def ensure_container(client: BlobServiceClient, container: str) -> None:
    """
    Ensure the container exists (create if not).
    """
    try:
        client.create_container(container)
    except ResourceExistsError:
        print(f"Container {container} already exists.")
