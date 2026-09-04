from __future__ import annotations

from app.modules.suppliers.acquisition_contracts import AcquisitionFailure
from app.modules.suppliers.currency_rate_http import (
    CurrencyRateFetchError,
    FetchedDocument,
    MAX_BYTES,
    fetch_rate_document,
    validate_rate_url,
    validated_document,
)
from app.modules.suppliers.models import SupplierSource
from app.modules.suppliers.portal_http_client import portal_request
from app.modules.suppliers.source_secrets import source_secret_provider


def _strings(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


async def fetch_currency_document(source: SupplierSource, url: str) -> FetchedDocument:
    config = source.configuration
    if str(config.get("authentication_type")) != "PORTAL_FORM":
        return await fetch_rate_document(url)
    await validate_rate_url(url)
    login_url = str(config.get("login_url") or "")
    await validate_rate_url(login_url)
    secrets = source_secret_provider.resolve(source.secret_reference or "")
    username = secrets.get("portal:username")
    password = secrets.get("portal:password")
    if not username or not password:
        raise CurrencyRateFetchError("Pristupni podaci portal konekcije nisu podešeni")
    try:
        response = await portal_request(
            login_url=login_url,
            login_submit_url=str(config["login_submit_url"]) if config.get("login_submit_url") else None,
            download_url=url,
            username_field=str(config.get("username_field") or "username"),
            password_field=str(config.get("password_field") or "password"),
            username=username,
            password=password,
            form_fields=_strings(config.get("login_form_fields")),
            headers=_strings(config.get("request_headers")),
            query={},
            timeout_seconds=min(int(str(config.get("timeout_seconds", 30))), 60),
            verify_tls=True,
            maximum_bytes=MAX_BYTES,
        )
    except AcquisitionFailure as exc:
        raise CurrencyRateFetchError(exc.safe_message) from exc
    if not 200 <= response.status_code < 300:
        raise CurrencyRateFetchError(f"Portal dobavljača je vratio status {response.status_code}")
    return validated_document(response.content, response.content_type or "")


__all__ = ["fetch_currency_document"]
