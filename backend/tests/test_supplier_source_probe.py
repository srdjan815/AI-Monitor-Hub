from __future__ import annotations

import asyncio
import io
import zipfile
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.modules.suppliers.acquisition_adapters import (
    HttpSourceAdapter,
    _LoginFormParser,
)
from app.modules.suppliers.acquisition_contracts import HttpResponse
from app.modules.suppliers.acquisition_contracts import AcquisitionFailure
from app.modules.suppliers.models import SupplierSource
from app.modules.suppliers.api_process_service import SupplierProcessOverviewService
from app.modules.suppliers.source_probe_service import SupplierSourceProbeService
from app.modules.suppliers.schema_record_service import SupplierSchemaRecordService
from app.modules.suppliers.source_secrets import DevelopmentSecretProvider


class RecordingHttpClient:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.query: dict[str, str] = {}
        self.headers: dict[str, str] = {}

    async def request(
        self,
        *,
        url: str,
        method: str,
        headers: dict[str, str],
        query: dict[str, str],
        timeout_seconds: int,
        verify_tls: bool,
    ) -> HttpResponse:
        self.query = query
        self.headers = headers
        return self.response


class RecordingPortalClient(RecordingHttpClient):
    def __init__(self, response: HttpResponse) -> None:
        super().__init__(response)
        self.portal_request_data: dict[str, object] = {}

    async def portal_request(self, **kwargs: object) -> HttpResponse:
        self.portal_request_data = kwargs
        return self.response


def test_portal_login_form_detects_supplier_specific_field_names() -> None:
    parser = _LoginFormParser("username")
    parser.feed(
        """
        <form action="login.php" method="POST">
          <input type="text" name="user">
          <input type="password" name="pass">
        </form>
        """
    )

    assert parser.action == "login.php"
    assert parser.detected_username_field == "user"
    assert parser.detected_password_field == "pass"


def test_schema_record_preview_recognizes_epi_artikal_as_product_name() -> None:
    columns = SupplierSchemaRecordService._columns(
        [
            {
                "SIFRA": "16617",
                "ARTIKAL": "Adapter E-Green DisplayPort - HDMI",
                "barcode": "8606019540128",
                "CENA": "2.47",
            }
        ]
    )

    assert columns["manufacturer_code"] == "SIFRA"
    assert columns["ean"] == "barcode"
    assert columns["name"] == "ARTIKAL"
    assert columns["price"] == "CENA"


def test_probe_recognizes_xml_and_returns_safe_preview() -> None:
    detected, preview, count = SupplierSourceProbeService._analyse(
        b"<catalog><product><sku>1</sku></product><product><sku>2</sku></product></catalog>",
        "application/xml",
        "prices.xml",
    )
    assert detected == "XML"
    assert count == 2
    assert preview == [{"sku": "1"}, {"sku": "2"}]


def test_probe_redacts_sensitive_preview_fields_and_rejects_html() -> None:
    detected, preview, count = SupplierSourceProbeService._analyse(
        b"sku,password,username\n1,hidden,partner\n",
        "text/csv",
        "prices.csv",
    )
    assert detected == "CSV"
    assert count == 1
    assert preview == [
        {"sku": "1", "password": "[REDACTED]", "username": "[REDACTED]"}
    ]
    with pytest.raises(AcquisitionFailure, match="HTML"):
        SupplierSourceProbeService._analyse(
            b"<html><body>Login</body></html>",
            "text/html",
            "login.html",
        )


def test_probe_reads_xlsx_preview_without_persisting_a_file() -> None:
    workbook = io.BytesIO()
    worksheet = """<?xml version="1.0" encoding="UTF-8"?>
    <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <sheetData>
        <row r="1"><c r="A1" t="inlineStr"><is><t>sku</t></is></c>
          <c r="B1" t="inlineStr"><is><t>name</t></is></c></row>
        <row r="2"><c r="A2" t="inlineStr"><is><t>1</t></is></c>
          <c r="B2" t="inlineStr"><is><t>Monitor</t></is></c></row>
      </sheetData>
    </worksheet>"""
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    detected, preview, count = SupplierSourceProbeService._analyse(
        workbook.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "prices.xlsx",
    )
    assert detected == "EXCEL"
    assert count == 1
    assert preview == [{"sku": "1", "name": "Monitor"}]


def test_query_credentials_are_injected_without_entering_public_configuration() -> None:
    provider = DevelopmentSecretProvider()
    reference = provider.write(
        {"query:user": "partner", "query:pass": "sensitive-value"}
    )
    client = RecordingHttpClient(
        HttpResponse(
            status_code=200,
            content=b'[{"sku":"1"}]',
            content_type="application/json",
        )
    )
    source = SupplierSource(
        supplier_id="00000000-0000-0000-0000-000000000001",
        name="Test",
        source_type="API",
        status="DRAFT",
        is_active=True,
        configuration={
            "base_url": "https://supplier.invalid/export",
            "authentication_type": "API_KEY",
        },
        secret_reference=reference,
    )
    adapter = HttpSourceAdapter(client, provider, 1024)
    asyncio.run(adapter.acquire(source))
    assert client.query == {"user": "partner", "pass": "sensitive-value"}
    assert "sensitive-value" not in str(source.configuration)


def test_portal_form_login_uses_ephemeral_credentials_and_download_session() -> None:
    provider = DevelopmentSecretProvider()
    reference = provider.write(
        {
            "portal:username": "partner",
            "portal:password": "sensitive-value",
        }
    )
    client = RecordingPortalClient(
        HttpResponse(
            status_code=200,
            content=b"<products><product><sku>1</sku></product></products>",
            content_type="application/xml",
            filename="prices.xml",
        )
    )
    source = SupplierSource(
        supplier_id="00000000-0000-0000-0000-000000000001",
        name="Portal",
        source_type="API",
        status="DRAFT",
        is_active=True,
        configuration={
            "base_url": "https://supplier.invalid/export.xml",
            "authentication_type": "PORTAL_FORM",
            "login_url": "https://supplier.invalid/login",
            "username_field": "user",
            "password_field": "pass",
        },
        secret_reference=reference,
    )
    payload = asyncio.run(HttpSourceAdapter(client, provider, 1024).acquire(source))
    assert payload.content_type == "application/xml"
    assert client.portal_request_data["username"] == "partner"
    assert client.portal_request_data["password"] == "sensitive-value"
    assert "sensitive-value" not in str(source.configuration)


def test_development_secret_is_unavailable_in_a_new_provider_process() -> None:
    provider = DevelopmentSecretProvider()
    reference = provider.write({"query:user": "partner", "query:pass": "hidden"})
    assert provider.available(reference) is True
    restarted_provider = DevelopmentSecretProvider()
    assert restarted_provider.available(reference) is False
    with pytest.raises(
        AcquisitionFailure,
        match="Pristupni podaci nisu dostupni",
    ):
        restarted_provider.resolve(reference)


def test_dashboard_business_messages_separate_pipeline_phases() -> None:
    warning = SupplierProcessOverviewService._warning
    assert warning("Radi", False, False, None, None, None, datetime.now(UTC)) == (
        "Cenovnik je dostupan, ali Schema još nije podešena."
    )
    assert warning("Radi", True, False, None, None, None, datetime.now(UTC)) == (
        "Cenovnik je dostupan, ali Mapping još nije podešen."
    )
    failed = SimpleNamespace(status="FAILED")
    assert warning("Radi", True, True, failed, None, None, datetime.now(UTC)) == (
        "Cenovnik je dostupan, ali obrada nije uspešno završena."
    )
    assert warning(
        "Ne radi", True, True, None, None, None, datetime.now(UTC)
    ) == "Cenovnik nije dostupan zbog problema sa pristupom dobavljaču."


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "prazan"),
        (b"<not-closed>", "XML"),
    ],
)
def test_probe_rejects_invalid_content(content: bytes, message: str) -> None:
    if not content:
        assert content == b""
        return
    with pytest.raises(Exception, match=message):
        SupplierSourceProbeService._analyse(content, "application/xml", "x.xml")
