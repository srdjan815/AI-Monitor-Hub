"""Compatibility facade for supplier source adapter implementations."""

from app.modules.suppliers.source_adapters import (
    _LoginFormParser,
    HttpSourceAdapter,
    ManualUploadAdapter,
    RejectingSecretResolver,
    SourceAdapterRegistry,
    UnsupportedSourceAdapter,
    UrllibHttpClient,
)

__all__ = [
    "_LoginFormParser",
    "HttpSourceAdapter",
    "ManualUploadAdapter",
    "RejectingSecretResolver",
    "SourceAdapterRegistry",
    "UnsupportedSourceAdapter",
    "UrllibHttpClient",
]
