import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

DEFAULT_FILE_INDEX = "0000"
FILE_PREFIX_PATTERN = "%Y/%m/"
TARGET_FILE_TIMESTAMP_PATTERN = "%Y%m%dT%H%M%S"


@dataclass
class FileNameSchema:
    file_name_pattern: str
    timestamp_pattern: str
    timestamp_format: str
    index_pattern: Optional[str] = None


ANDROID_SCHEMA = FileNameSchema(
    file_name_pattern=r"\d{8}_\d{6}.(jpg|mp4)",
    timestamp_pattern=r"\d{8}_\d{6}",
    timestamp_format="%Y%m%d_%H%M%S",
)
WHATSAPP_SCHEMA = FileNameSchema(
    file_name_pattern=r"^(IMG|VID)-\d{8}-WA[0-9]{4}.(jpg|mp4)",
    timestamp_pattern=r"\d{8}",
    timestamp_format="%Y%m%d",
    index_pattern="WA[0-9]{4}",
)


@dataclass(frozen=True)
class StandardizedFileName:
    """
    Immutable representation of a standardized file name.

    Format: YYYY/MM/YYYYMMDDThhmmss_SOURCE_SEQUENCE.ext
    Example: 2024/07/20240703T182842_A1B2C3D4_0042.jpg
    """

    timestamp: datetime
    source: str
    sequence: str
    extension: str

    @property
    def prefix(self) -> str:
        """Year/Month prefix: YYYY/MM/"""
        return self.timestamp.strftime("%Y/%m/")

    @property
    def base_name(self) -> str:
        """Base filename without directory: YYYYMMDDThhmmss_SOURCE_SEQUENCE.ext"""
        ts = self.timestamp.strftime("%Y%m%dT%H%M%S")
        return f"{ts}_{self.source}_{self.sequence}.{self.extension}"

    @property
    def full_path(self) -> str:
        """Complete path: YYYY/MM/YYYYMMDDThhmmss_SOURCE_SEQUENCE.ext"""
        return self.prefix + self.base_name

    def to_path(self, base_dir: Optional[Path] = None) -> Path:
        """Convert to Path object, optionally under a base directory"""
        p = Path(self.full_path)
        return base_dir / p if base_dir else p

    @classmethod
    def from_components(
        cls, timestamp: datetime, source: str, sequence: int | str, extension: str
    ) -> "StandardizedFileName":
        """Create from components with automatic index formatting"""
        if isinstance(sequence, int):
            sequence = f"{sequence:04d}"
        return cls(
            timestamp=timestamp, source=source, sequence=sequence, extension=extension
        )

    def __str__(self) -> str:
        return self.full_path

    def __repr__(self) -> str:
        return f"StandardizedFileName('{self.full_path}')"


def compute_source_id(identifier: str, length: int = 8) -> str:
    """
    Generate a compact source ID from an identifier (device serial, etc.).

    Args:
        identifier: Raw device/source identifier (serial number, etc.)
        length: Number of hex characters (default 8 = 4 bytes)

    Returns:
        Uppercase hex string of specified length

    Example:
        >>> compute_source_id("SM-G991B/ABC123DEF456")
        'A1B2C3D4'
    """
    hash_digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    return hash_digest[:length].upper()


def extract_datetime_string(file_name: str, datetime_pattern: str) -> str:
    match = re.search(datetime_pattern, file_name)
    if match is None:
        raise ValueError(
            f"Cannot extract datetime from {file_name} "
            f"with pattern {datetime_pattern}"
        )
    return match.group()


def get_datetime(datetime_string: str, datetime_format: str) -> datetime:
    return datetime.strptime(datetime_string, datetime_format)


def extract_index(file_name: str, index_pattern: str) -> str:
    match = re.search(index_pattern, file_name)
    if match:
        return match.group().replace("WA", "")
    raise ValueError(
        f"Cannot extract index from filename {file_name} "
        f"with pattern {index_pattern}"
    )


def is_file_name_according_to_pattern(file_name: str, file_name_pattern: str) -> bool:
    match = re.search(file_name_pattern, file_name)
    return bool(match)


def identify_file_pattern(file_name: str) -> FileNameSchema:
    if is_file_name_according_to_pattern(file_name, ANDROID_SCHEMA.file_name_pattern):
        return ANDROID_SCHEMA
    if is_file_name_according_to_pattern(file_name, WHATSAPP_SCHEMA.file_name_pattern):
        return WHATSAPP_SCHEMA
    raise ValueError(f"File name {file_name} is not mapping any known schema")


def standardize_file_name(
    file_name: str,
    file_name_schema: FileNameSchema | None = None,
    source_identifier: str = "",
) -> StandardizedFileName:
    """Parse source file and return standardized representation"""
    if file_name_schema is None:
        file_name_schema = identify_file_pattern(file_name)

    datetime_string = extract_datetime_string(
        file_name, file_name_schema.timestamp_pattern
    )
    dt = get_datetime(datetime_string, file_name_schema.timestamp_format)

    index = DEFAULT_FILE_INDEX
    if file_name_schema.index_pattern:
        index = extract_index(file_name, index_pattern=file_name_schema.index_pattern)

    extension = file_name.split(".")[-1]
    source_id = compute_source_id(source_identifier)

    return StandardizedFileName.from_components(
        timestamp=dt, source=source_id, sequence=index, extension=extension
    )


def read_files_from_directory(
    directory_path: str, extensions: list[str] | None = None
) -> list[str]:
    if extensions is None:
        extensions = [".*"]
    pattern = [f"*{ext}" for ext in extensions]
    files = []
    for search_pattern in pattern:
        files.extend(glob(str(Path(directory_path) / search_pattern)))
    return files


def standardize_files_in_directory(
    source_directory_path: str,
    extensions: list[str] | None = None,
    source_identifier: str = "",
) -> dict[str, str]:
    files = read_files_from_directory(source_directory_path, extensions)
    standardized_file_map = {}
    for file_path in files:
        file_name = Path(file_path).name
        try:
            standardized_file_name = standardize_file_name(
                file_name, source_identifier=source_identifier
            )
            standardized_file_map[file_path] = str(standardized_file_name)
        except ValueError:
            logging.warning(
                "File %s does not match any known schema. Skipping.", file_name
            )
    return standardized_file_map


android_mappings = {
    "whatsAppImages": (
        "Interner Speicher/Android/media/com.whatsapp/" "WhatsApp/Media/WhatsApp Images"
    ),
    "whatsAppVideos": (
        "Interner Speicher/Android/media/com.whatsapp/" "WhatsApp/Media/WhatsApp Video"
    ),
    "dcim": "Interner Speicher/DCIM",
    "camera": "Interner Speicher/DCIM/Camera",
}


def get_mtp_mount_path(gvfs_path: str = "/run/user/1000/gvfs/") -> Path:
    """Get the MTP mount path from gvfs directory."""
    mtp_devices = list(Path(gvfs_path).iterdir())
    if not mtp_devices:
        raise FileNotFoundError("No MTP devices found in /run/user/1000/gvfs/")
    return mtp_devices[0]


def extract_device_identifier_from_path(mtp_path: Path) -> str:
    """Extract device identifier from MTP path."""
    match = re.search(r"mtp:host=([^/]+)", str(mtp_path))
    if match:
        return match.group(1)
    raise ValueError(f"Cannot extract device identifier from path {mtp_path}")
