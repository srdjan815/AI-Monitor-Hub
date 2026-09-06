from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.modules.suppliers.eol_models import (
    EolExportBatch,
    EolExportItem,
    SupplierProductPresence,
)
from tests.test_supplier_snapshot_integration import (
    API_ROOT,
    _csv_payload,
    _headers,
    _pipeline,
    _purge,
)


async def _make_one_product_inactive(source_id: str) -> str:
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        presence = await session.scalar(
            select(SupplierProductPresence)
            .where(SupplierProductPresence.source_connection_id == uuid.UUID(source_id))
            .order_by(SupplierProductPresence.product_code_normalized)
            .limit(1)
        )
        assert presence is not None
        assert presence.ean is not None
        presence.is_currently_offered = False
        presence.last_seen_at = datetime.now(UTC) - timedelta(days=220)
        identity_key = presence.identity_key
        await session.commit()
    await engine.dispose()
    return identity_key


async def _purge_batches(identity_key: str) -> None:
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        batch_ids = list(
            await session.scalars(
                select(EolExportItem.batch_id).where(
                    EolExportItem.identity_key == identity_key
                )
            )
        )
        if batch_ids:
            await session.execute(
                delete(EolExportItem).where(EolExportItem.batch_id.in_(batch_ids))
            )
            await session.execute(
                delete(EolExportBatch).where(EolExportBatch.id.in_(batch_ids))
            )
            await session.commit()
    await engine.dispose()


def test_eol_candidate_and_idempotent_deactivation_package() -> None:
    suffix = uuid.uuid4().hex[:12]
    supplier_id = ""
    identity_key = ""
    with httpx.Client(base_url=API_ROOT, headers=_headers(), timeout=60) as client:
        try:
            supplier_id, source_id, root = _pipeline(client, suffix)
            run = client.post(
                f"{root}/acquisitions/upload",
                params={"filename": "eol.csv"},
                headers={"Content-Type": "text/csv"},
                content=_csv_payload("EOL integration"),
            )
            assert run.status_code == 201, run.text
            snapshot = client.post(
                f"{root}/snapshots", json={"acquisition_run_id": run.json()["id"]}
            )
            assert snapshot.status_code == 201, snapshot.text

            identity_key = asyncio.run(_make_one_product_inactive(source_id))
            candidates = client.get(
                "/suppliers/platform/eol-products",
                params={"inactivity_months": 6, "supplier_id": supplier_id},
            )
            assert candidates.status_code == 200, candidates.text
            body = candidates.json()
            assert body["total"] == 1
            assert body["items"][0]["identity_key"] == identity_key
            assert body["items"][0]["status"] == "EOL_CANDIDATE"
            assert body["items"][0]["export_eligible"] is True

            payload = {
                "identity_keys": [identity_key],
                "inactivity_months": 6,
                "target_systems": ["WEBSITE", "PANTHEON"],
                "idempotency_key": f"eol-integration-{suffix}",
            }
            prepared = client.post(
                "/suppliers/platform/eol-products/deactivation-batches", json=payload
            )
            assert prepared.status_code == 201, prepared.text
            assert prepared.json()["status"] == "PREPARED"
            assert prepared.json()["item_count"] == 1
            repeated = client.post(
                "/suppliers/platform/eol-products/deactivation-batches", json=payload
            )
            assert repeated.status_code == 201, repeated.text
            assert repeated.json()["id"] == prepared.json()["id"]

            marked = client.get(
                "/suppliers/platform/eol-products",
                params={"inactivity_months": 6, "supplier_id": supplier_id},
            ).json()["items"][0]
            assert marked["status"] == "MARKED_FOR_DEACTIVATION"
            assert marked["export_eligible"] is False
            assert marked["export_batch_code"] == prepared.json()["batch_code"]
        finally:
            if identity_key:
                asyncio.run(_purge_batches(identity_key))
            if supplier_id:
                asyncio.run(_purge(supplier_id))
