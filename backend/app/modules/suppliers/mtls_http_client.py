from __future__ import annotations

import asyncio
import base64
import ssl
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from app.modules.suppliers.acquisition_contracts import (
    AcquisitionFailure,
    HttpResponse,
)


async def certificate_request(
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
    return await asyncio.to_thread(
        _certificate_request,
        url,
        method,
        headers,
        query,
        timeout_seconds,
        verify_tls,
        pkcs12_base64,
        password,
        body,
    )


def _certificate_request(
    url: str,
    method: str,
    headers: dict[str, str],
    query: dict[str, str],
    timeout_seconds: int,
    verify_tls: bool,
    pkcs12_base64: str,
    password: str,
    body: bytes | None,
) -> HttpResponse:
    try:
        content = base64.b64decode(pkcs12_base64, validate=True)
        key, certificate, chain = pkcs12.load_key_and_certificates(
            content, password.encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise AcquisitionFailure(
            "acquisition_client_certificate_invalid",
            "Sačuvani klijentski sertifikat nije ispravan",
        ) from exc
    if key is None or certificate is None:
        raise AcquisitionFailure(
            "acquisition_client_certificate_private_key_missing",
            "Sačuvani sertifikat nema klijentski privatni ključ",
        )
    context = ssl.create_default_context()
    if not verify_tls:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    elif chain:
        # Some supplier B2B servers omit their private CA chain. The PKCS#12
        # package issued by that supplier is the scoped trust anchor; public
        # system roots and hostname verification remain enabled.
        context.load_verify_locations(
            cadata=b"".join(
                item.public_bytes(serialization.Encoding.PEM) for item in chain
            ).decode("ascii")
        )
    with tempfile.TemporaryDirectory(prefix="supplier-mtls-") as directory:
        root = Path(directory)
        certificate_path = root / "client-chain.pem"
        key_path = root / "client-key.pem"
        certificate_path.write_bytes(
            certificate.public_bytes(serialization.Encoding.PEM)
            + b"".join(
                item.public_bytes(serialization.Encoding.PEM)
                for item in chain or []
            )
        )
        key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        context.load_cert_chain(certificate_path, key_path)
        target = _target(url, query)
        request = urllib.request.Request(
            target,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(
                request, timeout=timeout_seconds, context=context
            ) as response:
                return HttpResponse(
                    status_code=response.status,
                    content=response.read(),
                    content_type=response.headers.get_content_type(),
                )
        except HTTPError as exc:
            raise AcquisitionFailure(
                "acquisition_http_failed",
                f"Server dobavljača je vratio status {exc.code}",
            ) from exc
        except (TimeoutError, URLError, ssl.SSLError) as exc:
            raise AcquisitionFailure(
                "acquisition_client_certificate_connection_failed",
                "mTLS povezivanje sa serverom dobavljača nije uspelo",
            ) from exc


def _target(url: str, query: dict[str, str]) -> str:
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


__all__ = ["certificate_request"]
