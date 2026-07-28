from __future__ import annotations

import asyncio
import csv
import io
import uuid

import httpx
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.modules.suppliers.acquisition_models import (
    SupplierAcquisitionIssue,
    SupplierAcquisitionRun,
    SupplierStagedRecord,
)
from app.modules.suppliers.mapping_profile_models import (
    SupplierMappingProfile,
    SupplierMappingRule,
)
from app.modules.suppliers.models import Supplier, SupplierSource
from app.modules.suppliers.schema_profile_models import (
    SupplierSchemaField,
    SupplierSchemaProfile,
)

API_ROOT = "http://localhost:8000/api/v1"


def _headers() -> dict[str, str]:
    token = create_access_token("acquisition-integration", ("system_admin",))
    return {"Authorization": f"Bearer {token}"}


async def _purge(supplier_id: str) -> None:
    identifier = uuid.UUID(supplier_id)
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        source_ids = list(
            await session.scalars(
                SupplierSource.__table__.select()
                .with_only_columns(SupplierSource.id)
                .where(SupplierSource.supplier_id == identifier)
            )
        )
        run_ids = list(
            await session.scalars(
                SupplierAcquisitionRun.__table__.select()
                .with_only_columns(SupplierAcquisitionRun.id)
                .where(SupplierAcquisitionRun.supplier_id == identifier)
            )
        )
        if run_ids:
            await session.execute(
                delete(SupplierAcquisitionIssue).where(
                    SupplierAcquisitionIssue.acquisition_run_id.in_(run_ids)
                )
            )
            await session.execute(
                delete(SupplierStagedRecord).where(
                    SupplierStagedRecord.acquisition_run_id.in_(run_ids)
                )
            )
            await session.execute(
                delete(SupplierAcquisitionRun).where(
                    SupplierAcquisitionRun.id.in_(run_ids)
                )
            )
        schema_ids = list(
            await session.scalars(
                SupplierSchemaProfile.__table__.select()
                .with_only_columns(SupplierSchemaProfile.id)
                .where(SupplierSchemaProfile.source_connection_id.in_(source_ids))
            )
        )
        mapping_ids = list(
            await session.scalars(
                SupplierMappingProfile.__table__.select()
                .with_only_columns(SupplierMappingProfile.id)
                .where(SupplierMappingProfile.schema_profile_id.in_(schema_ids))
            )
        )
        if mapping_ids:
            await session.execute(
                delete(SupplierMappingRule).where(
                    SupplierMappingRule.mapping_profile_id.in_(mapping_ids)
                )
            )
            await session.execute(
                delete(SupplierMappingProfile).where(
                    SupplierMappingProfile.id.in_(mapping_ids)
                )
            )
        if schema_ids:
            await session.execute(
                delete(SupplierSchemaField).where(
                    SupplierSchemaField.schema_profile_id.in_(schema_ids)
                )
            )
            await session.execute(
                delete(SupplierSchemaProfile).where(
                    SupplierSchemaProfile.id.in_(schema_ids)
                )
            )
        await session.execute(
            delete(SupplierSource).where(SupplierSource.supplier_id == identifier)
        )
        await session.execute(delete(Supplier).where(Supplier.id == identifier))
        await session.commit()
    await engine.dispose()


def _pipeline(client: httpx.Client, suffix: str) -> tuple[str, str, str]:
    supplier_response = client.post(
        "/suppliers", json={"company_name": f"Demo Distribution Serbia {suffix}"}
    )
    assert supplier_response.status_code == 201, supplier_response.text
    supplier_id = supplier_response.json()["id"]
    sources = f"/suppliers/{supplier_id}/sources"
    source_response = client.post(
        sources,
        json={
            "name": f"Manual CSV price list {suffix}",
            "source_type": "MANUAL_UPLOAD",
            "configuration": {"accepted_file_types": ["CSV"]},
        },
    )
    assert source_response.status_code == 201, source_response.text
    source = source_response.json()
    probe = client.post(
        f"{sources}/{source['id']}/probe-upload",
        params={"filename": "acquisition.csv"},
        content=b"supplier_sku,name\nSKU-1,Monitor\n",
        headers={"Content-Type": "text/csv"},
    )
    assert probe.status_code == 200, probe.text
    assert probe.json()["successful"] is True
    source = client.get(f"{sources}/{source['id']}").json()
    activated_source = client.patch(
        f"{sources}/{source['id']}",
        json={"version": source["version"], "status": "ACTIVE"},
    )
    assert activated_source.status_code == 200, activated_source.text

    schemas = f"{sources}/{source['id']}/schema-profiles"
    schema_response = client.post(schemas, json={"name": f"Schema {suffix}"})
    assert schema_response.status_code == 201, schema_response.text
    schema = schema_response.json()
    fields: list[dict] = []
    codes = (
        "supplier_sku",
        "ean",
        "name",
        "description",
        "price",
        "currency",
        "stock",
    )
    for position, code in enumerate(codes, 1):
        field_response = client.post(
            f"{schemas}/{schema['id']}/fields",
            json={
                "field_code": code,
                "name": code,
                "position": position,
                "data_type": "STRING",
                "required": code == "supplier_sku",
                "nullable": code != "supplier_sku",
                "path": code,
            },
        )
        assert field_response.status_code == 201, field_response.text
        fields.append(field_response.json())
    schema = client.get(f"{schemas}/{schema['id']}").json()
    activated_schema = client.post(
        f"{schemas}/{schema['id']}/activate",
        json={"version": schema["version"]},
    )
    assert activated_schema.status_code == 200, activated_schema.text

    mappings = f"{schemas}/{schema['id']}/mapping-profiles"
    mapping_response = client.post(mappings, json={"name": f"Mapping {suffix}"})
    assert mapping_response.status_code == 201, mapping_response.text
    mapping = mapping_response.json()
    targets = (
        "product_code",
        "ean",
        "name",
        "description",
        "price",
        "currency",
        "stock",
    )
    for priority, (field, target) in enumerate(zip(fields, targets), 1):
        rule_response = client.post(
            f"{mappings}/{mapping['id']}/rules",
            json={
                "schema_field_id": field["id"],
                "target_attribute": target,
                "transformation_type": "COPY",
                "priority": priority,
                "required": target == "product_code",
            },
        )
        assert rule_response.status_code == 201, rule_response.text
    mapping = client.get(f"{mappings}/{mapping['id']}").json()
    activated_mapping = client.post(
        f"{mappings}/{mapping['id']}/activate",
        json={"optimistic_version": mapping["optimistic_version"]},
    )
    assert activated_mapping.status_code == 200, activated_mapping.text
    return supplier_id, source["id"], f"{sources}/{source['id']}/acquisitions"


def test_frozen_supplier_pipeline_partial_success_and_idempotency() -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_id = ""
    with httpx.Client(base_url=API_ROOT, headers=_headers(), timeout=30) as client:
        try:
            supplier_id, _source_id, acquisitions = _pipeline(client, suffix)
            long_description = (
                "Višelinijski opis\n<html><b>Tehnički detalji</b></html>\n"
                + ("dobavljački proizvod " * 3500)
            )
            rows = [
                ["A-1", "860000000001", "Prvi", "Opis 1", "10.00", "RSD", "4"],
                ["A-2", "860000000002", "Drugi", long_description, "20", "EUR", "2"],
                ["A-3", "860000000003", "Treći", "Opis 3", "30", "RSD", "0"],
                ["", "860000000004", "Nevažeći", "Opis 4", "40", "RSD", "1"],
            ]
            header = "supplier_sku,ean,name,description,price,currency,stock\n"
            stream = io.StringIO(newline="")
            writer = csv.writer(stream)
            writer.writerow(header.strip().split(","))
            writer.writerows(rows)
            content = stream.getvalue().encode()
            created = client.post(
                f"{acquisitions}/upload",
                params={"filename": "cenovnik.csv"},
                headers={
                    "Idempotency-Key": f"idem-{suffix}",
                    "Content-Type": "text/csv",
                },
                content=content,
            )
            assert created.status_code == 201, created.text
            run = created.json()
            assert run["status"] == "PARTIALLY_SUCCEEDED"
            assert (run["total_record_count"], run["accepted_record_count"]) == (4, 3)
            assert run["rejected_record_count"] == 1
            assert run["error_count"] == 2
            assert run["checksum"]
            repeated = client.post(
                f"{acquisitions}/upload",
                params={"filename": "cenovnik.csv"},
                headers={
                    "Idempotency-Key": f"idem-{suffix}",
                    "Content-Type": "text/csv",
                },
                content=content,
            )
            assert repeated.status_code == 201
            assert repeated.json()["id"] == run["id"]
            conflict = client.post(
                f"{acquisitions}/upload",
                params={"filename": "cenovnik.csv"},
                headers={
                    "Idempotency-Key": f"idem-{suffix}",
                    "Content-Type": "text/csv",
                },
                content=content + b"\n",
            )
            assert conflict.status_code == 409
            records = client.get(
                f"{acquisitions}/{run['id']}/records", params={"limit": 2}
            ).json()
            assert records["total"] == 4
            assert "raw_data" not in records["items"][0]
            accepted = client.get(
                f"{acquisitions}/{run['id']}/records",
                params={"status": "ACCEPTED", "limit": 10},
            ).json()
            details = [
                client.get(f"{acquisitions}/{run['id']}/records/{item['id']}").json()
                for item in accepted["items"]
            ]
            long_row = next(
                row for row in details if row["raw_data"]["supplier_sku"] == "A-2"
            )
            assert long_row["raw_data"]["description"] == long_description
            assert long_row["mapped_data"]["description"] == long_description
            stats = client.get(f"{acquisitions}/{run['id']}/statistics").json()
            assert stats["accepted_record_count"] == 3
            issues = client.get(f"{acquisitions}/{run['id']}/issues").json()
            assert issues["total"] == 2
            assert long_description not in str(issues)
            retry = client.post(
                f"{acquisitions}/{run['id']}/retry",
                json={"idempotency_key": f"retry-{suffix}"},
            )
            assert retry.status_code == 201, retry.text
            assert retry.json()["id"] != run["id"]
            terminal_cancel = client.post(f"{acquisitions}/{run['id']}/cancel")
            assert terminal_cancel.status_code == 409
        finally:
            if supplier_id:
                asyncio.run(_purge(supplier_id))
