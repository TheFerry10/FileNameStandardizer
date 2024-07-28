from dataclasses import dataclass
import datetime
from pathlib import Path
import re
from typing import Optional

DEFAULT_FILE_INDEX = "0000"


@dataclass
class FileNameSchema:
    file_name_pattern: str
    timestamp_pattern: str
    timestamp_format: str
    index_pattern: Optional[str] = None


AndroidSchema = FileNameSchema(
    file_name_pattern=r"\d{8}_\d{6}.(jpg|mp4)",
    timestamp_pattern=r"\d{8}_\d{6}",
    timestamp_format="%Y%m%d_%H%M%S",
)
WhatsAppSchema = FileNameSchema(
    file_name_pattern=r"^(IMG|VID)-\d{8}-WA[0-9]{4}.(jpg|mp4)",
    timestamp_pattern=r"\d{8}",
    timestamp_format="%Y%m%d",
    index_pattern="WA[0-9]{4}",
)


def extract_datetime_string(file_name: str, datetime_pattern: str) -> str:
    match = re.search(datetime_pattern, file_name)
    return match.group()


def get_datetime(datetime_string: str, format: str) -> datetime.datetime:
    return datetime.datetime.strptime(datetime_string, format)


def extract_index(file_name: str, index_pattern: str) -> str:
    match = re.search(index_pattern, file_name)
    if match:
        return match.group().replace("WA", "")
    else:
        raise ValueError(
            f"Cannot extract index from filename {file_name} with pattern {index_pattern}"
        )


def is_file_name_according_to_pattern(file_name, file_name_pattern) -> bool:
    match = re.search(file_name_pattern, file_name)
    if match:
        return True
    else:
        return False


def identify_file_pattern(file_name: str) -> FileNameSchema:
    if is_file_name_according_to_pattern(file_name, AndroidSchema.file_name_pattern):
        return AndroidSchema
    elif is_file_name_according_to_pattern(file_name, WhatsAppSchema.file_name_pattern):
        return WhatsAppSchema
    else:
        ValueError(f"File name {file_name} is not mapping any known schema")


class FileNameBuilder:
    FILE_PREFIX_PATTERN = "%Y/%m/"
    TARGET_FILE_TIMESTAMP_PATTERN = "%Y%m%dT%H%M%S"

    def __init__(self, file_name_schema: FileNameSchema):
        self.file_name_schema = file_name_schema

    def standardize_file_name(
        self, file_name: str, file_name_schema: Optional[FileNameSchema] = None
    ) -> str:
        if file_name_schema is None:
            file_name_schema = self.file_name_schema

        datetime_string = extract_datetime_string(
            file_name, file_name_schema.timestamp_pattern
        )
        datetime_ = get_datetime(datetime_string, file_name_schema.timestamp_format)
        file_prefix = datetime_.strftime(self.FILE_PREFIX_PATTERN)
        file_timestamp = datetime_.strftime(self.TARGET_FILE_TIMESTAMP_PATTERN)
        if file_name_schema.index_pattern:
            file_index = extract_index(
                file_name, index_pattern=file_name_schema.index_pattern
            )
        else:
            file_index = DEFAULT_FILE_INDEX
        file_extension = file_name.split(".")[-1]
        file_base_name = f"{file_timestamp}_{file_index}.{file_extension}"
        return file_prefix + file_base_name


# file_name_schema = {}
# file_name_schema["android"] = "20240724_182842.jpg"

# android video = "20240724_181843.mp4"


# whats app img = "IMG-20240721-WA0007.jpg"
# whats app img = "VID-20240721-WA0000.mp4"

# "/Interner Speicher/DCIM/Camera"
# "/Interner Speicher/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Images"
