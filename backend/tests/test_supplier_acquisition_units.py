from __future__ import annotations

import hashlib
import io
import uuid
import zipfile
from pathlib import Path

import pytest

from app.modules.suppliers.acquisition_adapters import HttpSourceAdapter
from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
    HttpResponse,
)
from app.modules.suppliers.acquisition_parsers import ParserRegistry
from app.modules.suppliers.acquisition_storage import LocalArtifactStorage
from app.modules.suppliers.acquisition_transformations import MappingExecutor
from app.modules.suppliers.mapping_profile_models import SupplierMappingRule
from app.modules.suppliers.models import SupplierSource


def test_artifact_storage_is_atomic_bounded_and_path_safe(tmp_path: Path) -> None:
    storage = LocalArtifactStorage(tmp_path, maximum_bytes=20)
    payload = AcquiredPayload(b"sku,name\n1,Zmaj\n", "text/csv", "ulaz.csv", {})
    stored = storage.store(payload)
    assert stored.reference != "ulaz.csv"
    assert stored.checksum == hashlib.sha256(payload.content).hexdigest()
    assert storage.load(stored.reference) == payload.content
    with pytest.raises(AcquisitionFailure, match="bezbedan"):
        storage.store(AcquiredPayload(b"x", None, "../tajna.csv", {}))
    with pytest.raises(AcquisitionFailure, match="veli"):
        storage.store(AcquiredPayload(b"x" * 21, None, "velik.csv", {}))
    storage.delete(stored.reference)
    assert not list(tmp_path.iterdir())


def test_csv_json_xml_parsers_preserve_unicode_quotes_and_large_text() -> None:
    registry = ParserRegistry()
    long_text = "reč\n<html>opis</html> " + ("vrlo dugo " * 3000)
    csv_payload = f'sku,description\nA-1,"{long_text}"\n'.encode()
    csv_config = {"delimiter": ",", "encoding": "utf-8"}
    csv_rows = registry.resolve("CSV", "text/csv", "data.csv", csv_config).parse(
        csv_payload, csv_config
    )
    assert csv_rows == [{"sku": "A-1", "description": long_text}]
    json_rows = registry.resolve("API", "application/json", None, {}).parse(
        b'{"items":[{"sku":"A-1","name":"Zmaj"}]}', {}
    )
    assert json_rows[0]["name"] == "Zmaj"
    xml_config = {"item_path": "item"}
    xml_rows = registry.resolve("XML", "application/xml", "data.xml", xml_config).parse(
        "<items><item><sku>Č-1</sku></item></items>".encode(), xml_config
    )
    assert xml_rows == [{"sku": "Č-1"}]


def test_parser_rejects_malformed_and_xxe_payloads() -> None:
    registry = ParserRegistry()
    cases = [
        (b"{", "API", {}, None, "application/json"),
        (
            b'<!DOCTYPE x [<!ENTITY ext SYSTEM "file:///etc/passwd">]><x>&ext;</x>',
            "XML",
            {"item_path": "item"},
            "x.xml",
            "application/xml",
        ),
    ]
    for content, source_type, config, filename, content_type in cases:
        with pytest.raises(AcquisitionFailure):
            registry.resolve(source_type, content_type, filename, config).parse(
                content, config
            )


def test_excel_parser_uses_first_sheet_and_never_executes_formula() -> None:
    workbook = io.BytesIO()
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main"><sheets><sheet name="Podaci" '
            'sheetId="1" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
            '2006/relationships"><Relationship Id="rId1" '
            'Target="worksheets/sheet1.xml" Type="x"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/'
            '2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr">'
            '<is><t>sku</t></is></c><c r="B1" t="inlineStr"><is><t>formula</t>'
            '</is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>A-1</t>'
            '</is></c><c r="B2"><f>1+1</f><v>2</v></c></row></sheetData>'
            "</worksheet>",
        )
    registry = ParserRegistry()
    rows = registry.resolve(
        "EXCEL",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "data.xlsx",
        {},
    ).parse(workbook.getvalue(), {})
    assert rows == [{"sku": "A-1", "formula": ""}]


@pytest.mark.parametrize(
    ("kind", "source", "config", "default", "expected"),
    [
        ("COPY", " x ", None, None, " x "),
        ("DEFAULT_VALUE", "", None, "fallback", "fallback"),
        ("CONSTANT", "ignored", None, "fixed", "fixed"),
        ("CONCAT", "x", {"values": ["pre", "$value"], "separator": "-"}, None, "pre-x"),
        ("SPLIT", "a|b", {"delimiter": "|", "index": 1}, None, "b"),
        ("TRIM", " x ", None, None, "x"),
        ("UPPERCASE", "č", None, None, "Č"),
        ("LOWERCASE", "Č", None, None, "č"),
        ("REPLACE", "abc", {"old": "b", "new": "B"}, None, "aBc"),
        ("REGEX", "a12", {"pattern": r"\d+", "replacement": "X"}, None, "aX"),
    ],
)
def test_all_frozen_mapping_transformations(
    kind: str,
    source: object,
    config: dict[str, object] | None,
    default: str | None,
    expected: object,
) -> None:
    field_id = uuid.uuid4()
    rule = SupplierMappingRule(
        id=uuid.uuid4(),
        mapping_profile_id=uuid.uuid4(),
        schema_field_id=field_id,
        target_attribute="target",
        transformation_type=kind,
        transformation_config=config,
        default_value=default,
        validation_rule=None,
        priority=1,
        required=True,
        is_active=True,
    )
    result = MappingExecutor().execute({field_id: source}, [rule])
    assert result.problems == []
    assert result.mapped == {"target": expected}


def test_required_mapping_error_and_optional_warning_are_structured() -> None:
    field_id = uuid.uuid4()

    def broken(required: bool) -> SupplierMappingRule:
        return SupplierMappingRule(
            id=uuid.uuid4(),
            mapping_profile_id=uuid.uuid4(),
            schema_field_id=field_id,
            target_attribute=f"target-{required}",
            transformation_type="SPLIT",
            transformation_config={},
            priority=1,
            required=required,
            is_active=True,
        )

    required = MappingExecutor().execute({field_id: "x"}, [broken(True)])
    optional = MappingExecutor().execute({field_id: "x"}, [broken(False)])
    assert required.problems[0].severity == "ERROR"
    assert optional.problems[0].severity == "WARNING"


@pytest.mark.asyncio
async def test_http_adapter_uses_fake_client_and_fake_secret_resolver() -> None:
    requests: list[dict[str, object]] = []

    class Client:
        async def request(self, **kwargs: object) -> HttpResponse:
            requests.append(kwargs)
            return HttpResponse(200, b'[{"sku":"A-1"}]', "application/json")

    class Secrets:
        def resolve(self, reference: str) -> dict[str, str]:
            assert reference == "secret:supplier/test"
            return {"Authorization": "Bearer hidden"}

    source = SupplierSource(
        id=uuid.uuid4(),
        supplier_id=uuid.uuid4(),
        source_code="SRC-999999",
        name="Fake API",
        source_type="API",
        status="ACTIVE",
        configuration={
            "base_url": "https://supplier.invalid",
            "endpoint_path": "/products",
            "http_method": "GET",
            "timeout_seconds": 5,
        },
        secret_reference="secret:supplier/test",
        is_active=True,
    )
    payload = await HttpSourceAdapter(Client(), Secrets(), 1024).acquire(source)
    assert payload.content == b'[{"sku":"A-1"}]'
    assert requests[0]["url"] == "https://supplier.invalid/products"
    assert requests[0]["headers"] == {"Authorization": "Bearer hidden"}


@pytest.mark.asyncio
async def test_http_adapter_rejects_non_success_and_oversized_fake_responses() -> None:
    class Secrets:
        def resolve(self, reference: str) -> dict[str, str]:
            return {}

    class Client:
        def __init__(self, response: HttpResponse) -> None:
            self.response = response

        async def request(self, **kwargs: object) -> HttpResponse:
            return self.response

    source = SupplierSource(
        id=uuid.uuid4(),
        supplier_id=uuid.uuid4(),
        source_code="SRC-999998",
        name="Fake HTTP",
        source_type="HTTP",
        status="ACTIVE",
        configuration={"url": "https://supplier.invalid/file.json"},
        is_active=True,
    )
    with pytest.raises(AcquisitionFailure) as status_error:
        await HttpSourceAdapter(
            Client(HttpResponse(503, b"secret upstream details", "text/plain")),
            Secrets(),
            10,
        ).acquire(source)
    assert status_error.value.code == "acquisition_http_status"
    assert "secret upstream details" not in status_error.value.safe_message
    with pytest.raises(AcquisitionFailure) as size_error:
        await HttpSourceAdapter(
            Client(HttpResponse(200, b"x" * 11, "application/json")),
            Secrets(),
            10,
        ).acquire(source)
    assert size_error.value.code == "acquisition_artifact_too_large"
