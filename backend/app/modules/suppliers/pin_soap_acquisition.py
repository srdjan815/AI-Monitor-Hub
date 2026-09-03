from __future__ import annotations

import base64
import gzip
import json
from collections.abc import Awaitable, Callable
from typing import cast
from xml.etree import ElementTree

from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
    HttpResponse,
)
from app.modules.suppliers.models import SupplierSource

SoapFetch = Callable[[str, bytes, dict[str, str]], Awaitable[HttpResponse]]

_SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
_PIN_NAMESPACE = "http://webservice.b2b.navigator.rs/"


async def acquire_pin_payload(
    source: SupplierSource,
    config: dict[str, object],
    maximum_bytes: int,
    guid: str,
    fetch: SoapFetch,
) -> AcquiredPayload:
    response = await fetch(
        str(config["base_url"]),
        _request_body(guid, _shop_id(config.get("pin_shop_id", 4))),
        {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": '""',
        },
    )
    rows = _response_rows(response)
    envelope = {
        "products": rows,
        "source_summary": {
            "product_records": len(rows),
            "products_with_ean": sum(bool(row.get("EAN")) for row in rows),
            "integration_profile": "PIN_SOAP",
            "stock_scope": "ON_STOCK_ONLY",
        },
        "raw_source": base64.b64encode(gzip.compress(response.content)).decode(
            "ascii"
        ),
    }
    content = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    if len(content) > maximum_bytes:
        raise AcquisitionFailure(
            "acquisition_artifact_too_large",
            "PIN/ALSO cenovnik prelazi dozvoljenu veličinu",
        )
    return AcquiredPayload(
        content=content,
        content_type="application/json",
        original_filename=f"pin-also-{source.source_code}.json",
        source_metadata={
            "transport": "API_SOAP",
            "integration_profile": "PIN_SOAP",
            "http_status": response.status_code,
            "product_records": len(rows),
            "products_with_ean": sum(bool(row.get("EAN")) for row in rows),
        },
    )


def _request_body(guid: str, shop_id: int) -> bytes:
    envelope = ElementTree.Element(f"{{{_SOAP_ENV}}}Envelope")
    body = ElementTree.SubElement(envelope, f"{{{_SOAP_ENV}}}Body")
    operation = ElementTree.SubElement(body, f"{{{_PIN_NAMESPACE}}}getAllItems")
    # The production JAX-WS contract exposes positional argument names.
    ElementTree.SubElement(operation, "arg0").text = guid
    ElementTree.SubElement(operation, "arg1").text = str(shop_id)
    ElementTree.SubElement(operation, "arg2").text = "false"
    return cast(
        bytes,
        ElementTree.tostring(envelope, encoding="utf-8", xml_declaration=True),
    )


def _shop_id(value: object) -> int:
    if not isinstance(value, str | int | bytes | bytearray):
        raise AcquisitionFailure(
            "acquisition_pin_shop_invalid",
            "PIN/ALSO identifikator prodavnice nije ispravan",
        )
    return int(value)


def _response_rows(response: HttpResponse) -> list[dict[str, object]]:
    try:
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError as exc:
        raise AcquisitionFailure(
            "acquisition_pin_soap_invalid",
            "PIN/ALSO servis nije vratio ispravan SOAP XML odgovor",
        ) from exc
    fault = next(
        (element for element in root.iter() if _local(element.tag) == "Fault"),
        None,
    )
    if fault is not None:
        text = " ".join(part.strip() for part in fault.itertext() if part.strip())
        normalized = text.casefold()
        message = (
            "PIN/ALSO nije prihvatio klijentski GUID"
            if any(word in normalized for word in ("guid", "client", "auth"))
            else "PIN/ALSO SOAP servis je odbio zahtev za cenovnik"
        )
        raise AcquisitionFailure("acquisition_pin_soap_fault", message)
    if not 200 <= response.status_code < 300:
        raise AcquisitionFailure(
            "acquisition_pin_soap_http_failed",
            f"PIN/ALSO SOAP servis je vratio status {response.status_code}",
        )
    items = [element for element in root.iter() if _local(element.tag) == "item"]
    if not items:
        raise AcquisitionFailure(
            "acquisition_pin_products_empty",
            (
                "PIN/ALSO nije vratio artikle na stanju. Proverite GUID, period "
                "dostupnosti servisa i da li je web servis otključan"
            ),
        )
    rows = [_item(element) for element in items]
    in_stock = [
        row
        for row in rows
        if str(row.get("ON_STOCK", "")).strip().casefold()
        in {"1", "true", "yes", "da"}
    ]
    if not in_stock:
        raise AcquisitionFailure(
            "acquisition_pin_products_empty",
            "PIN/ALSO nije vratio nijedan artikal označen kao dostupan na stanju",
        )
    return in_stock


def _item(element: ElementTree.Element) -> dict[str, object]:
    row: dict[str, object] = {
        str(key).upper(): str(value).strip() for key, value in element.attrib.items()
    }
    for child in element:
        name = _local(child.tag)
        if name == "manufacturer":
            row["MANUFACTURER_ID"] = child.attrib.get("id", "")
            row["MANUFACTURER"] = _child_text(child, "name")
        elif name == "item_group":
            groups = _group_path(child)
            row["CATEGORY_PATH"] = groups
            row["ITEM_GROUP"] = groups[-1] if groups else ""
        elif len(child):
            row[name.upper()] = _nested_value(child)
        else:
            row[name.upper()] = (child.text or "").strip()
    return row


def _group_path(element: ElementTree.Element) -> list[str]:
    current: ElementTree.Element | None = element
    groups: list[str] = []
    while current is not None:
        name = _child_text(current, "name")
        if name:
            groups.append(name)
        current = next(
            (child for child in current if _local(child.tag) == "parent_group"),
            None,
        )
    groups.reverse()
    return groups


def _nested_value(element: ElementTree.Element) -> object:
    values: dict[str, object] = dict(element.attrib)
    for child in element:
        key = _local(child.tag)
        value: object = (
            _nested_value(child) if len(child) else (child.text or "").strip()
        )
        existing = values.get(key)
        if existing is None:
            values[key] = value
        elif isinstance(existing, list):
            existing.append(value)
        else:
            values[key] = [existing, value]
    return values


def _child_text(element: ElementTree.Element, name: str) -> str:
    child = next((item for item in element if _local(item.tag) == name), None)
    return (child.text or "").strip() if child is not None else ""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


__all__ = ["acquire_pin_payload"]
