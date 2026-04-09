# pylint: disable=import-error,no-name-in-module,consider-using-from-import
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import azure.functions as func
import azurefunctions.extensions.bindings.blob as blob
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient, BlobServiceClient, generate_blob_sas

from standardizer import standardize_file_name

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

PROCESSED_CONTAINER = "processed"
FAILED_CONTAINER = "failed"
SOURCE_CONTAINER = "upload"

COPY_MAX_RETRIES = 60
COPY_INITIAL_WAIT_SECONDS = 0.5
COPY_MAX_WAIT_SECONDS = 5.0


@dataclass(frozen=True)
class StorageContext:
    """Holds runtime storage configuration for copy operations."""

    client: BlobServiceClient
    service_account_url: str


def _create_storage_context() -> StorageContext:
    """Create storage context for Azure Storage using managed identity."""
    configured_account_url = os.getenv("STORAGE_CONNECTION__blobServiceUri")
    if not configured_account_url:
        configured_account_url = os.getenv("AZURE_STORAGEBLOB_RESOURCEENDPOINT")

    if not configured_account_url:
        raise RuntimeError(
            "Missing storage configuration. "
            "Set STORAGE_CONNECTION__blobServiceUri "
            "(or AZURE_STORAGEBLOB_RESOURCEENDPOINT) "
            "for managed identity mode."
        )

    normalized_url = configured_account_url.rstrip("/") + "/"
    credential = DefaultAzureCredential()
    client = BlobServiceClient(
        account_url=normalized_url,
        credential=credential,
    )

    return StorageContext(
        client=client,
        service_account_url=normalized_url,
    )


storage_context = _create_storage_context()


def _extract_blob_path_parts(blob_name: str) -> tuple[str, str]:
    """Extract source id and file name from devices/{source_id}/{file_name}."""
    parts = blob_name.split("/")
    if len(parts) != 3:
        raise ValueError(
            f"Invalid blob path format: {blob_name} "
            f"(expected 3 parts, got {len(parts)})"
        )
    return parts[1], parts[2]


def _resolve_target_location(
    file_name: str,
    source_id: str,
) -> tuple[str, str]:
    """Return target container and path for a source file."""
    try:
        target_file_name = str(standardize_file_name(file_name, source_id=source_id))
        logging.info(
            "Standardized: %s -> %s (source_id: %s)",
            file_name,
            target_file_name,
            source_id,
        )
        return PROCESSED_CONTAINER, target_file_name
    except ValueError as exc:
        logging.warning(
            "Failed to standardize file name %s: %s",
            file_name,
            exc,
        )
        return FAILED_CONTAINER, f"{source_id}/{file_name}"


def generate_source_sas_url(container_name: str, blob_name: str) -> str:
    """Generate a user delegation SAS URL for the source blob."""
    start_time = datetime.now(timezone.utc)
    expiry_time = start_time + timedelta(hours=1)
    user_delegation_key = storage_context.client.get_user_delegation_key(
        key_start_time=start_time,
        key_expiry_time=expiry_time,
    )

    sas_token = generate_blob_sas(
        account_name=storage_context.client.account_name,
        container_name=container_name,
        blob_name=blob_name,
        user_delegation_key=user_delegation_key,
        permission="r",
        expiry=expiry_time,
    )

    return (
        f"{storage_context.service_account_url}"
        f"{container_name}/{blob_name}?{sas_token}"
    )


def copy_blob(
    target_blob_client: BlobClient,
    source_container: str,
    source_blob_name: str,
) -> None:
    """Copy blob via start_copy_from_url and poll for completion."""
    source_url = generate_source_sas_url(source_container, source_blob_name)
    target_blob_client.start_copy_from_url(source_url)

    retries = 0
    wait_seconds = COPY_INITIAL_WAIT_SECONDS
    props = target_blob_client.get_blob_properties()

    while props.copy.status == "pending" and retries < COPY_MAX_RETRIES:
        time.sleep(wait_seconds)
        props = target_blob_client.get_blob_properties()
        retries += 1
        wait_seconds = min(wait_seconds * 1.5, COPY_MAX_WAIT_SECONDS)

    if props.copy.status == "success":
        logging.info(
            "Successfully copied %s/%s to %s/%s",
            source_container,
            source_blob_name,
            target_blob_client.container_name,
            target_blob_client.blob_name,
        )
        return

    if props.copy.status == "pending":
        logging.info(
            "Copy initiated for %s/%s to %s/%s "
            "(still pending after %d checks). "
            "Azure will complete the copy asynchronously.",
            source_container,
            source_blob_name,
            target_blob_client.container_name,
            target_blob_client.blob_name,
            retries,
        )
        return

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
    """Trigger handler for uploaded files requiring name normalization."""
    logging.info("Processing blob: %s", blob_client.blob_name)

    try:
        source_id, file_name = _extract_blob_path_parts(blob_client.blob_name)
    except ValueError as exc:
        logging.error("%s", exc)
        return

    target_container, target_file_name = _resolve_target_location(
        file_name,
        source_id,
    )

    target_blob_client = storage_context.client.get_blob_client(
        container=target_container,
        blob=target_file_name,
    )

    try:
        copy_blob(
            target_blob_client,
            SOURCE_CONTAINER,
            blob_client.blob_name,
        )
    except Exception as exc:
        logging.error(
            "Error processing blob %s: %s",
            blob_client.blob_name,
            exc,
            exc_info=True,
        )
        raise

    logging.info("Blob processing completed for %s", blob_client.blob_name)
