import os

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

from filenamestandardizer import domain

load_dotenv()


connection_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
container_name = os.environ["STORAGE_CONTAINER"]
home_dir = os.environ["HOME"]


if __name__ == "__main__":
    # source_directory = "tests/data"
    # source_directory = f"{home_dir}/Bilder/tmp"
    mount_path = domain.get_mtp_mount_path()
    source_identifier = domain.extract_device_identifier_from_path(mount_path)
    print(f"MTP mount path: {mount_path}")
    print(f"Source identifier: {source_identifier}")

    source_directory = mount_path.joinpath(
        domain.android_mappings["dcim"], "Portugal 2021"
    )
    print(f"Source directory: {source_directory}")
    if not source_directory.is_dir():
        raise NotADirectoryError(f"Source directory does not exist: {source_directory}")
    file_mapping = domain.standardize_files_in_directory(
        source_directory.as_posix(),
        extensions=[".jpg", ".mp4"],
        source_identifier=source_identifier,
    )
    print(file_mapping)
    # authenticate to azure blob storage
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    # create target container if not exists
    try:
        blob_service_client.create_container(container_name)
        print(f"Container {container_name} created.")
    except ResourceExistsError:
        print(f"Container {container_name} already exists.")

    # get all blobs from container
    container_client = blob_service_client.get_container_client(container_name)
    existing_blobs = {blob.name for blob in container_client.list_blobs()}
    print(f"Existing blobs in container: {existing_blobs}")
    # filter blobs which does not exist in target (not necessary due to overwrite=False
    # setting during copy)
    # upload blobs to target container with standardized filenames
    for source_path, target_file_name in file_mapping.items():
        if target_file_name in existing_blobs:
            print(f"Blob {target_file_name} already exists. Skipping upload.")
            continue
        with open(source_path, "rb") as data:
            blob_client = container_client.get_blob_client(target_file_name)
            blob_client.upload_blob(data, overwrite=False)
            print(f"Uploaded {source_path} as {target_file_name}.")
