from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.modules.suppliers.models import Supplier, SupplierSource
from app.modules.suppliers.retention_service import (
    RetentionConflict,
    SupplierRetentionService,
)
from app.modules.suppliers.retention_schemas import RetentionPolicyWrite


def _source(
    supplier_id: uuid.UUID, name: str, status: str, active: bool
) -> SupplierSource:
    return SupplierSource(
        supplier_id=supplier_id,
        name=name,
        source_type="API",
        status=status,
        is_active=active,
        configuration={},
    )


@pytest.mark.asyncio
async def test_retention_exposes_and_accepts_only_operational_sources() -> None:
    suffix = uuid.uuid4().hex
    async with AsyncSessionLocal() as session:
        supplier = Supplier(company_name=f"Retention active {suffix}")
        archived_supplier = Supplier(
            company_name=f"Retention archived {suffix}",
            status="INACTIVE",
            is_active=False,
        )
        session.add_all([supplier, archived_supplier])
        await session.flush()
        operational = _source(supplier.id, f"Operational {suffix}", "ACTIVE", True)
        archived = _source(supplier.id, f"Archived {suffix}", "INACTIVE", False)
        draft = _source(supplier.id, f"Draft {suffix}", "DRAFT", True)
        hidden_with_supplier = _source(
            archived_supplier.id, f"Hidden supplier {suffix}", "INACTIVE", True
        )
        session.add_all([operational, archived, draft, hidden_with_supplier])
        await session.commit()
        source_ids = [operational.id, archived.id, draft.id, hidden_with_supplier.id]
        supplier_ids = [supplier.id, archived_supplier.id]

        try:
            result = await SupplierRetentionService(session).policies()
            visible_ids = {item.source_connection_id for item in result.items}
            assert operational.id in visible_ids
            assert archived.id not in visible_ids
            assert draft.id not in visible_ids
            assert hidden_with_supplier.id not in visible_ids

            with pytest.raises(RetentionConflict, match="ne postoji"):
                await SupplierRetentionService(session).save_policy(
                    archived.id,
                    RetentionPolicyWrite(
                        enabled=False,
                        staging_retention_days=30,
                        snapshot_online_days=90,
                        minimum_online_snapshots=7,
                        cleanup_batch_size=1_000,
                        expected_version=None,
                    ),
                )
        finally:
            await session.rollback()
            await session.execute(
                delete(SupplierSource).where(SupplierSource.id.in_(source_ids))
            )
            await session.execute(delete(Supplier).where(Supplier.id.in_(supplier_ids)))
            await session.commit()
