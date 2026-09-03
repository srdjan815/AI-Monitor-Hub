from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.modules.suppliers.models import SupplierSource


class AcquisitionFailure(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message[:1000]


@dataclass(frozen=True, slots=True)
class AcquiredPayload:
    content: bytes
    content_type: str | None
    original_filename: str | None
    source_metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    reference: str
    checksum: str
    size_bytes: int
    content_type: str | None
    original_filename: str | None


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status_code: int
    content: bytes
    content_type: str | None
    filename: str | None = None


class SecretResolver(Protocol):
    def resolve(self, reference: str) -> dict[str, str]: ...


class HttpClient(Protocol):
    async def request(
        self,
        *,
        url: str,
        method: str,
        headers: dict[str, str],
        query: dict[str, str],
        timeout_seconds: int,
        verify_tls: bool,
    ) -> HttpResponse: ...


class SourceAdapter(Protocol):
    async def acquire(
        self,
        source: SupplierSource,
        supplied: AcquiredPayload | None = None,
    ) -> AcquiredPayload: ...


class Parser(Protocol):
    def parse(
        self,
        content: bytes,
        configuration: dict[str, object],
    ) -> list[dict[str, object]]: ...


__all__ = [
    "AcquiredPayload",
    "AcquisitionFailure",
    "HttpClient",
    "HttpResponse",
    "Parser",
    "SecretResolver",
    "SourceAdapter",
    "StoredArtifact",
]
