from __future__ import annotations

import asyncio
import json
from collections import Counter
from typing import Awaitable, Callable, cast

from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
    HttpResponse,
)
from app.modules.suppliers.asbis_imap import latest_asbis_attachment
from app.modules.suppliers.asbis_ean import resolve_asbis_ean
from app.modules.suppliers.asbis_parsing import (
    action_records,
    html_from_zip,
    normalize_product_code,
    product_code,
    xml_records,
)
from app.modules.suppliers.models import SupplierSource

HttpFetch = Callable[..., Awaitable[HttpResponse]]


async def acquire_asbis_payload(
    source: SupplierSource,
    config: dict[str, object],
    secrets: dict[str, str],
    maximum_bytes: int,
    fetch: HttpFetch,
) -> AcquiredPayload:
    api_user = secrets.get("query:USERNAME")
    api_password = secrets.get("query:PASSWORD")
    imap_user = secrets.get("imap:username")
    imap_password = secrets.get("imap:password")
    if not all((api_user, api_password, imap_user, imap_password)):
        raise AcquisitionFailure(
            "acquisition_asbis_credentials_missing",
            "ASBIS API i IMAP pristupni podaci nisu kompletno podešeni",
        )
    credentials = cast(
        tuple[str, str, str, str],
        (api_user, api_password, imap_user, imap_password),
    )
    responses = await _xml_payloads(config, credentials[0], credentials[1], fetch)
    attachment_name, attachment = await asyncio.to_thread(
        latest_asbis_attachment,
        config,
        credentials[2],
        credentials[3],
        maximum_bytes,
    )
    catalog = xml_records(responses["catalog"].content, "catalog")
    prices = xml_records(responses["price"].content, "price")
    actions = action_records(html_from_zip(attachment, maximum_bytes))
    products, join_summary = _join(catalog, prices, actions)
    summary: dict[str, object] = {
        "catalog_records": len(catalog),
        "price_records": len(prices),
        "promotion_records": len(actions),
        "joined_records": len(products),
        "join_key": "ASBIS_PRODUCT_CODE",
        "promotion_attachment": attachment_name,
        **join_summary,
    }
    content = json.dumps(
        {"products": products, "source_summary": summary}, ensure_ascii=False
    ).encode("utf-8")
    if len(content) > maximum_bytes:
        raise AcquisitionFailure(
            "acquisition_artifact_too_large",
            "Objedinjeni ASBIS cenovnik prelazi dozvoljenu veličinu",
        )
    return AcquiredPayload(
        content=content,
        content_type="application/json",
        original_filename=f"asbis-{source.source_code}.json",
        source_metadata={
            "transport": "API_IMAP",
            "integration_profile": "ASBIS_IT4PROFIT",
            **summary,
        },
    )


async def _xml_payloads(
    config: dict[str, object],
    username: str,
    password: str,
    fetch: HttpFetch,
) -> dict[str, HttpResponse]:
    base = str(config["base_url"]).rstrip("/")
    timeout = int(str(config.get("timeout_seconds", 30)))
    responses: dict[str, HttpResponse] = {}
    for name, path in (
        ("catalog", config["catalog_endpoint_path"]),
        ("price", config["price_endpoint_path"]),
    ):
        response = await fetch(
            url=f"{base}/{str(path).lstrip('/')}",
            method="GET",
            headers={},
            query={"USERNAME": username, "PASSWORD": password},
            timeout_seconds=timeout,
            verify_tls=bool(config.get("verify_tls", True)),
        )
        if not 200 <= response.status_code < 300 or not response.content:
            raise AcquisitionFailure(
                f"acquisition_asbis_{name}_failed",
                f"ASBIS {name} XML nije uspešno preuzet",
            )
        responses[name] = response
    return responses


def _join(
    catalog: list[dict[str, object]],
    prices: list[dict[str, object]],
    actions: list[dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    prices_by_code = _unique_by_code(prices, "price")
    actions_by_code = _unique_by_code(actions, "promotion")
    products: list[dict[str, object]] = []
    catalog_codes: set[str] = set()
    ean_statuses: Counter[str] = Counter()
    for row in catalog:
        code = product_code(row)
        if not code:
            continue
        key = normalize_product_code(code)
        if key in catalog_codes:
            raise AcquisitionFailure(
                "acquisition_asbis_catalog_duplicate_code",
                "ASBIS katalog sadrži duplu šifru artikla",
            )
        catalog_codes.add(key)
        merged = dict(row)
        merged.update(prices_by_code.get(key, {}))
        action = actions_by_code.get(key)
        merged["ASBIS_PRODUCT_CODE"] = code
        ean_resolution = resolve_asbis_ean(
            merged.get("EAN"), merged.get("ATTR_EAN Code")
        )
        merged["ASBIS_VALID_EAN"] = ean_resolution.value
        merged["ASBIS_EAN_STATUS"] = ean_resolution.status.value
        merged["ASBIS_EAN_MESSAGE"] = ean_resolution.message
        ean_statuses[ean_resolution.status.value] += 1
        merged["PROMOTION_ACTIVE"] = bool(action)
        # NOTES is a stable ASBIS source field. Keeping it present on every
        # product makes schema inference independent of which records happen
        # to be in its initial sample.
        merged["NOTES"] = str(action.get("NOTES", "")) if action else ""
        if action:
            merged.update(action)
            merged["EFFECTIVE_PRICE"] = action["PROMOTION_PRICE"]
        products.append(merged)
    return products, {
        "catalog_without_code": len(catalog) - len(catalog_codes),
        "catalog_without_price": sum(
            key not in prices_by_code for key in catalog_codes
        ),
        "unmatched_price_records": len(set(prices_by_code) - catalog_codes),
        "unmatched_promotion_records": len(set(actions_by_code) - catalog_codes),
        "valid_ean_records": sum(
            count
            for status, count in ean_statuses.items()
            if status not in {"CONFLICT", "MISSING", "INVALID"}
        ),
        "ean_status_counts": dict(sorted(ean_statuses.items())),
    }


def _unique_by_code(
    rows: list[dict[str, object]], feed: str
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        code = product_code(row)
        if not code:
            continue
        key = normalize_product_code(code)
        if key in result:
            raise AcquisitionFailure(
                f"acquisition_asbis_{feed}_duplicate_code",
                f"ASBIS {feed} izvor sadrži duplu šifru artikla",
            )
        result[key] = row
    return result


__all__ = ["acquire_asbis_payload"]
