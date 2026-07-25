from __future__ import annotations

import asyncio
import ssl
import urllib.parse
import urllib.request

from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
    HttpClient,
    HttpResponse,
    SecretResolver,
    SourceAdapter,
)
from app.modules.suppliers.models import SupplierSource


class RejectingSecretResolver:
    def resolve(self, reference: str) -> dict[str, str]:
        raise AcquisitionFailure(
            "acquisition_secret_resolution_unavailable",
            "Resolver poverljivih podataka nije konfigurisan",
        )


class UrllibHttpClient:
    async def request(
        self,
        *,
        url: str,
        method: str,
        headers: dict[str, str],
        query: dict[str, str],
        timeout_seconds: int,
        verify_tls: bool,
    ) -> HttpResponse:
        return await asyncio.to_thread(
            self._request,
            url,
            method,
            headers,
            query,
            timeout_seconds,
            verify_tls,
        )

    @staticmethod
    def _request(
        url: str,
        method: str,
        headers: dict[str, str],
        query: dict[str, str],
        timeout_seconds: int,
        verify_tls: bool,
    ) -> HttpResponse:
        separator = "&" if "?" in url else "?"
        target = f"{url}{separator}{urllib.parse.urlencode(query)}" if query else url
        request = urllib.request.Request(target, headers=headers, method=method)
        context = ssl.create_default_context()
        if not verify_tls:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
                context=context,
            ) as response:
                content_type = response.headers.get_content_type()
                return HttpResponse(
                    status_code=response.status,
                    content=response.read(),
                    content_type=content_type,
                )
        except Exception as exc:
            raise AcquisitionFailure(
                "acquisition_http_failed",
                "Spoljni izvor nije dostupan",
            ) from exc


class ManualUploadAdapter:
    async def acquire(
        self,
        source: SupplierSource,
        supplied: AcquiredPayload | None = None,
    ) -> AcquiredPayload:
        if supplied is None:
            raise AcquisitionFailure(
                "acquisition_upload_required",
                "Ručni izvor zahteva upload sadržaja",
            )
        return supplied


class HttpSourceAdapter:
    def __init__(
        self,
        client: HttpClient,
        secrets: SecretResolver,
        maximum_bytes: int,
    ) -> None:
        self.client = client
        self.secrets = secrets
        self.maximum_bytes = maximum_bytes

    async def acquire(
        self,
        source: SupplierSource,
        supplied: AcquiredPayload | None = None,
    ) -> AcquiredPayload:
        config = source.configuration
        if source.source_type == "API":
            base = str(config["base_url"]).rstrip("/")
            path = str(config.get("endpoint_path") or "")
            url = f"{base}/{path.lstrip('/')}" if path else base
        else:
            url = str(config["url"])
        headers = self._string_mapping(config.get("request_headers"))
        if source.secret_reference:
            headers.update(self.secrets.resolve(source.secret_reference))
        response = await self.client.request(
            url=url,
            method=str(config.get("http_method", "GET")),
            headers={str(k): str(v) for k, v in headers.items()},
            query=self._string_mapping(config.get("query_parameters")),
            timeout_seconds=int(str(config.get("timeout_seconds", 30))),
            verify_tls=bool(config.get("verify_tls", True)),
        )
        if not 200 <= response.status_code < 300:
            raise AcquisitionFailure(
                "acquisition_http_status",
                f"Spoljni izvor je vratio status {response.status_code}",
            )
        if len(response.content) > self.maximum_bytes:
            raise AcquisitionFailure(
                "acquisition_artifact_too_large",
                "Odgovor izvora prelazi dozvoljenu veličinu",
            )
        return AcquiredPayload(
            content=response.content,
            content_type=response.content_type,
            original_filename=response.filename,
            source_metadata={"transport": source.source_type},
        )

    @staticmethod
    def _string_mapping(value: object) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        return {str(key): str(item) for key, item in value.items()}


class UnsupportedSourceAdapter:
    async def acquire(
        self,
        source: SupplierSource,
        supplied: AcquiredPayload | None = None,
    ) -> AcquiredPayload:
        raise AcquisitionFailure(
            "acquisition_source_type_unsupported",
            f"Izvršenje za vrstu {source.source_type} nije podržano u Chapter 3.5",
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
                "Vrsta izvora nije podržana",
            )
        return adapter


__all__ = [
    "RejectingSecretResolver",
    "SourceAdapterRegistry",
    "UrllibHttpClient",
]
