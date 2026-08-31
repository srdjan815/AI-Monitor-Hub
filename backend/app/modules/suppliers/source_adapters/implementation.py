from __future__ import annotations

import asyncio
import ssl
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable
from typing import cast
from urllib.error import HTTPError, URLError

from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
    HttpClient,
    HttpResponse,
    SecretResolver,
    SourceAdapter,
)
from app.modules.suppliers.ct_soap_acquisition import acquire_ct_payload
from app.modules.suppliers.kimtec_acquisition import acquire_kimtec_payload
from app.modules.suppliers.models import SupplierSource
from app.modules.suppliers.mtls_http_client import certificate_request
from app.modules.suppliers.pin_soap_acquisition import acquire_pin_payload
from app.modules.suppliers.portal_http_client import (
    LoginFormParser as _LoginFormParser,
    portal_request as perform_portal_request,
)


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
        body: bytes | None = None,
    ) -> HttpResponse:
        target = UrllibHttpClient._target(url, query)
        request = urllib.request.Request(
            target,
            data=body,
            headers=headers,
            method=method,
        )
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
        except HTTPError as exc:
            if exc.code in {401, 403}:
                message = "Podaci za prijavu nisu prihvaćeni"
            elif exc.code == 404:
                message = "Cenovnik nije pronađen na unetoj adresi"
            else:
                message = f"Server dobavljača je vratio status {exc.code}"
            raise AcquisitionFailure("acquisition_http_failed", message) from exc
        except (TimeoutError, URLError) as exc:
            raise AcquisitionFailure(
                "acquisition_http_failed",
                "Server dobavljača nije odgovorio ili nije dostupan",
            ) from exc

    async def soap_request(
        self,
        *,
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout_seconds: int,
        verify_tls: bool,
    ) -> HttpResponse:
        return await asyncio.to_thread(
            self._soap_request,
            url,
            body,
            headers,
            timeout_seconds,
            verify_tls,
        )

    @staticmethod
    def _soap_request(
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout_seconds: int,
        verify_tls: bool,
    ) -> HttpResponse:
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
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
                return HttpResponse(
                    status_code=response.status,
                    content=response.read(),
                    content_type=response.headers.get_content_type(),
                )
        except HTTPError as exc:
            return HttpResponse(
                status_code=exc.code,
                content=exc.read(),
                content_type=(
                    exc.headers.get_content_type() if exc.headers is not None else None
                ),
            )
        except (TimeoutError, URLError) as exc:
            raise AcquisitionFailure(
                "acquisition_ct_soap_connection_failed",
                "CT SOAP servis nije dostupan ili nije odgovorio na vreme",
            ) from exc

    @staticmethod
    def _target(url: str, query: dict[str, str]) -> str:
        if not query:
            return url
        parsed = urllib.parse.urlsplit(url)
        parameters = dict(
            urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        )
        parameters.update(query)
        return urllib.parse.urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urllib.parse.urlencode(parameters),
                parsed.fragment,
            )
        )

    async def certificate_request(
        self,
        *,
        url: str,
        method: str,
        headers: dict[str, str],
        query: dict[str, str],
        timeout_seconds: int,
        verify_tls: bool,
        pkcs12_base64: str,
        password: str,
        body: bytes | None = None,
    ) -> HttpResponse:
        return await certificate_request(
            url=url,
            method=method,
            headers=headers,
            query=query,
            timeout_seconds=timeout_seconds,
            verify_tls=verify_tls,
            pkcs12_base64=pkcs12_base64,
            password=password,
            body=body,
        )

    async def portal_request(
        self,
        *,
        login_url: str,
        login_submit_url: str | None,
        download_url: str,
        username_field: str,
        password_field: str,
        username: str,
        password: str,
        form_fields: dict[str, str],
        headers: dict[str, str],
        query: dict[str, str],
        timeout_seconds: int,
        verify_tls: bool,
    ) -> HttpResponse:
        return await perform_portal_request(
            login_url=login_url,
            login_submit_url=login_submit_url,
            download_url=download_url,
            username_field=username_field,
            password_field=password_field,
            username=username,
            password=password,
            form_fields=form_fields,
            headers=headers,
            query=query,
            timeout_seconds=timeout_seconds,
            verify_tls=verify_tls,
        )


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
        query = self._string_mapping(config.get("query_parameters"))
        secret_values: dict[str, str] = {}
        if source.secret_reference:
            secret_values = self.secrets.resolve(source.secret_reference)
        if str(config.get("integration_profile")) == "CT_SOAP":
            return await self._ct_payload(
                source,
                config,
                secret_values,
                headers,
            )
        if str(config.get("integration_profile")) == "PIN_SOAP":
            return await self._pin_payload(source, config, secret_values, headers)
        if source.secret_reference:
            for key, value in secret_values.items():
                if key.startswith("query:"):
                    query[key.removeprefix("query:")] = value
                elif key.startswith("header:"):
                    headers[key.removeprefix("header:")] = value
                elif not key.startswith(("portal:", "mtls:", "soap:")):
                    headers[key] = value
        timeout_seconds = int(str(config.get("timeout_seconds", 30)))
        verify_tls = bool(config.get("verify_tls", True))
        authentication_type = str(config.get("authentication_type"))
        if (
            authentication_type == "CLIENT_CERTIFICATE"
            and str(config.get("integration_profile")) == "KIMTEC_MSAN"
        ):
            return await self._kimtec_payload(
                source, config, secret_values, headers, query
            )
        if authentication_type == "PORTAL_FORM":
            portal_request = getattr(self.client, "portal_request", None)
            username = secret_values.get("portal:username")
            password = secret_values.get("portal:password")
            if not callable(portal_request) or not username or not password:
                raise AcquisitionFailure(
                    "acquisition_portal_credentials_missing",
                    "Pristupni podaci za prijavu na portal nisu podešeni",
                )
            response = await portal_request(
                login_url=str(config["login_url"]),
                login_submit_url=(
                    str(config["login_submit_url"])
                    if config.get("login_submit_url")
                    else None
                ),
                download_url=url,
                username_field=str(config["username_field"]),
                password_field=str(config["password_field"]),
                username=username,
                password=password,
                form_fields=self._string_mapping(config.get("login_form_fields")),
                headers={str(k): str(v) for k, v in headers.items()},
                query=query,
                timeout_seconds=timeout_seconds,
                verify_tls=verify_tls,
            )
        elif authentication_type == "CLIENT_CERTIFICATE":
            response = await self._certificate_response(
                url, config, secret_values, headers, query
            )
        else:
            response = await self.client.request(
                url=url,
                method=str(config.get("http_method", "GET")),
                headers={str(k): str(v) for k, v in headers.items()},
                query=query,
                timeout_seconds=timeout_seconds,
                verify_tls=verify_tls,
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
            source_metadata={
                "transport": source.source_type,
                "http_status": response.status_code,
            },
        )

    async def _certificate_response(
        self,
        url: str,
        config: dict[str, object],
        secrets: dict[str, str],
        headers: dict[str, str],
        query: dict[str, str],
        *,
        method: str | None = None,
        body: bytes | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        request = getattr(self.client, "certificate_request", None)
        certificate = secrets.get("mtls:pkcs12_base64")
        password = secrets.get("mtls:password")
        if not callable(request) or not certificate or password is None:
            raise AcquisitionFailure(
                "acquisition_client_certificate_missing",
                "Klijentski sertifikat nije podešen za ovu konekciju",
            )
        request_headers = dict(headers)
        request_headers.update(extra_headers or {})
        response: HttpResponse = await request(
            url=url,
            method=method or str(config.get("http_method", "GET")),
            headers=request_headers,
            query=query,
            timeout_seconds=int(str(config.get("timeout_seconds", 30))),
            verify_tls=bool(config.get("verify_tls", True)),
            pkcs12_base64=certificate,
            password=password,
            body=body,
        )
        return response

    async def _kimtec_payload(
        self,
        source: SupplierSource,
        config: dict[str, object],
        secrets: dict[str, str],
        headers: dict[str, str],
        query: dict[str, str],
    ) -> AcquiredPayload:
        async def fetch(
            url: str,
            method: str,
            body: bytes | None,
            extra_headers: dict[str, str],
        ) -> HttpResponse:
            return await self._certificate_response(
                url,
                config,
                secrets,
                headers,
                query,
                method=method,
                body=body,
                extra_headers=extra_headers,
            )

        return await acquire_kimtec_payload(
            source,
            config,
            self.maximum_bytes,
            fetch,
        )

    async def _ct_payload(
        self,
        source: SupplierSource,
        config: dict[str, object],
        secrets: dict[str, str],
        headers: dict[str, str],
    ) -> AcquiredPayload:
        username = self._secret_value(secrets, "username")
        password = self._secret_value(secrets, "password")
        request = getattr(self.client, "soap_request", None)
        if not callable(request) or not username or not password:
            raise AcquisitionFailure(
                "acquisition_ct_credentials_missing",
                "CT korisničko ime i lozinka nisu trajno podešeni",
            )

        async def fetch(
            url: str,
            body: bytes,
            soap_headers: dict[str, str],
        ) -> HttpResponse:
            typed_request = cast(
                Callable[..., Awaitable[HttpResponse]],
                request,
            )
            return await typed_request(
                url=url,
                body=body,
                headers={**headers, **soap_headers},
                timeout_seconds=int(str(config.get("timeout_seconds", 30))),
                verify_tls=bool(config.get("verify_tls", True)),
            )

        return await acquire_ct_payload(
            source,
            config,
            self.maximum_bytes,
            username,
            password,
            fetch,
        )

    async def _pin_payload(
        self,
        source: SupplierSource,
        config: dict[str, object],
        secrets: dict[str, str],
        headers: dict[str, str],
    ) -> AcquiredPayload:
        guid = self._secret_value(secrets, "guid")
        request = getattr(self.client, "soap_request", None)
        if not callable(request) or not guid:
            raise AcquisitionFailure(
                "acquisition_pin_guid_missing",
                "PIN/ALSO klijentski GUID nije trajno podešen",
            )

        async def fetch(
            url: str,
            body: bytes,
            soap_headers: dict[str, str],
        ) -> HttpResponse:
            typed_request = cast(
                Callable[..., Awaitable[HttpResponse]],
                request,
            )
            return await typed_request(
                url=url,
                body=body,
                headers={**headers, **soap_headers},
                timeout_seconds=int(str(config.get("timeout_seconds", 60))),
                verify_tls=bool(config.get("verify_tls", True)),
            )

        return await acquire_pin_payload(
            source,
            config,
            self.maximum_bytes,
            guid,
            fetch,
        )

    @staticmethod
    def _secret_value(values: dict[str, str], name: str) -> str | None:
        return next(
            (
                values[key]
                for key in (
                    f"soap:{name}",
                    f"header:{name}",
                    f"query:{name}",
                    f"portal:{name}",
                    name,
                )
                if values.get(key)
            ),
            None,
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
    "_LoginFormParser",
    "RejectingSecretResolver",
    "SourceAdapterRegistry",
    "UrllibHttpClient",
]
