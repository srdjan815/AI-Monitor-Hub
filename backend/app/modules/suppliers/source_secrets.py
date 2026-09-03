from __future__ import annotations

import json
import base64
import os
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.modules.suppliers.acquisition_contracts import AcquisitionFailure


class SourceSecretProvider(Protocol):
    def write(self, values: dict[str, str]) -> str: ...
    def resolve(self, reference: str) -> dict[str, str]: ...
    def available(self, reference: str | None) -> bool: ...
    def write_certificate(self, content: bytes, password: str) -> str: ...


class FileSourceSecretProvider:
    """Persist credentials outside the database in the configured JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def write(self, values: dict[str, str]) -> str:
        reference = f"secret:supplier/{uuid.uuid4()}"
        with self._lock:
            records = self._records()
            records[reference] = dict(values)
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                existing_mode = (
                    self.path.stat().st_mode if self.path.exists() else 0o600
                )
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self.path.parent,
                    prefix=f".{self.path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as temporary:
                    json.dump(records, temporary, ensure_ascii=False, indent=2)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                    temporary_path = Path(temporary.name)
                os.chmod(temporary_path, existing_mode)
                os.replace(temporary_path, self.path)
            except OSError as exc:
                if "temporary_path" in locals():
                    temporary_path.unlink(missing_ok=True)
                raise AcquisitionFailure(
                    "acquisition_secret_store_unavailable",
                    "Pristupni podaci nisu mogli trajno da se sačuvaju",
                ) from exc
        return reference

    def write_certificate(self, content: bytes, password: str) -> str:
        return self.write(
            {
                "mtls:pkcs12_base64": base64.b64encode(content).decode("ascii"),
                "mtls:password": password,
            }
        )

    def resolve(self, reference: str) -> dict[str, str]:
        record = self._records().get(reference)
        if not isinstance(record, dict):
            raise AcquisitionFailure(
                "acquisition_secret_reference_unknown",
                "Credential reference nije pronađen u supplier-secrets.json",
            )
        resolved = self._normalize(record)
        if not resolved:
            raise AcquisitionFailure(
                "acquisition_secret_record_empty",
                "Credential reference nema podešene pristupne podatke",
            )
        return resolved

    def available(self, reference: str | None) -> bool:
        if not reference:
            return False
        try:
            return bool(self.resolve(reference))
        except AcquisitionFailure:
            return False

    def _records(self) -> dict[str, object]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except FileNotFoundError as exc:
            raise AcquisitionFailure(
                "acquisition_secret_file_missing",
                "supplier-secrets.json nije pronađen",
            ) from exc
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AcquisitionFailure(
                "acquisition_secret_file_invalid",
                "supplier-secrets.json nije validan ili nije čitljiv",
            ) from exc
        if not isinstance(value, dict):
            raise AcquisitionFailure(
                "acquisition_secret_file_invalid",
                "supplier-secrets.json mora sadržati JSON objekat",
            )
        return value

    @staticmethod
    def _normalize(record: dict[str, object]) -> dict[str, str]:
        metadata = {
            "placement",
            "username_parameter",
            "password_parameter",
            "token_parameter",
            "api_key_parameter",
        }
        credential_names = {"username", "password", "token", "api_key"}
        direct = {
            str(key): str(value)
            for key, value in record.items()
            if value is not None
            and key not in metadata
            and (
                str(key).startswith(("query:", "header:", "portal:", "soap:"))
                or key not in credential_names
            )
        }
        placement = str(record.get("placement", "HEADER")).upper()
        prefix = {
            "QUERY": "query:",
            "PORTAL_FORM": "portal:",
            "SOAP_BODY": "soap:",
        }.get(placement, "header:")
        parameters = {
            "username": ("username_parameter", "username"),
            "password": ("password_parameter", "password"),
            "token": ("token_parameter", "Authorization"),
            "api_key": ("api_key_parameter", "X-API-Key"),
        }
        for name, (parameter_key, default) in parameters.items():
            value = record.get(name)
            if value is None or not str(value):
                continue
            parameter = str(record.get(parameter_key) or default)
            normalized = str(value)
            if name == "token" and placement == "HEADER":
                normalized = f"Bearer {normalized}"
            direct[f"{prefix}{parameter}"] = normalized
        return direct


class EncryptedFileSourceSecretProvider(FileSourceSecretProvider):
    """Encrypted-at-rest file store with atomic replacement semantics."""

    def __init__(self, path: str | Path, key: str) -> None:
        super().__init__(path)
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise RuntimeError(
                "SUPPLIER_SECRETS_KEY mora biti validan Fernet ključ"
            ) from exc

    def _records(self) -> dict[str, object]:
        try:
            encrypted = self.path.read_bytes()
            plaintext = self._fernet.decrypt(encrypted)
            value = json.loads(plaintext.decode("utf-8"))
        except FileNotFoundError as exc:
            raise AcquisitionFailure(
                "acquisition_secret_file_missing",
                "Šifrovani supplier secret store nije pronađen",
            ) from exc
        except (OSError, InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AcquisitionFailure(
                "acquisition_secret_file_invalid",
                "Šifrovani supplier secret store nije validan ili ključ nije ispravan",
            ) from exc
        if not isinstance(value, dict):
            raise AcquisitionFailure(
                "acquisition_secret_file_invalid",
                "Dešifrovani supplier secret store mora sadržati JSON objekat",
            )
        return value

    def write(self, values: dict[str, str]) -> str:
        reference = f"secret:supplier/{uuid.uuid4()}"
        with self._lock:
            records = self._records() if self.path.exists() else {}
            records[reference] = dict(values)
            temporary_path: Path | None = None
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                payload = json.dumps(
                    records, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=self.path.parent,
                    prefix=f".{self.path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as temporary:
                    temporary.write(self._fernet.encrypt(payload))
                    temporary.flush()
                    os.fsync(temporary.fileno())
                    temporary_path = Path(temporary.name)
                os.chmod(temporary_path, 0o600)
                os.replace(temporary_path, self.path)
            except OSError as exc:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
                raise AcquisitionFailure(
                    "acquisition_secret_store_unavailable",
                    "Šifrovani pristupni podaci nisu mogli trajno da se sačuvaju",
                ) from exc
        return reference


class TestMemorySecretProvider:
    """Explicit test-only provider; never selected by a deployment mode."""

    def __init__(self) -> None:
        self._values: dict[str, dict[str, str]] = {}
        self._lock = threading.Lock()

    def write(self, values: dict[str, str]) -> str:
        reference = f"secret:test/{uuid.uuid4()}"
        with self._lock:
            self._values[reference] = dict(values)
        return reference

    def write_certificate(self, content: bytes, password: str) -> str:
        return self.write(
            {
                "mtls:pkcs12_base64": base64.b64encode(content).decode("ascii"),
                "mtls:password": password,
            }
        )

    def resolve(self, reference: str) -> dict[str, str]:
        with self._lock:
            values = self._values.get(reference)
        if values is None:
            raise AcquisitionFailure(
                "acquisition_secret_resolution_unavailable",
                "Pristupni podaci nisu dostupni u test provider-u",
            )
        return dict(values)

    def available(self, reference: str | None) -> bool:
        if reference is None:
            return False
        with self._lock:
            return reference in self._values


if settings.supplier_secret_mode == "test_memory":
    source_secret_provider: SourceSecretProvider = TestMemorySecretProvider()
elif settings.supplier_secret_mode == "encrypted_file":
    if settings.supplier_secrets_key is None:
        raise RuntimeError("SUPPLIER_SECRETS_KEY nedostaje")
    source_secret_provider = EncryptedFileSourceSecretProvider(
        settings.supplier_secrets_file,
        settings.supplier_secrets_key.get_secret_value(),
    )
else:
    source_secret_provider = FileSourceSecretProvider(settings.supplier_secrets_file)

# Backward-compatible test fixture name; never selected by normal deployment.
DevelopmentSecretProvider = TestMemorySecretProvider

__all__ = [
    "DevelopmentSecretProvider",
    "EncryptedFileSourceSecretProvider",
    "FileSourceSecretProvider",
    "SourceSecretProvider",
    "TestMemorySecretProvider",
    "source_secret_provider",
]
