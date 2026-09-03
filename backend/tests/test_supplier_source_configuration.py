from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.modules.suppliers.enums import SupplierSourceType
from app.modules.suppliers.source_validation_service import (
    SupplierSourceValidationService,
)

VALID_CONFIGURATIONS: dict[SupplierSourceType, dict[str, object]] = {
    SupplierSourceType.API: {
        "base_url": "https://supplier.example",
        "authentication_type": "NONE",
    },
    SupplierSourceType.HTTP: {
        "url": "https://supplier.example/feed.csv",
        "expected_content_type": "CSV",
    },
    SupplierSourceType.CSV: {
        "delivery_method": "SFTP",
        "filename_pattern": "*.csv",
    },
    SupplierSourceType.EXCEL: {
        "delivery_method": "MANUAL_UPLOAD",
        "filename_pattern": "*.xlsx",
        "header_row": 1,
        "data_start_row": 2,
    },
    SupplierSourceType.XML: {
        "delivery_method": "HTTP",
        "filename_pattern": "*.xml",
        "item_path": "/catalog/item",
    },
    SupplierSourceType.FTP: {
        "host": "ftp.example.test",
        "filename_pattern": "*.csv",
    },
    SupplierSourceType.SFTP: {
        "host": "sftp.example.test",
        "username": "feed",
        "filename_pattern": "*.xlsx",
        "host_key_fingerprint": "SHA256:abcdefghijklmnop",
    },
    SupplierSourceType.GOOGLE_DRIVE: {"folder_id": "folder-123"},
    SupplierSourceType.EMAIL: {
        "mailbox": "feed@example.test",
        "attachment_filename_pattern": "*.csv",
    },
    SupplierSourceType.MANUAL_UPLOAD: {
        "accepted_file_types": ["CSV", "EXCEL"],
        "maximum_file_size_mb": 25,
    },
}


@pytest.mark.parametrize(("source_type", "configuration"), VALID_CONFIGURATIONS.items())
def test_every_source_type_accepts_valid_minimal_configuration(
    source_type: SupplierSourceType,
    configuration: dict[str, object],
) -> None:
    normalized = SupplierSourceValidationService.normalize_configuration(
        source_type,
        configuration,
    )
    assert normalized


@pytest.mark.parametrize("source_type", list(SupplierSourceType))
def test_every_source_type_rejects_unknown_and_credential_fields(
    source_type: SupplierSourceType,
) -> None:
    base = dict(VALID_CONFIGURATIONS[source_type])
    with pytest.raises(HTTPException) as unknown:
        SupplierSourceValidationService.normalize_configuration(
            source_type,
            {**base, "unknown_setting": True},
        )
    assert unknown.value.detail["code"] == "supplier_source_invalid_configuration"

    with pytest.raises(HTTPException) as secret:
        SupplierSourceValidationService.normalize_configuration(
            source_type,
            {**base, "password": "must-not-be-stored"},
        )
    assert secret.value.detail["code"] == "supplier_source_invalid_configuration"
    assert "must-not-be-stored" not in str(secret.value.detail)


@pytest.mark.parametrize(
    ("source_type", "configuration"),
    [
        (SupplierSourceType.API, {"base_url": "not-a-url"}),
        (SupplierSourceType.API, {"base_url": "https://x.test", "http_method": "PUT"}),
        (
            SupplierSourceType.HTTP,
            {"url": "https://x.test", "expected_content_type": "PDF"},
        ),
        (
            SupplierSourceType.CSV,
            {"delivery_method": "LOCAL", "filename_pattern": "*.csv"},
        ),
        (
            SupplierSourceType.EXCEL,
            {
                "delivery_method": "EMAIL",
                "filename_pattern": "*.xlsx",
                "header_row": 2,
                "data_start_row": 2,
            },
        ),
        (
            SupplierSourceType.XML,
            {"delivery_method": "HTTP", "filename_pattern": "*.xml"},
        ),
        (SupplierSourceType.FTP, {"filename_pattern": "*.csv"}),
        (
            SupplierSourceType.SFTP,
            {"host": "x.test", "filename_pattern": "*.csv"},
        ),
        (SupplierSourceType.GOOGLE_DRIVE, {}),
        (
            SupplierSourceType.EMAIL,
            {"attachment_filename_pattern": "*.csv"},
        ),
        (
            SupplierSourceType.MANUAL_UPLOAD,
            {"accepted_file_types": ["PDF"], "maximum_file_size_mb": 0},
        ),
    ],
)
def test_source_specific_invalid_configuration_is_rejected(
    source_type: SupplierSourceType,
    configuration: dict[str, object],
) -> None:
    with pytest.raises(HTTPException) as error:
        SupplierSourceValidationService.normalize_configuration(
            source_type,
            configuration,
        )
    assert error.value.detail["code"] == "supplier_source_invalid_configuration"


def test_api_and_transport_secret_requirements_are_explicit() -> None:
    validator = SupplierSourceValidationService()
    assert not validator.requires_secret(
        SupplierSourceType.API,
        {"base_url": "https://x.test", "authentication_type": "NONE"},
    )
    assert validator.requires_secret(
        SupplierSourceType.API,
        {"base_url": "https://x.test", "authentication_type": "BEARER"},
    )
    for source_type in (
        SupplierSourceType.FTP,
        SupplierSourceType.SFTP,
        SupplierSourceType.EMAIL,
    ):
        assert validator.requires_secret(
            source_type,
            VALID_CONFIGURATIONS[source_type],
        )


def test_ewe_api_is_the_only_approved_public_http_endpoint() -> None:
    normalized = SupplierSourceValidationService.normalize_configuration(
        SupplierSourceType.API,
        {
            "base_url": "http://apicatalog.ewe.rs:5001/api/",
            "authentication_type": "BASIC",
            "query_parameters": {
                "images": "1",
                "currency": "rsd",
                "pdv": "0",
            },
        },
    )
    assert normalized["base_url"] == "http://apicatalog.ewe.rs:5001/api/"

    rejected_urls = (
        "http://supplier.example/api/",
        "http://apicatalog.ewe.rs/api/",
        "http://apicatalog.ewe.rs:5001/other/",
        "http://sub.apicatalog.ewe.rs:5001/api/",
    )
    for url in rejected_urls:
        with pytest.raises(HTTPException) as error:
            SupplierSourceValidationService.normalize_configuration(
                SupplierSourceType.API,
                {"base_url": url, "authentication_type": "NONE"},
            )
        assert error.value.detail["code"] == "supplier_source_invalid_configuration"


def test_ewe_base_url_rejects_embedded_query_and_credentials() -> None:
    unsafe_urls = (
        "http://user:secret@apicatalog.ewe.rs:5001/api/",
        "http://apicatalog.ewe.rs:5001/api/?user=secret",
        "http://apicatalog.ewe.rs:5001/api/#secret",
    )
    for url in unsafe_urls:
        with pytest.raises(HTTPException) as error:
            SupplierSourceValidationService.normalize_configuration(
                SupplierSourceType.API,
                {"base_url": url, "authentication_type": "BASIC"},
            )
        assert error.value.detail["code"] == "supplier_source_invalid_configuration"


@pytest.mark.parametrize(
    ("source_type", "field"),
    [
        (SupplierSourceType.API, "api_key"),
        (SupplierSourceType.FTP, "password"),
        (SupplierSourceType.SFTP, "private_key"),
        (SupplierSourceType.GOOGLE_DRIVE, "service_account_json"),
        (SupplierSourceType.EMAIL, "token"),
    ],
)
def test_explicit_credential_payloads_are_never_accepted(
    source_type: SupplierSourceType,
    field: str,
) -> None:
    with pytest.raises(HTTPException) as error:
        SupplierSourceValidationService.normalize_configuration(
            source_type,
            {**VALID_CONFIGURATIONS[source_type], field: "sensitive-value"},
        )
    assert error.value.detail["code"] == "supplier_source_invalid_configuration"
    assert "sensitive-value" not in str(error.value.detail)
