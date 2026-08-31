from __future__ import annotations

import io
import uuid
import zipfile
from unittest.mock import AsyncMock, Mock
from xml.sax.saxutils import escape

import pytest

from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
)
from app.modules.suppliers.schema_inference_engine import SchemaStructureDetector
from app.modules.suppliers.pipeline_models import SupplierSourceArtifact
from app.modules.suppliers.schema_inference_service import (
    SupplierSchemaInferenceService,
)
from app.modules.suppliers.schema_profile_schemas import SchemaProfileCreate
from app.modules.suppliers.schema_type_inference import SchemaFieldInferer


def _xlsx(rows: list[list[str]]) -> bytes:
    shared = [value for row in rows for value in row]
    sheet_rows: list[str] = []
    index = 0
    for row_number, row in enumerate(rows, 1):
        cells = []
        for column, _value in zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", row):
            cells.append(
                f'<c r="{column}{row_number}" t="s"><v>{index}</v></c>'
            )
            index += 1
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    strings = "".join(f"<si><t>{escape(value)}</t></si>" for value in shared)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f"{strings}</sst>"
            ),
        )
        archive.writestr(
            "xl/workbook.xml",
            (
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Cenovnik" sheetId="1" r:id="rId1"/></sheets>'
                "</workbook>"
            ),
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/></Relationships>'
            ),
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            (
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
            ),
        )
    return output.getvalue()


def test_detector_preserves_total_record_count_while_limiting_samples() -> None:
    rows = "\n".join(f"{index};Product {index}" for index in range(150))
    structure = SchemaStructureDetector.detect(
        AcquiredPayload(
            content=f"sku;name\n{rows}\n".encode(),
            content_type="text/csv",
            original_filename="large.csv",
            source_metadata={},
        )
    )
    assert structure.record_count == 150
    assert len(structure.rows) == 100


@pytest.mark.parametrize(
    ("content", "content_type", "filename", "expected_format", "headers"),
    [
        (
            b"izvestaj\nsifra;naziv;cena\n1;Monitor;199.99\n",
            "text/csv",
            "ds.csv",
            "CSV",
            ["sifra", "naziv", "cena"],
        ),
        (
            (
                b"<cenovnik><proizvod><sifra>1</sifra><naziv>Monitor</naziv>"
                b"<cena>199.99</cena></proizvod><proizvod><sifra>2</sifra>"
                b"<naziv>Mis</naziv><cena>20.50</cena></proizvod></cenovnik>"
            ),
            "application/xml",
            "ds.xml",
            "XML",
            ["sifra", "naziv", "cena"],
        ),
        (
            b'[{"sku":"1","name":"Monitor"},{"sku":"2","name":"Mis"}]',
            "application/json",
            "ds.json",
            "JSON",
            ["sku", "name"],
        ),
    ],
)
def test_detects_supplier_price_list_structure(
    content: bytes,
    content_type: str,
    filename: str,
    expected_format: str,
    headers: list[str],
) -> None:
    result = SchemaStructureDetector.detect(
        AcquiredPayload(content, content_type, filename, {})
    )

    assert result.detected_format == expected_format
    assert list(result.rows[0]) == headers


def test_detects_excel_header_and_rows() -> None:
    content = _xlsx(
        [
            ["DS Computers cenovnik", "", ""],
            ["Sifra", "Naziv", "Cena"],
            ["1", "Monitor", "199.99"],
        ]
    )

    result = SchemaStructureDetector.detect(
        AcquiredPayload(
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "ewe.xlsx",
            {},
        )
    )

    assert result.detected_format == "EXCEL"
    assert result.header_row == 2
    assert result.rows == [{"Sifra": "1", "Naziv": "Monitor", "Cena": "199.99"}]


def test_infers_field_types_nullability_samples_and_count() -> None:
    rows = [
        {
            "sku": "100",
            "price": "199.99",
            "available": "da",
            "created": "2026-07-28",
            "updated": "2026-07-28T12:30:00",
            "name": "Monitor",
            "optional": "",
        },
        {
            "sku": "101",
            "price": "20.50",
            "available": "ne",
            "created": "2026-07-29",
            "updated": "2026-07-29T09:00:00",
            "name": "Mis",
            "optional": "akcija",
        },
    ]

    fields = SchemaFieldInferer.fields(
        uuid.uuid4(),
        rows,
    )
    by_name = {item.entity.name: item for item in fields}

    assert len(fields) == len(rows[0])
    assert by_name["sku"].entity.data_type == "INTEGER"
    assert by_name["price"].entity.data_type == "DECIMAL"
    assert by_name["available"].entity.data_type == "BOOLEAN"
    assert by_name["created"].entity.data_type == "DATE"
    assert by_name["updated"].entity.data_type == "DATETIME"
    assert by_name["name"].entity.data_type == "STRING"
    assert by_name["optional"].entity.nullable is True
    assert by_name["name"].sample_values == ["Monitor", "Mis"]
    assert by_name["price"].confidence == 1.0


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"<html><body>Login</body></html>",
        b"<cenovnik/>",
    ],
)
def test_failed_detection_never_returns_an_empty_schema(content: bytes) -> None:
    with pytest.raises(AcquisitionFailure):
        SchemaStructureDetector.detect(
            AcquiredPayload(content, "application/octet-stream", "test.dat", {})
        )


@pytest.mark.asyncio
async def test_failed_artifact_analysis_creates_no_empty_profile() -> None:
    session = Mock()
    session.commit = AsyncMock()
    service = SupplierSchemaInferenceService(session)
    artifact = SupplierSourceArtifact(
        source_connection_id=uuid.uuid4(),
        storage_reference="invalid.xml",
        original_filename="invalid.xml",
        content_type="application/xml",
        detected_format="XML",
        size_bytes=11,
        checksum_sha256="0" * 64,
        source_metadata={},
        retention_status="ONLINE",
    )
    service.repository.add = AsyncMock()

    with pytest.raises(AcquisitionFailure):
        await service.create_from_artifact(
            uuid.uuid4(),
            artifact,
            AcquiredPayload(b"<cenovnik/>", "application/xml", "invalid.xml", {}),
            SchemaProfileCreate(name="Neuspešna analiza"),
        )

    service.repository.add.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_ds_business_limits_override_sample_lengths() -> None:
    inferred = SchemaFieldInferer.fields(
        uuid.uuid4(),
        [
            {
                "proizvodjac": "Pluginn",
                "grupa": "KABLOVI",
                "nadgrupa": "OPREMA",
                "naziv": "Kratak naziv",
                "opis": "<p>Kratak opis</p>",
                "cena": "12594.30",
                "mpcena": "16314.48",
                "barkod": "0012345678905",
                "sifra": "43174",
            }
        ],
    )
    fields = {item.entity.name: item.entity for item in inferred}

    assert fields["proizvodjac"].max_length == 25
    assert fields["grupa"].max_length == 45
    assert fields["nadgrupa"].max_length == 45
    assert fields["naziv"].max_length == 255
    assert fields["opis"].max_length == 150_000
    assert fields["cena"].data_type == "DECIMAL"
    assert fields["cena"].precision == 38
    assert fields["cena"].scale == 2
    assert fields["mpcena"].data_type == "DECIMAL"
    assert fields["barkod"].data_type == "STRING"
    assert fields["barkod"].example_value == "0012345678905"
    assert fields["sifra"].required is True
def test_epi_business_string_limits_are_not_derived_from_short_sample() -> None:
    inferred = SchemaFieldInferer.fields(
        uuid.uuid4(),
        [
            {
                "ARTIKAL": "Kratak naziv",
                "PODKATEGORIJA": "Adapter",
            }
        ],
    )
    limits = {item.entity.name: item.entity.max_length for item in inferred}

    assert limits["ARTIKAL"] == 255
    assert limits["PODKATEGORIJA"] == 50


def test_global_product_identity_and_price_inference_policy() -> None:
    inferred = SchemaFieldInferer.fields(
        uuid.uuid4(),
        [
            {
                "CODE": "VERY-LONG-SUPPLIER-PART-NUMBER-001",
                "NAME": "Kratak naziv",
                "MANUFACTURER": "Proizvođač",
                "PRICE": "12345678901234567890.125",
                "BARCODE": "0012345678905",
            }
        ],
    )
    fields = {item.entity.name: item.entity for item in inferred}

    assert fields["CODE"].data_type == "STRING"
    assert fields["CODE"].max_length == 255
    assert fields["NAME"].max_length == 255
    assert fields["MANUFACTURER"].max_length == 25
    assert fields["PRICE"].data_type == "DECIMAL"
    assert fields["PRICE"].precision == 38
    assert fields["PRICE"].scale == 2
    assert fields["BARCODE"].data_type == "STRING"
    assert fields["BARCODE"].max_length == 64
    assert fields["BARCODE"].example_value == "0012345678905"


def test_item_group_uses_category_business_limit() -> None:
    inferred = SchemaFieldInferer.fields(
        uuid.uuid4(),
        [{"ITEM_GROUP": "Maticne ploce"}],
    )

    field = inferred[0].entity
    assert field.data_type == "STRING"
    assert field.max_length == 45


def test_multiple_supplier_prices_remain_decimal_with_one_primary_price() -> None:
    inferred = SchemaFieldInferer.fields(
        uuid.uuid4(),
        [
            {
                "PRICE": "100.00",
                "PRICE_WITH_DISCOUNTS": "90.00",
                "RETAIL_PRICE": "120.00",
            }
        ],
    )
    fields = {item.entity.name: item.entity for item in inferred}

    assert all(field.data_type == "DECIMAL" for field in fields.values())
    assert [name for name, field in fields.items() if field.is_price] == [
        "PRICE_WITH_DISCOUNTS"
    ]
