from __future__ import annotations

import asyncio
import uuid

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.modules.suppliers.retention_models import (
    SupplierDataRetentionPolicy,
    SupplierRetentionRun,
)
from tests.test_supplier_snapshot_integration import (
    API_ROOT,
    _headers,
    _pipeline,
    _purge,
)


async def _purge_retention(source_id: str) -> None:
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        policy = await session.scalar(
            select(SupplierDataRetentionPolicy).where(
                SupplierDataRetentionPolicy.source_connection_id == uuid.UUID(source_id)
            )
        )
        if policy is not None:
            policy_id = policy.id
            await session.execute(
                delete(SupplierRetentionRun).where(
                    SupplierRetentionRun.policy_id == policy_id
                )
            )
            await session.execute(
                delete(SupplierDataRetentionPolicy).where(
                    SupplierDataRetentionPolicy.id == policy_id
                )
            )
            await session.commit()
    await engine.dispose()


def test_retention_policy_preview_is_read_only_and_audited() -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_id = ""
    source_id = ""
    with httpx.Client(base_url=API_ROOT, headers=_headers(), timeout=60) as client:
        try:
            supplier_id, source_id, _ = _pipeline(client, suffix)
            policies = client.get("/system/resources/data-retention/policies")
            assert policies.status_code == 200, policies.text
            source = next(
                item
                for item in policies.json()["items"]
                if item["source_connection_id"] == source_id
            )
            assert source["configured"] is False
            missing_policy = client.post(
                f"/system/resources/data-retention/policies/{source_id}/preview"
            )
            assert missing_policy.status_code == 409
            unknown_source = client.put(
                f"/system/resources/data-retention/policies/{uuid.uuid4()}",
                json={
                    "enabled": False,
                    "staging_retention_days": 30,
                    "snapshot_online_days": 90,
                    "minimum_online_snapshots": 7,
                    "cleanup_batch_size": 1000,
                    "expected_version": None,
                },
            )
            assert unknown_source.status_code == 409
            saved = client.put(
                f"/system/resources/data-retention/policies/{source_id}",
                json={
                    "enabled": False,
                    "staging_retention_days": 30,
                    "snapshot_online_days": 90,
                    "minimum_online_snapshots": 7,
                    "cleanup_batch_size": 1000,
                    "expected_version": None,
                },
            )
            assert saved.status_code == 200, saved.text
            stale = client.put(
                f"/system/resources/data-retention/policies/{source_id}",
                json={
                    "enabled": True,
                    "staging_retention_days": 45,
                    "snapshot_online_days": 120,
                    "minimum_online_snapshots": 10,
                    "cleanup_batch_size": 500,
                    "expected_version": saved.json()["version"] + 1,
                },
            )
            assert stale.status_code == 409
            updated = client.put(
                f"/system/resources/data-retention/policies/{source_id}",
                json={
                    "enabled": False,
                    "staging_retention_days": 45,
                    "snapshot_online_days": 120,
                    "minimum_online_snapshots": 10,
                    "cleanup_batch_size": 500,
                    "expected_version": saved.json()["version"],
                },
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["version"] == saved.json()["version"] + 1
            preview = client.post(
                f"/system/resources/data-retention/policies/{source_id}/preview"
            )
            assert preview.status_code == 200, preview.text
            body = preview.json()
            assert body["execution_allowed"] is False
            assert "Politika nije uključena" in body["blockers"]
            assert body["candidate_staging_rows"] == 0
            runs = client.get("/system/resources/data-retention/runs")
            assert runs.status_code == 200, runs.text
            assert any(item["id"] == body["run_id"] for item in runs.json())
        finally:
            if source_id:
                asyncio.run(_purge_retention(source_id))
            if supplier_id:
                asyncio.run(_purge(supplier_id))
