from __future__ import annotations

import threading
import uuid
from typing import Protocol

from app.core.config import settings
from app.modules.suppliers.acquisition_contracts import AcquisitionFailure


class SourceSecretProvider(Protocol):
    def write(self, values: dict[str, str]) -> str: ...
    def resolve(self, reference: str) -> dict[str, str]: ...
    def available(self, reference: str | None) -> bool: ...


class DevelopmentSecretProvider:
    """Process-local development store; values never enter Source JSON or logs."""

    def __init__(self) -> None:
        self._values: dict[str, dict[str, str]] = {}
        self._lock = threading.Lock()

    def write(self, values: dict[str, str]) -> str:
        reference = f"secret:runtime/{uuid.uuid4()}"
        with self._lock:
            self._values[reference] = dict(values)
        return reference

    def resolve(self, reference: str) -> dict[str, str]:
        with self._lock:
            values = self._values.get(reference)
        if values is None:
            raise AcquisitionFailure(
                "acquisition_secret_resolution_unavailable",
                "Pristupni podaci nisu dostupni; unesite ih ponovo",
            )
        return dict(values)

    def available(self, reference: str | None) -> bool:
        if reference is None:
            return False
        with self._lock:
            return reference in self._values


class ProductionSecretProvider:
    """Fail-closed boundary until an external production vault is configured."""

    def write(self, values: dict[str, str]) -> str:
        raise AcquisitionFailure(
            "acquisition_secret_resolution_unavailable",
            "Produkcioni servis za pristupne podatke nije konfigurisan",
        )

    def resolve(self, reference: str) -> dict[str, str]:
        raise AcquisitionFailure(
            "acquisition_secret_resolution_unavailable",
            "Produkcioni servis za pristupne podatke nije konfigurisan",
        )

    def available(self, reference: str | None) -> bool:
        return False


source_secret_provider: SourceSecretProvider = (
    ProductionSecretProvider()
    if settings.app_env == "production"
    else DevelopmentSecretProvider()
)

__all__ = ["SourceSecretProvider", "source_secret_provider"]
