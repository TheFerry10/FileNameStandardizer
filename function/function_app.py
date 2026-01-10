# pylint: disable=import-error,no-name-in-module,consider-using-from-import
import logging
import os
import time

import azure.functions as func
import azurefunctions.extensions.bindings.blob as blob
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import BlobClient, BlobServiceClient

from filenamestandardizer import domain

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


PROCESSED_CONTAINER = "processed"
FAILED_CONTAINER = "failed"

account_url = os.getenv("STORAGE_CONNECTION__blobServiceUri")
credential = ManagedIdentityCredential()
blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)


def copy_blob(target_blob_client: BlobClient, source_blob_url: str) -> None:
    max_retries = 30
    retry_count = 0
    target_blob_client.start_copy_from_url(source_blob_url)

    props = target_blob_client.get_blob_properties()

    while props.copy.status == "pending" and retry_count < max_retries:
        time.sleep(0.1)
        props = target_blob_client.get_blob_properties()
        retry_count += 1

    if props.copy.status == "success":
        logging.info(
            "Successfully copied %s to %s",
            source_blob_url,
            target_blob_client.blob_name,
        )
    else:
        logging.error(
            "Copy failed for %s: status=%s", source_blob_url, props.copy.status
        )
        raise ValueError(f"Blob copy failed with status: {props.copy.status}")


@app.blob_trigger(
    arg_name="blob_client",
    path="upload/devices/{source_id}/{file_name}",
    connection="STORAGE_CONNECTION",
)
def standardize_uploaded_file(blob_client: blob.BlobClient) -> None:
    logging.info(
        "Python blob trigger function processed blob\nBlob name: %s\n",
        blob_client.blob_name,
    )

    source_id = blob_client.blob_name.split("/")[1]
    file_name = blob_client.blob_name.split("/")[2]
    try:
        target_file_name = str(
            domain.standardize_file_name(file_name, source_id=source_id)
        )
        target_container = PROCESSED_CONTAINER
        logging.info("Standardized file name: %s", target_file_name)
    except ValueError:
        target_file_name = f"{source_id}/{file_name}"
        target_container = FAILED_CONTAINER

    target_blob_client = blob_service_client.get_blob_client(
        container=target_container, blob=target_file_name
    )
    copy_blob(target_blob_client, blob_client.url)
    logging.info("Blob processing completed for %s", blob_client.blob_name)
