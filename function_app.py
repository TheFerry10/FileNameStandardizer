# pylint: disable=import-error,no-name-in-module,consider-using-from-import
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import azure.functions as func
import azurefunctions.extensions.bindings.blob as blob
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient, BlobServiceClient, generate_blob_sas

from standardizer import standardize_file_name

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

SOURCE_CONTAINER = "landing-zone"
PROCESSED_CONTAINER = "processed"
FAILED_CONTAINER = "failed"
TARGET_CONTAINER_MAPPING = {"success": PROCESSED_CONTAINER, "failed": FAILED_CONTAINER}

COPY_MAX_RETRIES = 60
COPY_INITIAL_WAIT_SECONDS = 0.5
COPY_MAX_WAIT_SECONDS = 5.0


def _create_blob_service_client() -> BlobServiceClient:
    """Create a BlobServiceClient for Azure Storage using managed identity."""
    account_url = os.getenv("STORAGE_CONNECTION__blobServiceUri") or os.getenv(
        "AZURE_STORAGEBLOB_RESOURCEENDPOINT"
    )
    if not account_url:
        raise RuntimeError(
            "Missing storage configuration. "
            "Set STORAGE_CONNECTION__blobServiceUri "
            "(or AZURE_STORAGEBLOB_RESOURCEENDPOINT) "
            "for managed identity mode."
        )

    return BlobServiceClient(
        account_url=account_url.rstrip("/") + "/",
        credential=DefaultAzureCredential(),
    )


blob_service_client = _create_blob_service_client()


def _extract_blob_path_parts(blob_name: str) -> dict[str, str]:
    """Extract device id and file name from devices/{device_id}/{file_name}."""
    parts = blob_name.split("/")
    if len(parts) != 3:
        raise ValueError(
            f"Invalid blob path format: {blob_name} "
            f"(expected 3 parts, got {len(parts)})"
        )
    return {"device_id": parts[1], "file_name": parts[2]}


def _resolve_target_location(
    file_name: str,
    device_id: str,
    target_container_mapping: dict[str, str] = None,
) -> dict:
    """Resolve the target location for a given file name and device ID."""
    if target_container_mapping is None:
        target_container_mapping = TARGET_CONTAINER_MAPPING
    try:
        target_file_name = str(standardize_file_name(file_name, device_id=device_id))
        logging.info(
            "Standardized: %s -> %s (device_id: %s)",
            file_name,
            target_file_name,
            device_id,
        )
        return {
            "target_file_name": target_file_name,
            "target_container": target_container_mapping["success"],
        }
    except ValueError as exc:
        logging.warning(
            "Failed to standardize file name %s: %s",
            file_name,
            exc,
        )
        return {
            "target_file_name": f"{device_id}/{file_name}",
            "target_container": target_container_mapping["failed"],
        }


def generate_source_sas_url(container_name: str, blob_name: str) -> str:
    """Generate a user delegation SAS URL for the source blob."""
    start_time = datetime.now(timezone.utc)
    expiry_time = start_time + timedelta(hours=1)
    user_delegation_key = blob_service_client.get_user_delegation_key(
        key_start_time=start_time,
        key_expiry_time=expiry_time,
    )

    sas_token = generate_blob_sas(
        account_name=blob_service_client.account_name,
        container_name=container_name,
        blob_name=blob_name,
        user_delegation_key=user_delegation_key,
        permission="r",
        expiry=expiry_time,
    )

    return f"{blob_service_client.url}" f"{container_name}/{blob_name}?{sas_token}"


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
    path="landing-zone/devices/{device_id}/{file_name}",
    connection="STORAGE_CONNECTION",
)
def standardize_uploaded_file(blob_client: blob.BlobClient) -> None:
    """Trigger handler for uploaded files requiring name normalization."""
    logging.info("Processing blob: %s", blob_client.blob_name)

    try:
        blob_parts = _extract_blob_path_parts(blob_client.blob_name)
    except ValueError as exc:
        logging.error("%s", exc)
        return

    target_location = _resolve_target_location(
        blob_parts["file_name"],
        blob_parts["device_id"],
        TARGET_CONTAINER_MAPPING,
    )

    target_blob_client = blob_service_client.get_blob_client(
        container=target_location["target_container"],
        blob=target_location["target_file_name"],
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
