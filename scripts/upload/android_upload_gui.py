"""
Simple GUI for uploading photos from Android phone to Azure
Double-click this file to run!
"""  # pylint: disable=duplicate-code

import glob
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient, ContainerClient
from dotenv import load_dotenv

from filenamestandardizer import domain

load_dotenv()

GVFS_DIR = "/run/user/1000/gvfs/"
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
    source: Path, device_name_arg: str, container_client_arg: ContainerClient
) -> bool:
    device_id = domain.compute_source_id(device_name_arg)
    files = domain.read_files_from_directory(
        source.as_posix(), extensions=[".jpg", ".mp4"]
    )
    file_mapping = {
        file: os.path.join("devices", device_id, file.split("/")[-1]) for file in files
    }
    upload_to_blob_storage(container_client_arg, file_mapping)
    return True


class AndroidUploadGUI:  # pylint: disable=too-many-instance-attributes
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("📱 Android Photo Upload")
        self.root.geometry("700x700")
        self.root.resizable(True, True)

        # Variables
        self.device_path: str | None = None
        self.device_name: str | None = None
        self.internal_storage: str | None = None

        # Create UI
        self.create_widgets()

        # Auto-detect device on startup
        self.root.after(500, self.detect_device)

    def create_widgets(self) -> None:
        # Header
        header = tk.Label(
            self.root,
            text="📱 Android Photo Upload to Azure",
            font=("Arial", 16, "bold"),
            pady=15,
        )
        header.pack()

        # Device status frame
        device_frame = ttk.LabelFrame(self.root, text="Device Status", padding=10)
        device_frame.pack(fill="x", padx=20, pady=10)

        self.device_label = tk.Label(
            device_frame, text="🔍 Searching for device...", font=("Arial", 10)
        )
        self.device_label.pack()

        self.refresh_btn = ttk.Button(
            device_frame, text="🔄 Refresh", command=self.detect_device
        )
        self.refresh_btn.pack(pady=5)

        # Folder selection frame
        folder_frame = ttk.LabelFrame(self.root, text="Select Media Folder", padding=10)
        folder_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(folder_frame, text="Available folders:").pack(anchor="w")

        self.folder_var = tk.StringVar()
        self.folder_combo = ttk.Combobox(
            folder_frame, textvariable=self.folder_var, state="disabled", width=50
        )
        self.folder_combo.pack(pady=5, fill="x")

        # Custom path entry
        tk.Label(folder_frame, text="Or enter custom path:").pack(
            anchor="w", pady=(10, 0)
        )
        self.custom_path = tk.Entry(folder_frame, width=50)
        self.custom_path.pack(pady=5, fill="x")
        # self.custom_path.insert(0, "DCIM/Camera")

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

    def detect_device(self) -> None:
        """Detect connected Android device"""
        self.log("🔍 Searching for Android device...")
        self.device_label.config(text="🔍 Searching for device...")

        if not os.path.exists(GVFS_DIR):
            self.device_label.config(text="❌ GVFS directory not found")
            self.log("❌ GVFS not available")
            return

        mtp_paths = glob.glob(f"{GVFS_DIR}mtp:*")

        if not mtp_paths:
            self.device_label.config(text="❌ No device connected")
            self.log("❌ No Android device found. Please connect your phone.")
            messagebox.showwarning(
                "No Device",
                "No Android device found!\n\n"
                "Please:\n"
                "1. Connect your phone via USB\n"
                "2. Unlock your phone\n"
                "3. Enable File Transfer (MTP) mode\n"
                "4. Access the phone in your file manager once",
            )
            return

        self.device_path = mtp_paths[0]
        device_dir = os.path.basename(self.device_path)
        self.device_name = device_dir.removeprefix("mtp:host=")

        # Find internal storage
        possible_paths = [
            os.path.join(self.device_path, "Interner Speicher"),
            os.path.join(self.device_path, "Internal storage"),
            os.path.join(self.device_path, "Internal Storage"),
        ]

        self.internal_storage = None
        for path in possible_paths:
            if os.path.isdir(path):
                self.internal_storage = path
                break

        if not self.internal_storage:
            self.device_label.config(text="❌ Cannot access storage")
            self.log("❌ Cannot access internal storage. Please unlock your phone.")
            return

        self.device_label.config(text=f"✅ Connected: {self.device_name}")
        self.log(f"✅ Device found: {self.device_name}")

        # Load available folders
        self.load_folders()

        # Enable upload button
        self.upload_btn.config(state="normal")

    def load_folders(self) -> None:
        """Load available media folders from device"""
        if self.internal_storage is None:
            self.log("⚠ Internal storage not available")
            return
        dcim_path = os.path.join(self.internal_storage, "DCIM")

        if not os.path.isdir(dcim_path):
            self.log("⚠ No DCIM folder found")
            return

        folders = [
            "Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Images",
            "Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Videos",
        ]

        try:
            for item in os.listdir(dcim_path):
                full_path = os.path.join(dcim_path, item)
                if os.path.isdir(full_path):
                    folders.append(f"DCIM/{item}")

            if folders:
                self.folder_combo.config(state="readonly", values=folders)
                self.folder_combo.current(0)
                self.log(f"📁 Found {len(folders)} media folder(s)")
            else:
                self.log("⚠ No folders found in DCIM")

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log(f"⚠ Error scanning folders: {e}")

    def start_upload(self) -> None:
        """Start the upload process in a separate thread"""
        # Get selected or custom path
        mediadir = self.custom_path.get().strip()
        if not mediadir:
            mediadir = self.folder_var.get()

        if not mediadir:
            messagebox.showerror("Error", "Please select or enter a media folder!")
            return

        # Confirm
        result = messagebox.askyesno(
            "Confirm Upload", f"Upload photos from:\n{mediadir}\n\nContinue?"
        )

        if not result:
            return

        # Disable buttons during upload
        self.upload_btn.config(state="disabled")
        self.refresh_btn.config(state="disabled")

        self.log(f"\n📤 Starting upload from: {mediadir}")

        # Run upload in separate thread to keep GUI responsive
        if self.internal_storage is None:
            messagebox.showerror("Error", "Internal storage not available!")
            self.upload_btn.config(state="normal")
            self.refresh_btn.config(state="normal")
            return
        internal_storage_path = Path(self.internal_storage)
        source_directory = internal_storage_path / mediadir
        if not source_directory.is_dir():
            messagebox.showerror(
                "Error", f"The directory {source_directory} does not exist."
            )
            self.upload_btn.config(state="normal")
            self.refresh_btn.config(state="normal")
            return
        self.run_upload(source_directory)

    def run_upload(self, source_directory: Path) -> None:
        try:
            if self.device_name is None:
                messagebox.showerror("Error", "Device name not available!")
                return
            upload_media_files(source_directory, self.device_name, container_client)
            self.log("\n✅ ✨ Upload completed successfully! ✨")
            messagebox.showinfo("Success", "Upload completed successfully!")
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log(f"\n❌ Upload failed: {e}")
            messagebox.showerror("Error", f"Upload failed:\n{e}")
        finally:
            self.upload_btn.config(state="normal")
            self.refresh_btn.config(state="normal")


def main() -> None:
    root = tk.Tk()
    AndroidUploadGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
