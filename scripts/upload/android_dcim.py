import argparse
import glob
import os
from pathlib import Path
from pprint import pprint

from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient, ContainerClient
from dotenv import load_dotenv

from filenamestandardizer import domain

load_dotenv()


# "/run/user/1000/gvfs/mtp:host=SAMSUNG_SAMSUNG_Android_RFCW112HFCK/Interner Speicher"
# "SAMSUNG_SAMSUNG_Android_RFCW112HFCK"
parser = argparse.ArgumentParser(
    description="Upload files from Android DCIM to Azure Blob Storage"
)

parser.add_argument(
    "--mediadir",
    type=str,
    required=True,
    help="Relative source directory path on the device, e.g. 'DCIM/Camera'",
)
args = parser.parse_args()

connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

container_name = os.getenv("LANDING_ZONE_STORAGE_CONTAINER")
account_url = os.getenv("AZURE_STORAGEBLOB_RESOURCEENDPOINT")
tenant_id = os.getenv("AZURE_TENANT_ID")
client_id = os.getenv("AZURE_CLIENT_ID")
client_secret = os.getenv("AZURE_CLIENT_SECRET")
credential = ClientSecretCredential(tenant_id, client_id, client_secret)

blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
container_client = blob_service_client.get_container_client(container_name)
GVFS_DIR = "/run/user/1000/gvfs/"


def upload_to_blob_storage(
    container_client_arg: ContainerClient, file_mapping: dict[str, str]
) -> None:
    existing_blobs = {blob.name for blob in container_client_arg.list_blobs()}
    for source_path, target_file_name in file_mapping.items():
        if target_file_name in existing_blobs:
            print(f"Blob {target_file_name} already exists. Skipping upload.")
            continue
        with open(source_path, "rb") as data:
            blob_client = container_client_arg.get_blob_client(target_file_name)
            blob_client.upload_blob(data, overwrite=False)
            print(f"Uploaded {source_path} as {target_file_name}.")


def upload_media_files(
    source: Path, device_name_arg: str, container_client_arg: ContainerClient
) -> None:
    device_id = domain.compute_source_id(device_name_arg)

    print(f"Source directory: {source}")
    if not source.is_dir():
        raise NotADirectoryError(f"Source directory does not exist: {source}")
    files = domain.read_files_from_directory(
        source.as_posix(), extensions=[".jpg", ".mp4"]
    )
    file_mapping = {
        file: os.path.join("devices", device_id, file.split("/")[-1]) for file in files
    }
    pprint(file_mapping)

    upload_to_blob_storage(container_client_arg, file_mapping)


if __name__ == "__main__":

    mtp_paths = glob.glob("/run/user/1000/gvfs/mtp:*")

    if len(mtp_paths) == 0:
        raise ValueError(
            "No MTP devices found. Please connect your Android device via MTP."
        )

    if len(mtp_paths) > 1:
        raise ValueError("Multiple MTP devices found. Please connect only one device.")

    device_path = Path(mtp_paths[0])

    if not device_path.is_dir():
        raise NotADirectoryError(f"MTP device path is not a directory: {device_path}")
    device_dir = device_path.name
    print(f"Android phone connected at {device_path}")

    device_name = device_dir.removeprefix("mtp:host=")
    print(f"Device Name: {device_name}")

    internal_storage_path = Path(device_path) / "Interner Speicher"

    if not internal_storage_path.is_dir():
        raise ValueError(
            (
                "Internal Storage path not found! Please check if the device is "
                "unlocked and MTP is enabled."
            )
        )
    source_directory: Path = internal_storage_path / args.mediadir
    if not source_directory.is_dir():
        raise NotADirectoryError(f"Source directory does not exist: {source_directory}")
    upload_media_files(source_directory, device_name, container_client)
