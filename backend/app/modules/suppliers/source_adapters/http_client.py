from __future__ import annotations

import asyncio
import ssl
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

from app.modules.suppliers.acquisition_contracts import (
    AcquisitionFailure,
    HttpResponse,
)
from app.modules.suppliers.mtls_http_client import certificate_request
from app.modules.suppliers.portal_http_client import (
    LoginFormParser as _LoginFormParser,
    portal_request as perform_portal_request,
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
                return HttpResponse(
                    status_code=response.status,
                    content=response.read(),
                    content_type=response.headers.get_content_type(),
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
        parameters = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
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


__all__ = ["_LoginFormParser", "UrllibHttpClient"]
