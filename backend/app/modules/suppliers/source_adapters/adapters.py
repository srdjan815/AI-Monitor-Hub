from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
    HttpClient,
    HttpResponse,
    SecretResolver,
)
from app.modules.suppliers.asbis_acquisition import acquire_asbis_payload
from app.modules.suppliers.ct_soap_acquisition import acquire_ct_payload
from app.modules.suppliers.kimtec_acquisition import acquire_kimtec_payload
from app.modules.suppliers.models import SupplierSource
from app.modules.suppliers.pin_soap_acquisition import acquire_pin_payload


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
        if str(config.get("integration_profile")) == "ASBIS_IT4PROFIT":
            return await acquire_asbis_payload(
                source, config, secret_values, self.maximum_bytes, self.client.request
            )
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


__all__ = ["HttpSourceAdapter", "ManualUploadAdapter"]
