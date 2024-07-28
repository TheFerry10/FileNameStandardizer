import domain
import datetime
import pytest


def test_extract_datetime_string_android_file():
    file_name = "20240724_182842.jpg"
    expected_datetime_string = "20240724_182842"
    datetime_pattern = r"\d{8}_\d{6}"
    datetime_string = domain.extract_datetime_string(file_name, datetime_pattern)
    assert expected_datetime_string == datetime_string


def test_extract_datetime_string_from_whatsapp_file():
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
def test_get_datetime(datetime_string, format_, expected_datetime):

    datetime_ = domain.get_datetime(datetime_string, format_)
    assert expected_datetime == datetime_


def test_extract_index():
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
            domain.AndroidSchema,
            "2024/07/20240707T121110_0000.jpg",
        ),
        (
            "IMG-20240721-WA0007.jpg",
            domain.WhatsAppSchema,
            "2024/07/20240721T000000_0007.jpg",
        ),
    ],
)
def test_file_name_standardization(
    original_file_name, file_name_schema, expected_target_file_name
):
    file_name_builder = domain.FileNameBuilder(file_name_schema=file_name_schema)
    target_file_name = file_name_builder.standardize_file_name(
        original_file_name, file_name_schema
    )
    assert expected_target_file_name == target_file_name


@pytest.mark.parametrize(
    "original_file_name, expected_target_file_name",
    [
        (
            "20240707_121110.jpg",
            "2024/07/20240707T121110_0000.jpg",
        ),
        (
            "IMG-20240721-WA0007.jpg",
            "2024/07/20240721T000000_0007.jpg",
        ),
    ],
)
def test_e2e(original_file_name, expected_target_file_name):
    file_name_schema = domain.identify_file_pattern(original_file_name)
    file_name_builder = domain.FileNameBuilder(file_name_schema=file_name_schema)
    target_file_name = file_name_builder.standardize_file_name(
        original_file_name, file_name_schema
    )
    assert expected_target_file_name == target_file_name


@pytest.mark.parametrize(
    "file_name, expected_file_name_schema",
    [
        ("IMG-20240721-WA0007.jpg", domain.WhatsAppSchema),
        ("VID-20240721-WA0007.mp4", domain.WhatsAppSchema),
        ("20240721_121233.jpg", domain.AndroidSchema),
        ("20240721_121233.mp4", domain.AndroidSchema),
    ],
)
def test_identify_file_schema_from_filename(file_name, expected_file_name_schema):
    file_name_schema = domain.identify_file_pattern(file_name)
    assert expected_file_name_schema == file_name_schema
