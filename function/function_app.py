# pylint: disable=import-error,no-name-in-module,consider-using-from-import
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import azure.functions as func
import azurefunctions.extensions.bindings.blob as blob
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient, BlobServiceClient, generate_blob_sas

from filenamestandardizer import domain

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


PROCESSED_CONTAINER = "processed"
FAILED_CONTAINER = "failed"
SOURCE_CONTAINER = "upload"

# Validate required environment variable
account_url = os.environ["STORAGE_CONNECTION__blobServiceUri"]


credential = DefaultAzureCredential()
blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)


def generate_source_sas_url(container_name: str, blob_name: str) -> str:
    """Generate a user delegation SAS URL for the source blob."""
    # Get user delegation key (valid for managed identity)
    start_time = datetime.now(timezone.utc)
    expiry_time = start_time + timedelta(hours=1)

    user_delegation_key = blob_service_client.get_user_delegation_key(
        key_start_time=start_time, key_expiry_time=expiry_time
    )

    # Extract account name from URL
    account_name = account_url.split("//")[1].split(".")[0]

    # Generate SAS token with read permission
    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        user_delegation_key=user_delegation_key,
        permission="r",  # Read permission only
        expiry=expiry_time,
    )

    return f"{account_url}{container_name}/{blob_name}?{sas_token}"


def copy_blob(
    target_blob_client: BlobClient, source_container: str, source_blob_name: str
) -> None:
    """
    Copy blob server-side using user delegation SAS for source authentication.

    Uses exponential backoff for polling to handle large video files efficiently.
    """
    # Generate SAS URL for source blob
    source_url = generate_source_sas_url(source_container, source_blob_name)

    # Start server-side copy (asynchronous operation)
    target_blob_client.start_copy_from_url(source_url)

    # Poll with exponential backoff for large files
    max_retries = 60  # Up to ~5 minutes of polling
    retry_count = 0
    wait_time = 0.5  # Start with 500ms

    props = target_blob_client.get_blob_properties()

    while props.copy.status == "pending" and retry_count < max_retries:
        time.sleep(wait_time)
        props = target_blob_client.get_blob_properties()
        retry_count += 1
        # Exponential backoff, cap at 5 seconds
        wait_time = min(wait_time * 1.5, 5.0)

    if props.copy.status == "success":
        logging.info(
            "Successfully copied %s/%s to %s/%s",
            source_container,
            source_blob_name,
            target_blob_client.container_name,
            target_blob_client.blob_name,
        )
    elif props.copy.status == "pending":
        # For very large files, copy may still be in progress
        logging.info(
            "Copy initiated for %s/%s to %s/%s (still pending after %d checks). "
            "Azure will complete the copy asynchronously.",
            source_container,
            source_blob_name,
            target_blob_client.container_name,
            target_blob_client.blob_name,
            retry_count,
        )
    else:
        logging.error(
            "Copy failed for %s/%s: status=%s",
            source_container,
            source_blob_name,
            props.copy.status,
        )
        raise ValueError(f"Blob copy failed with status: {props.copy.status}")


@app.blob_trigger(
    arg_name="blob_client",
    path="upload/devices/{source_id}/{file_name}",
    connection="STORAGE_CONNECTION",
)
def standardize_uploaded_file(blob_client: blob.BlobClient) -> None:
    logging.info(
        "Processing blob: %s",
        blob_client.blob_name,
    )

    # blob_client.blob_name format: devices/{source_id}/{file_name} (3 parts)
    parts = blob_client.blob_name.split("/")
    if len(parts) != 3:
        logging.error(
            "Invalid blob path format: %s (expected 3 parts, got %d)",
            blob_client.blob_name,
            len(parts),
        )
        return

    # parts[0] is "devices"
    source_id = parts[1]  # source_id from path pattern
    file_name = parts[2]  # file_name from path pattern

    try:
        target_file_name = str(
            domain.standardize_file_name(file_name, source_id=source_id)
        )
        target_container = PROCESSED_CONTAINER
        logging.info(
            "Standardized: %s -> %s (source_id: %s)",
            file_name,
            target_file_name,
            source_id,
        )
    except ValueError as e:
        logging.warning("Failed to standardize file name %s: %s", file_name, e)
        target_file_name = f"{source_id}/{file_name}"
        target_container = FAILED_CONTAINER

    target_blob_client = blob_service_client.get_blob_client(
        container=target_container, blob=target_file_name
    )

    try:
        # Copy blob (server-side, efficient for large media files)
        copy_blob(target_blob_client, SOURCE_CONTAINER, blob_client.blob_name)

        # Delete source blob after successful copy initiation
        source_blob_client = blob_service_client.get_blob_client(
            container=SOURCE_CONTAINER, blob=blob_client.blob_name
        )
        source_blob_client.delete_blob()
        logging.info("Deleted source blob: %s", blob_client.blob_name)

    except Exception as e:
        logging.error(
            "Error processing blob %s: %s",
            blob_client.blob_name,
            e,
            exc_info=True,
        )
        raise

    logging.info("Blob processing completed for %s", blob_client.blob_name)
