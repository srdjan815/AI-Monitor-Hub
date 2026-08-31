from __future__ import annotations

import base64
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.modules.suppliers.acquisition_adapters import HttpSourceAdapter
from app.modules.suppliers.acquisition_contracts import HttpResponse
from app.modules.suppliers.models import SupplierSource
from app.modules.suppliers.source_configuration import ApiSourceConfiguration
from app.modules.suppliers.source_secrets import FileSourceSecretProvider


CATALOG = b"""<NewDataSet><Table><ProductCode>100</ProductCode><ProductName>Test</ProductName></Table></NewDataSet>"""
PRICES = b"""<NewDataSet><Table><ProductCode>100</ProductCode><ProductPartnerPrice>12.34</ProductPartnerPrice></Table></NewDataSet>"""
BARCODES = b"""<NewDataSet><Table><ProductCode>100</ProductCode><BarcodeType>EAN</BarcodeType><BarcodeValue>8601234567890</BarcodeValue></Table></NewDataSet>"""


class CertificateClient:
    async def certificate_request(self, **kwargs: Any) -> HttpResponse:
        assert kwargs["pkcs12_base64"] == "certificate"
        assert kwargs["password"] == "password"
        if str(kwargs["url"]).endswith("B2BProductService.asmx"):
            assert kwargs["method"] == "POST"
            assert b"GetProductsBarcodes" in kwargs["body"]
            assert b"http://www.msan.hr/B2B/" in kwargs["body"]
            assert kwargs["headers"]["SOAPAction"] == (
                '"http://www.msan.hr/B2B/GetProductsBarcodes"'
            )
            content = BARCODES
        else:
            content = CATALOG if "GetProductsList" in kwargs["url"] else PRICES
        return HttpResponse(200, content, "application/xml")


class SecretResolver:
    def resolve(self, reference: str) -> dict[str, str]:
        assert reference == "secret:test"
        return {
            "mtls:pkcs12_base64": "certificate",
            "mtls:password": "password",
        }


def test_kimtec_configuration_requires_client_certificate() -> None:
    with pytest.raises(ValueError, match="klijentski sertifikat"):
        ApiSourceConfiguration.model_validate(
            {
                "base_url": "https://b2b.kimtec.rs",
                "integration_profile": "KIMTEC_MSAN",
                "catalog_endpoint_path": "/GetProductsList.aspx",
                "price_endpoint_path": "/GetProductsPriceList.aspx",
                "barcode_service_url": "https://b2b.kimtec.rs/B2BProductService.asmx",
            }
        )


@pytest.mark.asyncio
async def test_kimtec_feeds_are_joined_by_product_code() -> None:
    source = cast(
        SupplierSource,
        SimpleNamespace(
            source_type="API",
            source_code="SRC-TEST",
            secret_reference="secret:test",
            configuration={
                "base_url": "https://b2b.kimtec.rs",
                "http_method": "GET",
                "authentication_type": "CLIENT_CERTIFICATE",
                "integration_profile": "KIMTEC_MSAN",
                "catalog_endpoint_path": "/GetProductsList.aspx",
                "price_endpoint_path": "/GetProductsPriceList.aspx",
                "barcode_service_url": "https://b2b.kimtec.rs/B2BProductService.asmx",
                "timeout_seconds": 30,
                "verify_tls": True,
            },
        ),
    )
    payload = await HttpSourceAdapter(
        cast(Any, CertificateClient()), SecretResolver(), 1_000_000
    ).acquire(source)
    value = json.loads(payload.content)
    assert value["products"] == [
        {
            "ProductCode": "100",
            "ProductName": "Test",
            "ProductPartnerPrice": "12.34",
            "BarcodeType": "EAN",
            "BarcodeValue": "8601234567890",
            "EAN": "8601234567890",
        }
    ]
    assert value["source_summary"]["join_key"] == "ProductCode"
    assert value["source_summary"]["products_with_ean"] == 1
    assert set(value["raw_sources"]) == {"barcode", "catalog", "price"}


def test_file_provider_persists_certificate_outside_database(tmp_path: Path) -> None:
    path = tmp_path / "supplier-secrets.json"
    path.write_text("{}", encoding="utf-8")
    reference = FileSourceSecretProvider(path).write_certificate(
        b"binary-certificate", "certificate-password"
    )
    resolved = FileSourceSecretProvider(path).resolve(reference)
    assert base64.b64decode(resolved["mtls:pkcs12_base64"]) == b"binary-certificate"
    assert resolved["mtls:password"] == "certificate-password"


def test_mtls_client_uses_pkcs12_chain_as_scoped_trust_anchor() -> None:
    source = Path(
        "app/modules/suppliers/mtls_http_client.py"
    ).read_text(encoding="utf-8")
    assert "context.load_verify_locations" in source
    assert "check_hostname = False" in source
    assert source.index("elif chain:") < source.index("context.load_verify_locations")
