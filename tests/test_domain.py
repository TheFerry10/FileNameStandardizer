import datetime

import pytest

from filenamestandardizer import domain


def test_extract_datetime_string_android_file() -> None:
    file_name = "20240724_182842.jpg"
    expected_datetime_string = "20240724_182842"
    datetime_pattern = r"\d{8}_\d{6}"
    datetime_string = domain.extract_datetime_string(file_name, datetime_pattern)
    assert expected_datetime_string == datetime_string


def test_extract_datetime_string_from_whatsapp_file() -> None:
    file_name = "IMG-20240721-WA0007.jpg"
    expected_datetime_string = "20240721"
    datetime_pattern = r"\d{8}"
    datetime_string = domain.extract_datetime_string(file_name, datetime_pattern)
    assert expected_datetime_string == datetime_string


@pytest.mark.parametrize(
    "datetime_string,format_,expected_datetime",
    [
        (
            "20240724_182842",
            "%Y%m%d_%H%M%S",
            datetime.datetime(2024, 7, 24, 18, 28, 42),
        ),
        ("20240721", "%Y%m%d", datetime.datetime(2024, 7, 21)),
    ],
)
def test_get_datetime(
    datetime_string: str, format_: str, expected_datetime: datetime.datetime
) -> None:

    datetime_ = domain.get_datetime(datetime_string, format_)
    assert expected_datetime == datetime_


def test_extract_index() -> None:
    expected_index = "0007"
    file_name = "IMG-20240721-WA0007.jpg"
    index_pattern = "WA[0-9]{4}"
    file_name_index = domain.extract_index(file_name, index_pattern)
    assert expected_index == file_name_index


@pytest.mark.parametrize(
    "original_file_name, file_name_schema,expected_target_file_name",
    [
        (
            "20240707_121110.jpg",
            domain.ANDROID_SCHEMA,
            "2024/07/20240707T121110_E3B0C442_0000.jpg",
        ),
        (
            "IMG-20240721-WA0007.jpg",
            domain.WHATSAPP_SCHEMA,
            "2024/07/20240721T000000_E3B0C442_0007.jpg",
        ),
    ],
)
def test_file_name_standardization_with_schema(
    original_file_name: str,
    file_name_schema: domain.FileNameSchema,
    expected_target_file_name: str,
) -> None:

    target_file_name = domain.standardize_file_name(
        original_file_name, file_name_schema
    )
    assert expected_target_file_name == str(target_file_name)


def test_file_name_standardization_with_schema_and_identifier() -> None:
    # Device0 -> D5555C1A
    original_file_name = "20240707_121110.jpg"
    file_name_schema = domain.ANDROID_SCHEMA
    identifier = "Device0"
    expected_target_file_name = "2024/07/20240707T121110_D5555C1A_0000.jpg"
    target_file_name = domain.standardize_file_name(
        original_file_name, file_name_schema, identifier
    )
    assert expected_target_file_name == str(target_file_name)


@pytest.mark.parametrize(
    "original_file_name, expected_target_file_name",
    [
        (
            "20240707_121110.jpg",
            "2024/07/20240707T121110_E3B0C442_0000.jpg",
        ),
        (
            "20240707_121110.mp4",
            "2024/07/20240707T121110_E3B0C442_0000.mp4",
        ),
        (
            "IMG-20240721-WA0007.jpg",
            "2024/07/20240721T000000_E3B0C442_0007.jpg",
        ),
        (
            "VID-20240721-WA0007.mp4",
            "2024/07/20240721T000000_E3B0C442_0007.mp4",
        ),
    ],
)
def test_standardize_file_name_with_schema_estimation(
    original_file_name: str, expected_target_file_name: str
) -> None:
    target_file_name = domain.standardize_file_name(original_file_name)
    assert expected_target_file_name == str(target_file_name)


def test_standardize_file_name_raise_value_error_on_unknown_file_schema() -> None:
    original_file_name = "IMG-20240721.jpg"
    with pytest.raises(ValueError):
        domain.standardize_file_name(original_file_name)


@pytest.mark.parametrize(
    "file_name, expected_file_name_schema",
    [
        ("IMG-20240721-WA0007.jpg", domain.WHATSAPP_SCHEMA),
        ("VID-20240721-WA0007.mp4", domain.WHATSAPP_SCHEMA),
        ("20240721_121233.jpg", domain.ANDROID_SCHEMA),
        ("20240721_121233.mp4", domain.ANDROID_SCHEMA),
    ],
)
def test_identify_file_schema_from_filename(
    file_name: str, expected_file_name_schema: domain.FileNameSchema
) -> None:
    file_name_schema = domain.identify_file_pattern(file_name)
    assert expected_file_name_schema == file_name_schema


def test_raise_value_error_on_unknown_file_schema() -> None:
    file_name = "IMG-20240721.jpg"
    with pytest.raises(ValueError):
        domain.identify_file_pattern(file_name)


def test_read_files_from_directory() -> None:
    directory_path = "tests/data"
    files = domain.read_files_from_directory(
        directory_path, extensions=[".jpg", ".mp4"]
    )

    expected_files = [
        "tests/data/20240724_182842.jpg",
        "tests/data/IMG-unknown_schema.jpg",
        "tests/data/VID-20240721-WA0000.mp4",
    ]
    assert sorted(files) == sorted(expected_files)


def test_standardize_file_names_in_directory() -> None:
    expected_standardized_files = {
        "tests/data/20240724_182842.jpg": ("2024/07/20240724T182842_E3B0C442_0000.jpg"),
        "tests/data/VID-20240721-WA0000.mp4": (
            "2024/07/20240721T000000_E3B0C442_0000.mp4"
        ),
    }
    directory_path = "tests/data"
    standardized_files = domain.standardize_files_in_directory(
        directory_path, extensions=[".jpg", ".mp4"]
    )
    assert standardized_files == expected_standardized_files
