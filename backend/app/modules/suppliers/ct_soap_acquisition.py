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

SoapFetch = Callable[
    [str, bytes, dict[str, str]],
    Awaitable[HttpResponse],
]

_SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
_CT_NAMESPACE = "http://www.ct4partners.com/B2B"
_SOAP_ACTION = f"{_CT_NAMESPACE}/GetCTProducts_WithAttributes"


async def acquire_ct_payload(
    source: SupplierSource,
    config: dict[str, object],
    maximum_bytes: int,
    username: str,
    password: str,
    fetch: SoapFetch,
) -> AcquiredPayload:
    body = _request_body(username, password)
    response = await fetch(
        str(config["base_url"]),
        body,
        {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{_SOAP_ACTION}"',
        },
    )
    rows = _response_rows(response)
    envelope = {
        "products": rows,
        "source_summary": {
            "product_records": len(rows),
            "products_with_barcode": sum(bool(row.get("BARCODE")) for row in rows),
            "integration_profile": "CT_SOAP",
        },
        "raw_source": base64.b64encode(gzip.compress(response.content)).decode(
            "ascii"
        ),
    }
    content = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    if len(content) > maximum_bytes:
        raise AcquisitionFailure(
            "acquisition_artifact_too_large",
            "Objedinjeni CT cenovnik prelazi dozvoljenu veličinu",
        )
    return AcquiredPayload(
        content=content,
        content_type="application/json",
        original_filename=f"ct-{source.source_code}.json",
        source_metadata={
            "transport": "API_SOAP",
            "integration_profile": "CT_SOAP",
            "http_status": response.status_code,
            "product_records": len(rows),
            "products_with_barcode": sum(bool(row.get("BARCODE")) for row in rows),
        },
    )


def _request_body(username: str, password: str) -> bytes:
    envelope = ElementTree.Element(f"{{{_SOAP_ENV}}}Envelope")
    body = ElementTree.SubElement(envelope, f"{{{_SOAP_ENV}}}Body")
    operation = ElementTree.SubElement(
        body,
        f"{{{_CT_NAMESPACE}}}GetCTProducts_WithAttributes",
    )
    for name, value in (
        ("username", username),
        ("password", password),
        ("productGroupCode", ""),
        ("manufacturerCode", ""),
        ("searchphrase", ""),
    ):
        ElementTree.SubElement(operation, f"{{{_CT_NAMESPACE}}}{name}").text = value
    return cast(
        bytes,
        ElementTree.tostring(
            envelope,
            encoding="utf-8",
            xml_declaration=True,
        ),
    )


def _response_rows(response: HttpResponse) -> list[dict[str, object]]:
    try:
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError as exc:
        raise AcquisitionFailure(
            "acquisition_ct_soap_invalid",
            "CT servis nije vratio ispravan SOAP XML odgovor",
        ) from exc
    fault = next(
        (element for element in root.iter() if _local(element.tag) == "Fault"),
        None,
    )
    if fault is not None:
        text = " ".join(part.strip() for part in fault.itertext() if part.strip())
        normalized = text.casefold()
        if any(word in normalized for word in ("user", "password", "login", "auth")):
            message = "CT nije prihvatio korisničko ime ili lozinku"
        elif "ip" in normalized:
            message = "Javna IP adresa aplikacije nije odobrena kod CT dobavljača"
        else:
            message = "CT SOAP servis je odbio zahtev za cenovnik"
        raise AcquisitionFailure("acquisition_ct_soap_fault", message)
    if not 200 <= response.status_code < 300:
        raise AcquisitionFailure(
            "acquisition_ct_soap_http_failed",
            f"CT SOAP servis je vratio status {response.status_code}",
        )
    products = [
        element for element in root.iter() if _local(element.tag) == "CTPRODUCT"
    ]
    if not products:
        raise AcquisitionFailure(
            "acquisition_ct_products_empty",
            (
                "CT nije vratio proizvode. Proverite pristupne podatke i da li je "
                "javna IP adresa aplikacije odobrena kod dobavljača"
            ),
        )
    return [_product(element) for element in products]


def _product(element: ElementTree.Element) -> dict[str, object]:
    result: dict[str, object] = {}
    for child in element:
        name = _local(child.tag)
        if name == "IMAGE_URLS":
            result[name] = [
                (item.text or "").strip()
                for item in child
                if (item.text or "").strip()
            ]
        elif name == "ATTRIBUTES":
            result[name] = _attributes(child)
        else:
            result[name] = (child.text or "").strip()
    return result


def _attributes(element: ElementTree.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for attribute in element:
        values = {
            _local(child.tag): (child.text or "").strip() for child in attribute
        }
        code = values.get("AttributeCode")
        if code:
            result[code] = values.get("AttributeValue", "")
    return result


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


__all__ = ["acquire_ct_payload"]
