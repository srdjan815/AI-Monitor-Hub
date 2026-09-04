from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

MAX_BYTES = 262_144
MAX_REDIRECTS = 2
ALLOWED_TYPES = (
    "text/",
    "application/json",
    "application/xml",
    "application/xhtml+xml",
)


class CurrencyRateFetchError(ValueError):
    pass


@dataclass(frozen=True)
class FetchedDocument:
    content: bytes
    content_type: str
    checksum: str


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


async def validate_rate_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise CurrencyRateFetchError(
            "Dozvoljena je samo javna HTTPS adresa bez korisničkih podataka"
        )
    if parsed.port not in (None, 443):
        raise CurrencyRateFetchError("Izvor kursa mora koristiti standardni HTTPS port")
    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo, parsed.hostname, 443, type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise CurrencyRateFetchError("Adresa izvora nije dostupna") from exc
    addresses = {item[4][0] for item in records}
    if not addresses or any(
        not ipaddress.ip_address(value).is_global for value in addresses
    ):
        raise CurrencyRateFetchError(
            "Privatne, lokalne i rezervisane mrežne adrese nisu dozvoljene"
        )


# Internal compatibility alias for existing focused tests.
_validate_url = validate_rate_url


def _read_once(url: str, timeout: float) -> tuple[int, bytes, str, str | None]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AI-Monitor-Hub-Currency/1.0",
            "Accept": "text/html,application/json,application/xml,text/plain",
        },
    )
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), _NoRedirect()
    )
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            return exc.code, b"", "", exc.headers.get("Location")
        raise CurrencyRateFetchError(f"Izvor je vratio HTTP status {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise CurrencyRateFetchError(
            "Izvor nije dostupan ili nije odgovorio na vreme"
        ) from exc
    with response:
        content_type = response.headers.get_content_type().lower()
        content = response.read(MAX_BYTES + 1)
        return response.status, content, content_type, response.headers.get("Location")


async def fetch_rate_document(url: str, timeout: float = 10.0) -> FetchedDocument:
    current = url
    for redirect in range(MAX_REDIRECTS + 1):
        await validate_rate_url(current)
        status, content, content_type, location = await asyncio.to_thread(
            _read_once, current, timeout
        )
        if 300 <= status < 400:
            if redirect == MAX_REDIRECTS or not location:
                raise CurrencyRateFetchError(
                    "Izvor ima previše ili neispravno preusmerenje"
                )
            current = urllib.parse.urljoin(current, location)
            continue
        if not any(content_type.startswith(value) for value in ALLOWED_TYPES):
            raise CurrencyRateFetchError("Tip sadržaja izvora nije dozvoljen")
        if len(content) > MAX_BYTES:
            raise CurrencyRateFetchError(
                "Odgovor izvora je veći od dozvoljene veličine"
            )
        return FetchedDocument(
            content, content_type, hashlib.sha256(content).hexdigest()
        )
    raise CurrencyRateFetchError("Izvor nije moguće preuzeti")


def validated_document(content: bytes, content_type: str) -> FetchedDocument:
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if not any(normalized_type.startswith(value) for value in ALLOWED_TYPES):
        raise CurrencyRateFetchError("Tip sadržaja izvora nije dozvoljen")
    if len(content) > MAX_BYTES:
        raise CurrencyRateFetchError("Odgovor izvora je veći od dozvoljene veličine")
    return FetchedDocument(content, normalized_type, hashlib.sha256(content).hexdigest())


__all__ = [
    "CurrencyRateFetchError",
    "FetchedDocument",
    "MAX_BYTES",
    "fetch_rate_document",
    "validate_rate_url",
    "validated_document",
]
