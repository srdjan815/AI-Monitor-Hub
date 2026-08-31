from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, cast
from xml.etree import ElementTree

import pytest

from app.modules.suppliers.acquisition_adapters import HttpSourceAdapter
from app.modules.suppliers.acquisition_contracts import HttpResponse
from app.modules.suppliers.models import SupplierSource
from app.modules.suppliers.source_configuration import ApiSourceConfiguration


PIN_RESPONSE = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <getAllItemsResponse xmlns="http://webservice.b2b.navigator.rs/">
      <return>
        <item id="101" on_stock="true" price="100.50" price_with_discounts="95.25" tax_value="20" warranty="24">
          <ean>0012345678905</ean>
          <erp_code>ERP-101</erp_code>
          <item_code>PIN-101</item_code>
          <item_group id="12"><parent_group id="1"><name>RaÄunari</name></parent_group><name>Laptopovi</name></item_group>
          <manufacturer id="7"><name>Test Brand</name></manufacturer>
          <name>Test proizvod</name>
          <oem>PN-101</oem>
          <stock>12.0</stock>
        </item>
        <item id="102" on_stock="false"><ean>0012345678906</ean><name>Nije na stanju</name></item>
      </return>
    </getAllItemsResponse>
  </soap:Body>
</soap:Envelope>""".encode()


class SoapClient:
    async def soap_request(self, **kwargs: Any) -> HttpResponse:
        assert kwargs["url"] == (
            "https://partner.pinsoft.com/b2b/services/stock-webservice"
        )
        assert kwargs["headers"]["SOAPAction"] == '""'
        root = ElementTree.fromstring(kwargs["body"])
        values = {node.tag.rsplit("}", 1)[-1]: node.text for node in root.iter()}
        assert values["arg0"] == "hidden-guid"
        assert values["arg1"] == "4"
        assert values["arg2"] == "false"
        return HttpResponse(200, PIN_RESPONSE, "text/xml")


class Secrets:
    def resolve(self, reference: str) -> dict[str, str]:
        assert reference == "secret:pin"
        return {"soap:guid": "hidden-guid"}


def _source() -> SupplierSource:
    return cast(
        SupplierSource,
        SimpleNamespace(
            source_type="API",
            source_code="SRC-PIN",
            secret_reference="secret:pin",
            configuration={
                "base_url": (
                    "https://partner.pinsoft.com/b2b/services/stock-webservice"
                ),
                "http_method": "POST",
                "authentication_type": "SOAP_BODY",
                "integration_profile": "PIN_SOAP",
                "pin_shop_id": 4,
                "timeout_seconds": 30,
                "verify_tls": True,
            },
        ),
    )


def test_pin_configuration_requires_soap_body_and_post() -> None:
    with pytest.raises(ValueError, match="SOAP telu"):
        ApiSourceConfiguration.model_validate(
            {
                "base_url": (
                    "https://partner.pinsoft.com/b2b/services/stock-webservice"
                ),
                "http_method": "POST",
                "authentication_type": "BASIC",
                "integration_profile": "PIN_SOAP",
            }
        )


@pytest.mark.asyncio
async def test_pin_feed_returns_only_in_stock_items_without_exposing_guid() -> None:
    payload = await HttpSourceAdapter(
        cast(Any, SoapClient()), Secrets(), 1_000_000
    ).acquire(_source())

    value = json.loads(payload.content)
    assert len(value["products"]) == 1
    assert value["products"][0]["EAN"] == "0012345678905"
    assert value["products"][0]["ITEM_CODE"] == "PIN-101"
    assert value["products"][0]["STOCK"] == "12.0"
    assert value["products"][0]["CATEGORY_PATH"] == [
        "RaÄunari",
        "Laptopovi",
    ]
    assert value["source_summary"]["stock_scope"] == "ON_STOCK_ONLY"
    assert b"hidden-guid" not in payload.content
