from __future__ import annotations

import json
import logging

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.core.config import Settings
from app.core.security import StaticAdminAuthenticationAdapter
from app.modules.suppliers.acquisition_contracts import AcquisitionFailure
from app.modules.suppliers.source_secrets import (
    EncryptedFileSourceSecretProvider,
    FileSourceSecretProvider,
)
from app.modules.suppliers.source_schemas import SupplierSourceCreate


def _settings(token: str | None) -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://test:test@db/test",
        auth_mode="static",
        ai_monitor_admin_token=token,
    )


def test_static_admin_token_survives_adapter_and_application_recreation() -> None:
    token = "stable-local-administrator-token-123456789"

    first = StaticAdminAuthenticationAdapter(_settings(token))
    restarted = StaticAdminAuthenticationAdapter(_settings(token))

    assert first.authenticate(token).roles == ("system_admin",)
    assert restarted.authenticate(token).permissions


def test_static_admin_rejects_wrong_token_and_never_issues_tokens() -> None:
    adapter = StaticAdminAuthenticationAdapter(
        _settings("stable-local-administrator-token-123456789")
    )

    with pytest.raises(HTTPException) as wrong:
        adapter.authenticate("wrong-token")
    assert wrong.value.status_code == 401
    with pytest.raises(RuntimeError, match="ne generiše"):
        adapter.issue_token("administrator")


def test_missing_static_admin_token_is_a_clear_startup_error() -> None:
    with pytest.raises(RuntimeError, match="AI_MONITOR_ADMIN_TOKEN"):
        _settings(None).validate_runtime_secrets()


def test_static_token_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    token = "stable-local-administrator-token-never-log-this"
    adapter = StaticAdminAuthenticationAdapter(_settings(token))

    with caplog.at_level(logging.DEBUG):
        adapter.authenticate(token)

    assert token not in caplog.text


def test_file_provider_reloads_and_survives_instance_recreation(tmp_path) -> None:
    path = tmp_path / "supplier-secrets.json"
    reference = "secret:supplier/ds"
    path.write_text(
        json.dumps(
            {
                reference: {
                    "placement": "QUERY",
                    "username_parameter": "korisnickoime",
                    "password_parameter": "lozinka",
                    "username": "partner",
                    "password": "hidden",
                }
            }
        ),
        encoding="utf-8",
    )

    first = FileSourceSecretProvider(path)
    restarted = FileSourceSecretProvider(path)

    assert first.resolve(reference) == {
        "query:korisnickoime": "partner",
        "query:lozinka": "hidden",
    }
    assert restarted.resolve(reference) == first.resolve(reference)
    assert restarted.available(reference) is True


def test_file_provider_accepts_windows_utf8_bom(tmp_path) -> None:
    path = tmp_path / "supplier-secrets.json"
    path.write_text(
        json.dumps({"supplier/test": {"api_key": "hidden"}}),
        encoding="utf-8-sig",
    )

    assert FileSourceSecretProvider(path).available("supplier/test") is True


def test_file_provider_persists_new_credentials_across_recreation(tmp_path) -> None:
    path = tmp_path / "supplier-secrets.json"
    path.write_text("{}", encoding="utf-8")
    reference = FileSourceSecretProvider(path).write(
        {
            "portal:username": "partner",
            "portal:password": "hidden",
        }
    )

    assert FileSourceSecretProvider(path).resolve(reference) == {
        "portal:username": "partner",
        "portal:password": "hidden",
    }


def test_encrypted_file_provider_persists_without_plaintext(tmp_path) -> None:
    path = tmp_path / "supplier-secrets.enc"
    key = Fernet.generate_key().decode("ascii")
    provider = EncryptedFileSourceSecretProvider(path, key)

    reference = provider.write(
        {"portal:username": "partner", "portal:password": "hidden-password"}
    )

    raw = path.read_bytes()
    assert b"partner" not in raw
    assert b"hidden-password" not in raw
    assert EncryptedFileSourceSecretProvider(path, key).resolve(reference) == {
        "portal:username": "partner",
        "portal:password": "hidden-password",
    }


def test_encrypted_file_provider_fails_closed_with_wrong_key(tmp_path) -> None:
    path = tmp_path / "supplier-secrets.enc"
    first_key = Fernet.generate_key().decode("ascii")
    EncryptedFileSourceSecretProvider(path, first_key).write(
        {"header:X-API-Key": "hidden"}
    )

    wrong_key = Fernet.generate_key().decode("ascii")
    with pytest.raises(AcquisitionFailure) as failure:
        EncryptedFileSourceSecretProvider(path, wrong_key).resolve(
            "secret:supplier/unknown"
        )
    assert failure.value.code == "acquisition_secret_file_invalid"


def test_encrypted_file_provider_rejects_invalid_master_key(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="Fernet"):
        EncryptedFileSourceSecretProvider(tmp_path / "secrets.enc", "not-a-key")


def test_file_provider_reports_missing_unknown_and_invalid_files(tmp_path) -> None:
    missing = FileSourceSecretProvider(tmp_path / "missing.json")
    with pytest.raises(AcquisitionFailure) as missing_error:
        missing.resolve("secret:missing")
    assert missing_error.value.code == "acquisition_secret_file_missing"

    path = tmp_path / "supplier-secrets.json"
    path.write_text("{invalid", encoding="utf-8")
    with pytest.raises(AcquisitionFailure) as invalid_error:
        FileSourceSecretProvider(path).resolve("secret:missing")
    assert invalid_error.value.code == "acquisition_secret_file_invalid"

    path.write_text("{}", encoding="utf-8")
    with pytest.raises(AcquisitionFailure) as unknown_error:
        FileSourceSecretProvider(path).resolve("secret:missing")
    assert unknown_error.value.code == "acquisition_secret_reference_unknown"


def test_file_provider_never_logs_secret_values(
    tmp_path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "supplier-password-never-log-this"
    path = tmp_path / "supplier-secrets.json"
    path.write_text(
        json.dumps({"secret:supplier/test": {"password": secret}}),
        encoding="utf-8",
    )

    with caplog.at_level(logging.DEBUG):
        FileSourceSecretProvider(path).resolve("secret:supplier/test")

    assert secret not in caplog.text


def test_new_sources_accept_readable_supplier_secret_references() -> None:
    source = SupplierSourceCreate(
        name="Novi cenovnik",
        source_type="HTTP",
        configuration={
            "url": "https://supplier.invalid/cenovnik.xlsx",
            "expected_content_type": "EXCEL",
        },
        secret_reference="supplier/ewe_computers",
    )

    assert source.secret_reference == "supplier/ewe_computers"
