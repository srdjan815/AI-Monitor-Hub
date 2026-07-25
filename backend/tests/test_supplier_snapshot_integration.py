from __future__ import annotations

import asyncio
import csv
import io
import uuid

import httpx
from sqlalchemy import delete, select
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
from app.modules.suppliers.snapshot_models import (
    SupplierSnapshot,
    SupplierSnapshotArchiveOperation,
    SupplierSnapshotItem,
)

API_ROOT = "http://localhost:8000/api/v1"


def _headers() -> dict[str, str]:
    token = create_access_token("snapshot-integration", ("system_admin",))
    return {"Authorization": f"Bearer {token}"}


async def _purge(supplier_id: str) -> None:
    identifier = uuid.UUID(supplier_id)
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        source_ids = list(
            await session.scalars(
                select(SupplierSource.id).where(
                    SupplierSource.supplier_id == identifier
                )
            )
        )
        run_ids = list(
            await session.scalars(
                select(SupplierAcquisitionRun.id).where(
                    SupplierAcquisitionRun.supplier_id == identifier
                )
            )
        )
        snapshot_ids = list(
            await session.scalars(
                select(SupplierSnapshot.id).where(
                    SupplierSnapshot.supplier_id == identifier
                )
            )
        )
        if snapshot_ids:
            await session.execute(
                delete(SupplierSnapshotArchiveOperation).where(
                    SupplierSnapshotArchiveOperation.snapshot_id.in_(snapshot_ids)
                )
            )
            await session.execute(
                delete(SupplierSnapshotItem).where(
                    SupplierSnapshotItem.snapshot_id.in_(snapshot_ids)
                )
            )
            await session.execute(
                delete(SupplierSnapshot).where(SupplierSnapshot.id.in_(snapshot_ids))
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
                select(SupplierSchemaProfile.id).where(
                    SupplierSchemaProfile.source_connection_id.in_(source_ids)
                )
            )
        )
        mapping_ids = list(
            await session.scalars(
                select(SupplierMappingProfile.id).where(
                    SupplierMappingProfile.schema_profile_id.in_(schema_ids)
                )
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


async def _ineligible_runs(run: dict[str, object]) -> list[str]:
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    identifiers: list[str] = []
    async with sessions() as session:
        for run_status in ("PENDING", "RUNNING", "FAILED", "CANCELLED"):
            entity = SupplierAcquisitionRun(
                supplier_id=uuid.UUID(str(run["supplier_id"])),
                source_connection_id=uuid.UUID(str(run["source_connection_id"])),
                schema_profile_id=uuid.UUID(str(run["schema_profile_id"])),
                mapping_profile_id=uuid.UUID(str(run["mapping_profile_id"])),
                schema_version_reference=int(run["schema_version_reference"]),
                mapping_version_reference=int(run["mapping_version_reference"]),
                trigger_type="MANUAL",
                status=run_status,
                source_type=str(run["source_type"]),
            )
            session.add(entity)
            await session.flush()
            identifiers.append(str(entity.id))
        await session.commit()
    await engine.dispose()
    return identifiers


def _pipeline(client: httpx.Client, suffix: str) -> tuple[str, str, str]:
    supplier_response = client.post(
        "/suppliers", json={"company_name": f"Snapshot Supplier {suffix}"}
    )
    assert supplier_response.status_code == 201, supplier_response.text
    supplier_id = supplier_response.json()["id"]
    sources = f"/suppliers/{supplier_id}/sources"
    source_response = client.post(
        sources,
        json={
            "name": f"Snapshot CSV {suffix}",
            "source_type": "MANUAL_UPLOAD",
            "configuration": {"accepted_file_types": ["CSV"]},
        },
    )
    assert source_response.status_code == 201, source_response.text
    source = source_response.json()
    validated = client.post(f"{sources}/{source['id']}/validate")
    activated_source = client.patch(
        f"{sources}/{source['id']}",
        json={"version": validated.json()["version"], "status": "ACTIVE"},
    )
    assert activated_source.status_code == 200, activated_source.text

    schemas = f"{sources}/{source['id']}/schema-profiles"
    schema = client.post(schemas, json={"name": f"Snapshot Schema {suffix}"}).json()
    codes = (
        "supplier_sku",
        "name",
        "description",
        "image_url",
        "primary_image_url",
        "additional_images",
    )
    fields: list[dict] = []
    for position, code in enumerate(codes, 1):
        response = client.post(
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
        assert response.status_code == 201, response.text
        fields.append(response.json())
    schema = client.get(f"{schemas}/{schema['id']}").json()
    active_schema = client.post(
        f"{schemas}/{schema['id']}/activate",
        json={"version": schema["version"]},
    )
    assert active_schema.status_code == 200, active_schema.text
    mappings = f"{schemas}/{schema['id']}/mapping-profiles"
    mapping = client.post(mappings, json={"name": f"Snapshot Mapping {suffix}"}).json()
    targets = (
        "product_code",
        "name",
        "description",
        "image_url",
        "primary_image_url",
        "additional_images",
    )
    for priority, (field, target) in enumerate(zip(fields, targets), 1):
        response = client.post(
            f"{mappings}/{mapping['id']}/rules",
            json={
                "schema_field_id": field["id"],
                "target_attribute": target,
                "transformation_type": "COPY",
                "priority": priority,
                "required": target == "product_code",
            },
        )
        assert response.status_code == 201, response.text
    mapping = client.get(f"{mappings}/{mapping['id']}").json()
    active_mapping = client.post(
        f"{mappings}/{mapping['id']}/activate",
        json={"optimistic_version": mapping["optimistic_version"]},
    )
    assert active_mapping.status_code == 200, active_mapping.text
    return supplier_id, source["id"], f"{sources}/{source['id']}"


def _csv_payload(long_description: str) -> bytes:
    rows = [
        [
            "A-1",
            "Prvi",
            "Opis 1",
            "https://img.test/a.jpg",
            "https://img.test/manual-photo.jpg",
            "https://img.test/a.jpg",
        ],
        ["A-2", "Drugi", long_description, "", "", "https://img.test/b.jpg"],
        ["A-3", "Treći", "Opis 3", "", "", ""],
    ]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(
        [
            "supplier_sku",
            "name",
            "description",
            "image_url",
            "primary_image_url",
            "additional_images",
        ]
    )
    writer.writerows(rows)
    return stream.getvalue().encode()


def test_snapshot_create_archive_offload_restore_pipeline() -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_id = ""
    with httpx.Client(base_url=API_ROOT, headers=_headers(), timeout=60) as client:
        try:
            supplier_id, source_id, source_root = _pipeline(client, suffix)
            product_total = client.get("/products").json()["total"]
            long_description = (
                "Višelinijski čćž opis\n<html><b>Fotografisan proizvod</b></html>\n"
                + ("dugačak dobavljački opis " * 4000)
            )
            acquisition = client.post(
                f"{source_root}/acquisitions/upload",
                params={"filename": "snapshot.csv"},
                headers={"Content-Type": "text/csv"},
                content=_csv_payload(long_description),
            )
            assert acquisition.status_code == 201, acquisition.text
            run = acquisition.json()
            assert run["status"] == "SUCCEEDED"
            snapshots = f"{source_root}/snapshots"
            for ineligible_id in asyncio.run(_ineligible_runs(run)):
                rejected = client.post(
                    snapshots,
                    json={"acquisition_run_id": ineligible_id},
                )
                assert rejected.status_code == 409
                assert rejected.json()["code"] == "snapshot_acquisition_ineligible"
            created = client.post(
                snapshots,
                json={"acquisition_run_id": run["id"]},
            )
            assert created.status_code == 201, created.text
            snapshot = created.json()
            assert snapshot["status"] == "READY"
            assert snapshot["storage_state"] == "ONLINE"
            assert snapshot["total_items"] == 3
            repeated = client.post(snapshots, json={"acquisition_run_id": run["id"]})
            assert repeated.status_code == 201
            assert repeated.json()["id"] == snapshot["id"]
            items = client.get(f"{snapshots}/{snapshot['id']}/items").json()
            assert items["total"] == 3
            details = [
                client.get(f"{snapshots}/{snapshot['id']}/items/{item['id']}").json()
                for item in items["items"]
            ]
            long_item = next(
                item for item in details if item["mapped_data"]["product_code"] == "A-2"
            )
            assert long_item["mapped_data"]["description"] == long_description
            first = next(
                item for item in details if item["mapped_data"]["product_code"] == "A-1"
            )
            assert [link["url"] for link in first["source_image_links"]] == [
                "https://img.test/a.jpg",
                "https://img.test/manual-photo.jpg",
            ]
            integrity = client.post(f"{snapshots}/{snapshot['id']}/verify")
            assert integrity.json() == {
                "snapshot_id": snapshot["id"],
                "valid": True,
                "code": "snapshot_integrity_ok",
            }
            operator_token = create_access_token(
                "snapshot-operator", ("snapshot_operator",)
            )
            with httpx.Client(
                base_url=API_ROOT,
                headers={"Authorization": f"Bearer {operator_token}"},
                timeout=60,
            ) as operator:
                exported = operator.post(
                    f"{snapshots}/{snapshot['id']}/archive",
                    json={"include_source_artifact": True},
                )
                assert exported.status_code == 201, exported.text
                operation = exported.json()
                assert operation["status"] == "VERIFIED"
                operation_read = operator.get(
                    f"{snapshots}/{snapshot['id']}/archives/{operation['id']}"
                )
                assert operation_read.status_code == 200
                assert (
                    operation_read.json()["archive_checksum"]
                    == operation["archive_checksum"]
                )
                forbidden_offload = operator.post(
                    f"{snapshots}/{snapshot['id']}/offload",
                    json={
                        "operation_id": operation["id"],
                        "archive_reference": operation["archive_reference"],
                        "archive_checksum": operation["archive_checksum"],
                    },
                )
                assert forbidden_offload.status_code == 403
            assert (
                client.get(f"{snapshots}/{snapshot['id']}/items").json()["total"] == 3
            )
            offloaded = client.post(
                f"{snapshots}/{snapshot['id']}/offload",
                json={
                    "operation_id": operation["id"],
                    "archive_reference": operation["archive_reference"],
                    "archive_checksum": operation["archive_checksum"],
                },
            )
            assert offloaded.status_code == 200, offloaded.text
            assert offloaded.json()["storage_state"] == "ARCHIVED"
            assert offloaded.json()["total_items"] == 3
            assert client.get(f"{snapshots}/{snapshot['id']}/items").status_code == 409
            stats = client.get(f"{snapshots}/{snapshot['id']}/statistics").json()
            assert stats["active_item_count"] == 0
            restored = client.post(f"{snapshots}/{snapshot['id']}/restore")
            assert restored.status_code == 200, restored.text
            assert restored.json()["id"] == snapshot["id"]
            assert (
                restored.json()["snapshot_fingerprint"]
                == snapshot["snapshot_fingerprint"]
            )
            restored_items = client.get(f"{snapshots}/{snapshot['id']}/items").json()
            assert restored_items["total"] == 3
            restored_long = client.get(
                f"{snapshots}/{snapshot['id']}/items/{long_item['id']}"
            ).json()
            assert restored_long["mapped_data"]["description"] == long_description
            held_run = client.post(
                f"{source_root}/acquisitions/upload",
                params={"filename": "held.csv"},
                headers={"Content-Type": "text/csv"},
                content=_csv_payload(long_description.replace("opis", "zapis", 1)),
            ).json()
            held_snapshot = client.post(
                snapshots,
                json={
                    "acquisition_run_id": held_run["id"],
                    "legal_hold": True,
                    "preserve_online": True,
                },
            ).json()
            preview = client.get(
                f"/suppliers/{supplier_id}/snapshots/archive-candidates",
                params={"source_id": source_id},
            ).json()
            held_candidate = next(
                item
                for item in preview["items"]
                if item["snapshot_id"] == held_snapshot["id"]
            )
            assert held_candidate["eligible"] is False
            assert "snapshot_legal_hold" in held_candidate["exclusion_reasons"]
            held_export = client.post(
                f"{snapshots}/{held_snapshot['id']}/archive",
                json={"include_source_artifact": False},
            ).json()
            bulk = client.post(
                f"{snapshots}/archive-bulk",
                json={
                    "snapshot_ids": [held_snapshot["id"], str(uuid.uuid4())],
                    "include_source_artifact": False,
                },
            )
            assert bulk.status_code == 200, bulk.text
            assert len(bulk.json()["succeeded"]) == 1
            assert len(bulk.json()["failed"]) == 1
            held_offload = client.post(
                f"{snapshots}/{held_snapshot['id']}/offload",
                json={
                    "operation_id": held_export["id"],
                    "archive_reference": held_export["archive_reference"],
                    "archive_checksum": held_export["archive_checksum"],
                    "override_preserve_online": True,
                },
            )
            assert held_offload.status_code == 409
            assert held_offload.json()["code"] == "snapshot_legal_hold"
            future_preview = client.get(
                f"/suppliers/{supplier_id}/snapshots/archive-candidates",
                params={"created_from": "2100-01-01T00:00:00Z"},
            ).json()
            assert future_preview["items"] == []
            assert client.get("/products").json()["total"] == product_total
        finally:
            if supplier_id:
                asyncio.run(_purge(supplier_id))
