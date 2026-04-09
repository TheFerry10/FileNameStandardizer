import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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
    index_pattern: str | None = None


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

    def to_path(self, base_dir: Path | None = None) -> Path:
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
    source_id: str = "UNKNOWN",
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

    return StandardizedFileName.from_components(
        timestamp=dt, source=source_id, sequence=index, extension=extension
    )
