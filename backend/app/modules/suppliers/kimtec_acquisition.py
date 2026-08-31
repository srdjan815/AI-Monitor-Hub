from __future__ import annotations

import base64
import gzip
import json
from collections.abc import Awaitable, Callable
from xml.etree import ElementTree

from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
    HttpResponse,
)
from app.modules.suppliers.models import SupplierSource

CertificateFetch = Callable[
    [str, str, bytes | None, dict[str, str]],
    Awaitable[HttpResponse],
]


async def acquire_kimtec_payload(
    source: SupplierSource,
    config: dict[str, object],
    maximum_bytes: int,
    fetch: CertificateFetch,
) -> AcquiredPayload:
    base = str(config["base_url"]).rstrip("/")
    feeds = {
        "catalog": str(config["catalog_endpoint_path"]),
        "price": str(config["price_endpoint_path"]),
    }
    responses: dict[str, HttpResponse] = {}
    for name, path in feeds.items():
        response = await fetch(f"{base}/{path.lstrip('/')}", "GET", None, {})
        if not 200 <= response.status_code < 300 or not response.content:
            raise AcquisitionFailure(
                f"acquisition_kimtec_{name}_failed",
                f"KimTec {name} deo nije uspešno preuzet",
            )
        responses[name] = response
    barcode_body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soap:Body><GetProductsBarcodes xmlns="http://www.msan.hr/B2B/">'
        '<ProductCode></ProductCode>'
        '</GetProductsBarcodes></soap:Body></soap:Envelope>'
    ).encode("utf-8")
    soap_action = str(
        config.get(
            "barcode_soap_action",
            "http://www.msan.hr/B2B/GetProductsBarcodes",
        )
    )
    if soap_action == "http://tempuri.org/GetProductsBarcodes":
        soap_action = "http://www.msan.hr/B2B/GetProductsBarcodes"
    barcode_response = await fetch(
        str(config["barcode_service_url"]),
        "POST",
        barcode_body,
        {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{soap_action}"',
        },
    )
    if not 200 <= barcode_response.status_code < 300 or not barcode_response.content:
        raise AcquisitionFailure(
            "acquisition_kimtec_barcode_failed",
            "KimTec barcode deo nije uspešno preuzet",
        )
    responses["barcode"] = barcode_response
    catalog = _xml_records(responses["catalog"].content, "catalog")
    prices = _xml_records(responses["price"].content, "price")
    barcodes = _xml_records(responses["barcode"].content, "barcode")
    price_by_code = {
        str(row.get("ProductCode", "")).strip(): row
        for row in prices
        if str(row.get("ProductCode", "")).strip()
    }
    barcode_by_code = {
        str(row.get("ProductCode", "")).strip(): row
        for row in barcodes
        if str(row.get("ProductCode", "")).strip()
    }
    products: list[dict[str, object]] = []
    for catalog_row in catalog:
        product_code = str(catalog_row.get("ProductCode", "")).strip()
        if not product_code:
            continue
        merged = dict(catalog_row)
        merged.update(price_by_code.get(product_code, {}))
        barcode = barcode_by_code.get(product_code, {})
        merged.update(barcode)
        if str(barcode.get("BarcodeType", "")).strip().upper() == "EAN":
            merged["EAN"] = str(barcode.get("BarcodeValue", "")).strip()
        products.append(merged)
    envelope = {
        "products": products,
        "source_summary": {
            "catalog_records": len(catalog),
            "price_records": len(prices),
            "barcode_records": len(barcodes),
            "products_with_ean": sum(bool(row.get("EAN")) for row in products),
            "joined_records": len(products),
            "join_key": "ProductCode",
        },
        "raw_sources": {
            name: base64.b64encode(gzip.compress(response.content)).decode("ascii")
            for name, response in responses.items()
        },
    }
    content = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    if len(content) > maximum_bytes:
        raise AcquisitionFailure(
            "acquisition_artifact_too_large",
            "Objedinjeni KimTec cenovnik prelazi dozvoljenu veličinu",
        )
    return AcquiredPayload(
        content=content,
        content_type="application/json",
        original_filename=f"kimtec-{source.source_code}.json",
        source_metadata={
            "transport": "API_MTLS",
            "integration_profile": "KIMTEC_MSAN",
            "catalog_records": len(catalog),
            "price_records": len(prices),
            "barcode_records": len(barcodes),
            "products_with_ean": sum(bool(row.get("EAN")) for row in products),
            "joined_records": len(products),
        },
    )


def _xml_records(content: bytes, feed: str) -> list[dict[str, object]]:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise AcquisitionFailure(
            f"acquisition_kimtec_{feed}_xml_invalid",
            f"KimTec {feed} odgovor nije ispravan XML",
        ) from exc
    records: list[dict[str, object]] = [
        {
            child.tag.rsplit("}", 1)[-1]: (child.text or "").strip()
            for child in item
        }
        for item in root.iter()
        if item.tag.rsplit("}", 1)[-1] == "Table"
    ]
    if not records:
        raise AcquisitionFailure(
            f"acquisition_kimtec_{feed}_empty",
            f"KimTec {feed} odgovor ne sadrži artikle",
        )
    return records


__all__ = ["acquire_kimtec_payload"]
