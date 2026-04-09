"""
Simple GUI for uploading files from local folder to Azure
Double-click this file to run!
"""  # pylint: disable=duplicate-code

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient, ContainerClient
from dotenv import load_dotenv

from filenamestandardizer import domain

load_dotenv()

account_url = os.getenv("AZURE_STORAGEBLOB_RESOURCEENDPOINT")
container_name = os.getenv("LANDING_ZONE_STORAGE_CONTAINER")
tenant_id = os.getenv("AZURE_TENANT_ID")
client_id = os.getenv("AZURE_CLIENT_ID")
client_secret = os.getenv("AZURE_CLIENT_SECRET")
credential = ClientSecretCredential(tenant_id, client_id, client_secret)

blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
container_client = blob_service_client.get_container_client(container_name)


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
    source: Path, device_name: str, container_client_arg: ContainerClient
) -> None:
    device_id = domain.compute_source_id(device_name)
    files = domain.read_files_from_directory(
        source.as_posix(), extensions=[".jpg", ".mp4"]
    )
    file_mapping = {
        file: os.path.join("devices", device_id, file.split("/")[-1]) for file in files
    }
    upload_to_blob_storage(container_client_arg, file_mapping)


class LocalUploadGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("� Local Folder Upload")
        self.root.geometry("700x600")
        self.root.resizable(True, True)

        # Variables
        self.selected_folder: Path | None = None
        self.device_name = tk.StringVar(value="local-machine")

        # Create UI
        self.create_widgets()

    def create_widgets(self) -> None:
        # Header
        header = tk.Label(
            self.root,
            text="� Local Folder Upload to Azure",
            font=("Arial", 16, "bold"),
            pady=15,
        )
        header.pack()

        # Device name frame
        name_frame = ttk.LabelFrame(self.root, text="Device Name", padding=10)
        name_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(
            name_frame,
            text="Enter a name for this device/source:",
            font=("Arial", 10),
        ).pack(anchor="w")

        name_entry = ttk.Entry(name_frame, textvariable=self.device_name, width=40)
        name_entry.pack(pady=5, fill="x")

        # Folder selection frame
        folder_frame = ttk.LabelFrame(self.root, text="Select Folder", padding=10)
        folder_frame.pack(fill="x", padx=20, pady=10)

        self.folder_label = tk.Label(
            folder_frame,
            text="No folder selected",
            font=("Arial", 10),
            fg="gray",
        )
        self.folder_label.pack(pady=5)

        browse_btn = ttk.Button(
            folder_frame, text="📁 Browse Folder...", command=self.browse_folder
        )
        browse_btn.pack(pady=5)

        # Upload button
        self.upload_btn = ttk.Button(
            self.root,
            text="📤 Start Upload",
            command=self.start_upload,
            state="disabled",
        )
        self.upload_btn.pack(pady=20)

        # Progress/Log area
        log_frame = ttk.LabelFrame(self.root, text="Status", padding=10)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=20, width=80, state="disabled", font=("Courier", 10)
        )
        self.log_text.pack(fill="both", expand=True)

    def log(self, message: str) -> None:
        """Add message to log area"""
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update()

    def browse_folder(self) -> None:
        """Open folder browser dialog"""
        folder = filedialog.askdirectory(
            title="Select Folder to Upload",
            initialdir=os.path.expanduser("~"),
        )

        if folder:
            self.selected_folder = Path(folder)
            self.folder_label.config(
                text=f"Selected: {self.selected_folder}", fg="green"
            )
            self.upload_btn.config(state="normal")
            self.log(f"📁 Folder selected: {self.selected_folder}")

            # Count files
            try:
                files = domain.read_files_from_directory(
                    self.selected_folder.as_posix(), extensions=[".jpg", ".mp4"]
                )
                self.log(f"📊 Found {len(files)} file(s) to upload")
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.log(f"⚠️  Error scanning folder: {e}")

    def start_upload(self) -> None:
        """Start the upload process"""
        if not self.selected_folder:
            messagebox.showerror("Error", "Please select a folder first!")
            return

        device_name = self.device_name.get().strip()
        if not device_name:
            messagebox.showerror("Error", "Please enter a device name!")
            return

        # Confirm
        result = messagebox.askyesno(
            "Confirm Upload",
            f"Upload files from:\n{self.selected_folder}\n\nDevice name: {
                device_name}\n\nContinue?",
        )

        if not result:
            return

        # Disable button during upload
        self.upload_btn.config(state="disabled")

        self.log(f"\n📤 Starting upload from: {self.selected_folder}")
        self.log(f"🏷️  Device name: {device_name}")

        self.run_upload()

    def run_upload(self) -> None:
        try:
            device_name = self.device_name.get().strip()
            if self.selected_folder is None:
                messagebox.showerror("Error", "No folder selected!")
                return
            upload_media_files(self.selected_folder, device_name, container_client)
            self.log("\n✅ ✨ Upload completed successfully! ✨")
            messagebox.showinfo("Success", "Upload completed successfully!")
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log(f"\n❌ Upload failed: {e}")
            messagebox.showerror("Error", f"Upload failed:\n{e}")
        finally:
            self.upload_btn.config(state="normal")


def main() -> None:
    root = tk.Tk()
    LocalUploadGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
