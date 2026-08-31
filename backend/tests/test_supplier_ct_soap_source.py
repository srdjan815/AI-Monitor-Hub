from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from xml.etree import ElementTree

import pytest

from app.modules.suppliers.acquisition_adapters import HttpSourceAdapter
from app.modules.suppliers.acquisition_contracts import HttpResponse
from app.modules.suppliers.models import SupplierSource
from app.modules.suppliers.source_configuration import ApiSourceConfiguration
from app.modules.suppliers.source_secrets import FileSourceSecretProvider


CT_RESPONSE = b"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetCTProducts_WithAttributesResponse xmlns="http://www.ct4partners.com/B2B">
      <GetCTProducts_WithAttributesResult>
        <CTPRODUCT>
          <CODE>CT-100</CODE>
          <NAME>Test proizvod</NAME>
          <MANUFACTURERCODE>PN-100</MANUFACTURERCODE>
          <BARCODE>08601234567890</BARCODE>
          <PRICE>123.45</PRICE>
          <IMAGE_URLS><string>https://example.invalid/image.jpg</string></IMAGE_URLS>
          <ATTRIBUTES>
            <ATTRIBUTE><AttributeCode>RAM</AttributeCode><AttributeValue>16 GB</AttributeValue></ATTRIBUTE>
          </ATTRIBUTES>
        </CTPRODUCT>
      </GetCTProducts_WithAttributesResult>
    </GetCTProducts_WithAttributesResponse>
  </soap:Body>
</soap:Envelope>"""


class SoapClient:
    async def soap_request(self, **kwargs: Any) -> HttpResponse:
        assert kwargs["url"] == "https://www.ct4partners.com/WS/CTProductsInStock.asmx"
        assert kwargs["headers"]["Content-Type"] == "text/xml; charset=utf-8"
        assert kwargs["headers"]["SOAPAction"] == (
            '"http://www.ct4partners.com/B2B/GetCTProducts_WithAttributes"'
        )
        root = ElementTree.fromstring(kwargs["body"])
        values = {
            node.tag.rsplit("}", 1)[-1]: node.text for node in root.iter()
        }
        assert values["username"] == "partner"
        assert values["password"] == "hidden"
        assert values["productGroupCode"] is None
        return HttpResponse(200, CT_RESPONSE, "text/xml")


class Secrets:
    def resolve(self, reference: str) -> dict[str, str]:
        assert reference == "secret:ct"
        return {"soap:username": "partner", "soap:password": "hidden"}


def _source() -> SupplierSource:
    return cast(
        SupplierSource,
        SimpleNamespace(
            source_type="API",
            source_code="SRC-CT",
            secret_reference="secret:ct",
            configuration={
                "base_url": "https://www.ct4partners.com/WS/CTProductsInStock.asmx",
                "http_method": "POST",
                "authentication_type": "SOAP_BODY",
                "integration_profile": "CT_SOAP",
                "timeout_seconds": 30,
                "verify_tls": True,
            },
        ),
    )


def test_ct_configuration_requires_soap_body_and_post() -> None:
    with pytest.raises(ValueError, match="SOAP telu"):
        ApiSourceConfiguration.model_validate(
            {
                "base_url": "https://www.ct4partners.com/WS/CTProductsInStock.asmx",
                "http_method": "POST",
                "authentication_type": "BASIC",
                "integration_profile": "CT_SOAP",
            }
        )


@pytest.mark.asyncio
async def test_ct_soap_feed_is_normalized_without_exposing_credentials() -> None:
    payload = await HttpSourceAdapter(
        cast(Any, SoapClient()), Secrets(), 1_000_000
    ).acquire(_source())

    value = json.loads(payload.content)
    assert value["products"] == [
        {
            "CODE": "CT-100",
            "NAME": "Test proizvod",
            "MANUFACTURERCODE": "PN-100",
            "BARCODE": "08601234567890",
            "PRICE": "123.45",
            "IMAGE_URLS": ["https://example.invalid/image.jpg"],
            "ATTRIBUTES": {"RAM": "16 GB"},
        }
    ]
    assert value["source_summary"]["product_records"] == 1
    assert value["source_summary"]["products_with_barcode"] == 1
    assert b"partner" not in payload.content
    assert b"hidden" not in payload.content


def test_ct_credentials_persist_outside_database(tmp_path: Path) -> None:
    path = tmp_path / "supplier-secrets.json"
    path.write_text("{}", encoding="utf-8")
    reference = FileSourceSecretProvider(path).write(
        {"soap:username": "partner", "soap:password": "hidden"}
    )

    restarted = FileSourceSecretProvider(path)
    assert restarted.resolve(reference) == {
        "soap:username": "partner",
        "soap:password": "hidden",
    }
