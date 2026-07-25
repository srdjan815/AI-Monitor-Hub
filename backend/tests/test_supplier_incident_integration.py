from __future__ import annotations

import asyncio
import uuid

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.modules.suppliers.acquisition_models import SupplierAcquisitionRun
from app.modules.suppliers.delta_models import SupplierDeltaRun
from app.modules.suppliers.incident_models import (
    SupplierIncident, SupplierIncidentComment, SupplierIncidentEvent,
    SupplierIncidentLink, SupplierIncidentRule,
)
from app.modules.suppliers.snapshot_models import SupplierSnapshot
from tests.test_supplier_snapshot_integration import API_ROOT, _csv_payload, _headers, _pipeline, _purge


async def _facts(supplier_id: str, source_id: str, snapshots: list[str]) -> tuple[str, str, list[dict[str, object]]]:
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    signals: list[dict[str, object]] = [
        {"code": "HIGH_REMOVAL_RATIO", "ratio": 0.8},
        {"code": "LARGE_PRICE_INCREASE", "percentage": "80.0"},
        {"code": "CURRENCY_CHANGED", "previous": "EUR", "current": "RSD"},
        {"code": "IMAGE_SET_CHANGED"},
        {"code": "SCHEMA_VERSION_CHANGED"},
    ]
    async with sessions() as session:
        template = (await session.execute(select(SupplierAcquisitionRun).where(SupplierAcquisitionRun.supplier_id == uuid.UUID(supplier_id)).limit(1))).scalar_one()
        failed = SupplierAcquisitionRun(
            supplier_id=uuid.UUID(supplier_id), source_connection_id=uuid.UUID(source_id),
            schema_profile_id=template.schema_profile_id, mapping_profile_id=template.mapping_profile_id,
            schema_version_reference=template.schema_version_reference,
            mapping_version_reference=template.mapping_version_reference,
            trigger_type="MANUAL", status="FAILED", source_type=template.source_type,
            failure_code="SOURCE_AUTHENTICATION_FAILED",
            failure_message="Authorization: Bearer super-secret token=hidden",
        )
        session.add(failed)
        previous = await session.get(SupplierSnapshot, uuid.UUID(snapshots[0]))
        current = await session.get(SupplierSnapshot, uuid.UUID(snapshots[1]))
        assert previous and current and previous.snapshot_fingerprint and current.snapshot_fingerprint
        delta = SupplierDeltaRun(
            supplier_id=uuid.UUID(supplier_id), source_connection_id=uuid.UUID(source_id),
            previous_snapshot_id=previous.id, current_snapshot_id=current.id,
            previous_snapshot_fingerprint=previous.snapshot_fingerprint,
            current_snapshot_fingerprint=current.snapshot_fingerprint,
            previous_schema_profile_id=previous.schema_profile_id,
            current_schema_profile_id=current.schema_profile_id,
            previous_mapping_profile_id=previous.mapping_profile_id,
            current_mapping_profile_id=current.mapping_profile_id,
            status="SUCCEEDED", comparison_version=1, total_previous_items=3,
            total_current_items=1, removed_items=2, modified_items=1,
            price_increased_items=1, image_changed_items=1,
            anomaly_signals=signals, completed_at=current.finalized_at, created_by="incident-test",
        )
        session.add(delta)
        await session.commit()
        return str(failed.id), str(delta.id), signals


async def _cleanup(supplier_id: str) -> None:
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    identifier = uuid.UUID(supplier_id)
    async with sessions() as session:
        incident_ids = list(await session.scalars(select(SupplierIncident.id).where(SupplierIncident.supplier_id == identifier)))
        if incident_ids:
            await session.execute(delete(SupplierIncidentLink).where((SupplierIncidentLink.incident_id.in_(incident_ids)) | (SupplierIncidentLink.related_incident_id.in_(incident_ids))))
            await session.execute(delete(SupplierIncidentComment).where(SupplierIncidentComment.incident_id.in_(incident_ids)))
            await session.execute(delete(SupplierIncidentEvent).where(SupplierIncidentEvent.incident_id.in_(incident_ids)))
            await session.execute(delete(SupplierIncident).where(SupplierIncident.id.in_(incident_ids)))
        await session.execute(delete(SupplierIncidentRule).where(SupplierIncidentRule.supplier_id == identifier))
        await session.commit()
    await engine.dispose()
    await _purge(supplier_id)


def test_supplier_incident_operational_cycle() -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_id = ""
    with httpx.Client(base_url=API_ROOT, headers=_headers(), timeout=60) as client:
        try:
            supplier_id, source_id, root = _pipeline(client, suffix)
            snapshots: list[str] = []
            for index in range(2):
                run = client.post(f"{root}/acquisitions/upload", params={"filename": f"incident-{index}.csv"}, headers={"Content-Type": "text/csv"}, content=_csv_payload("dugačak opis " * 2000))
                snapshot = client.post(f"{root}/snapshots", json={"acquisition_run_id": run.json()["id"]})
                snapshots.append(snapshot.json()["id"])
            failed_id, delta_id, original_signals = asyncio.run(_facts(supplier_id, source_id, snapshots))
            products_before = client.get("/products").json()["total"]
            inventory_before = client.get("/inventory").json()["total"]
            rule = client.post("/supplier-incident-rules", json={
                "rule_code": f"IMAGE_{suffix.upper()}", "name": "Image anomaly",
                "source_domain": "DELTA", "incident_type": "IMAGE_SET_CHANGED",
                "signal_code": "IMAGE_SET_CHANGED", "resulting_severity": "MEDIUM",
                "default_priority": "P3", "threshold_configuration": {},
                "supplier_id": supplier_id, "source_connection_id": source_id,
            })
            assert rule.status_code == 201, rule.text
            acquisition = client.post(f"/supplier-incidents/sync/acquisition-runs/{failed_id}")
            assert acquisition.status_code == 200 and len(acquisition.json()) == 1
            assert "super-secret" not in str(acquisition.json())
            delta = client.post(f"/supplier-incidents/sync/delta-runs/{delta_id}")
            assert delta.status_code == 200, delta.text
            assert {row["incident_type"] for row in delta.json()} == {
                "HIGH_REMOVAL_RATIO", "LARGE_PRICE_INCREASE", "CURRENCY_CHANGED",
                "IMAGE_SET_CHANGED", "SCHEMA_VERSION_CHANGED",
            }
            repeated = client.post(f"/supplier-incidents/sync/delta-runs/{delta_id}")
            assert all(row["occurrence_count"] == 2 for row in repeated.json())
            removal = next(row for row in repeated.json() if row["incident_type"] == "HIGH_REMOVAL_RATIO")
            acknowledged = client.post(f"/supplier-incidents/{removal['id']}/acknowledge")
            assert acknowledged.json()["status"] == "ACKNOWLEDGED"
            assigned = client.post(f"/supplier-incidents/{removal['id']}/assign", json={"assigned_user_id": "operator-1"})
            assert assigned.json()["assigned_user_id"] == "operator-1"
            comment = client.post(f"/supplier-incidents/{removal['id']}/comments", json={"body": "<script>alert(1)</script> Provera"})
            assert "<script>" not in comment.json()["body"]
            assert client.post(f"/supplier-incidents/{removal['id']}/start").json()["status"] == "IN_PROGRESS"
            resolved = client.post(f"/supplier-incidents/{removal['id']}/resolve", json={"resolution_code": "DATA_CONFIRMED", "resolution_summary": "Provereno"})
            assert resolved.json()["status"] == "RESOLVED"
            recurrence = client.post(f"/supplier-incidents/sync/delta-runs/{delta_id}").json()
            reopened = next(row for row in recurrence if row["id"] == removal["id"])
            assert reopened["status"] == "OPEN" and reopened["occurrence_count"] == 3
            image = next(row for row in recurrence if row["incident_type"] == "IMAGE_SET_CHANGED")
            suppressed = client.post(f"/supplier-incidents/{image['id']}/suppress", json={"reason": "Prihvaćena buka"})
            assert suppressed.json()["status"] == "SUPPRESSED"
            suppressed_recurrence = client.post(f"/supplier-incidents/sync/delta-runs/{delta_id}").json()
            image_again = next(row for row in suppressed_recurrence if row["id"] == image["id"])
            assert image_again["status"] == "SUPPRESSED" and image_again["occurrence_count"] == 4
            events = client.get(f"/supplier-incidents/{removal['id']}/events").json()
            assert {event["event_type"] for event in events["items"]} >= {"CREATED", "OCCURRENCE", "ACKNOWLEDGED", "ASSIGNED", "COMMENT_ADDED", "INVESTIGATION_STARTED", "RESOLVED", "REOPENED"}
            manual = client.post("/supplier-incidents", json={
                "supplier_id": supplier_id, "source_connection_id": source_id,
                "incident_type": "MANUAL_DATA_QUALITY_REPORT", "severity": "MEDIUM",
                "priority": "P3", "title": "Ručna provera", "description": "Opis",
            })
            assert manual.status_code == 201
            assert client.get("/products").json()["total"] == products_before
            assert client.get("/inventory").json()["total"] == inventory_before
            assert client.get(f"{root}/deltas/{delta_id}").json()["anomaly_signals"] == original_signals
            assert all(client.get(f"{root}/snapshots/{snapshot_id}").json()["status"] == "READY" for snapshot_id in snapshots)
        finally:
            if supplier_id:
                asyncio.run(_cleanup(supplier_id))
