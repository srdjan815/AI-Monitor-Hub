"""Compatibility façade for the decomposed source-adapter package."""

from app.modules.suppliers.source_adapters.adapters import (
    HttpSourceAdapter,
    ManualUploadAdapter,
)
from app.modules.suppliers.source_adapters.http_client import (
    _LoginFormParser,
    UrllibHttpClient,
)
from app.modules.suppliers.source_adapters.registry import (
    RejectingSecretResolver,
    SourceAdapterRegistry,
    UnsupportedSourceAdapter,
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
