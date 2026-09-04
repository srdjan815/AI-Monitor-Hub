from __future__ import annotations

from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
    HttpClient,
    SecretResolver,
    SourceAdapter,
)
from app.modules.suppliers.models import SupplierSource
from app.modules.suppliers.source_adapters.adapters import (
    HttpSourceAdapter,
    ManualUploadAdapter,
)

class RejectingSecretResolver:
    def resolve(self, reference: str) -> dict[str, str]:
        raise AcquisitionFailure(
            "acquisition_secret_resolution_unavailable",
            "Resolver poverljivih podataka nije konfigurisan",
        )


class UnsupportedSourceAdapter:
    async def acquire(
        self,
        source: SupplierSource,
        supplied: AcquiredPayload | None = None,
    ) -> AcquiredPayload:
        raise AcquisitionFailure(
            "acquisition_source_type_unsupported",
            f"IzvrÅ¡enje za vrstu {source.source_type} nije podrÅ¾ano u Chapter 3.5",
        )


class SourceAdapterRegistry:
    def __init__(
        self,
        http_client: HttpClient,
        secret_resolver: SecretResolver,
        maximum_bytes: int,
    ) -> None:
        manual = ManualUploadAdapter()
        http = HttpSourceAdapter(http_client, secret_resolver, maximum_bytes)
        unsupported = UnsupportedSourceAdapter()
        self.adapters: dict[str, SourceAdapter] = {
            "MANUAL_UPLOAD": manual,
            "CSV": manual,
            "EXCEL": manual,
            "XML": manual,
            "API": http,
            "HTTP": http,
            "FTP": unsupported,
            "SFTP": unsupported,
            "GOOGLE_DRIVE": unsupported,
            "EMAIL": unsupported,
        }

    def resolve(self, source_type: str) -> SourceAdapter:
        adapter = self.adapters.get(source_type)
        if adapter is None:
            raise AcquisitionFailure(
                "acquisition_source_type_unsupported",
                "Vrsta izvora nije podrÅ¾ana",
            )
        return adapter


__all__ = [
    "RejectingSecretResolver",
    "SourceAdapterRegistry",
    "UnsupportedSourceAdapter",
]

