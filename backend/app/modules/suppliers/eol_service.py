from __future__ import annotations

import calendar
import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_actor_id
from app.modules.suppliers.eol_models import EolExportBatch, EolExportItem
from app.modules.suppliers.eol_repository import SupplierEolRepository
from app.modules.suppliers.eol_schemas import (
    EolBatchCreate,
    EolBatchRead,
    EolCandidateList,
    EolCandidateRead,
    EolSupplierPresenceRead,
)
from app.modules.suppliers.errors import supplier_error


def months_before(value: datetime, months: int) -> datetime:
    year = value.year
    month = value.month - months
    while month <= 0:
        year -= 1
        month += 12
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


class SupplierEolService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierEolRepository(session)

    async def list_candidates(
        self,
        *,
        inactivity_months: int,
        supplier_id: uuid.UUID | None,
        search: str | None,
        limit: int,
        offset: int,
        now: datetime | None = None,
    ) -> EolCandidateList:
        current = now or datetime.now(UTC)
        cutoff = months_before(current, inactivity_months)
        rows, total = await self.repository.list_candidates(
            cutoff=cutoff,
            supplier_id=supplier_id,
            search=search,
            limit=limit,
            offset=offset,
        )
        return EolCandidateList(
            items=[self._candidate(row, current) for row in rows],
            total=total,
            inactivity_months=inactivity_months,
            cutoff_at=cutoff,
        )

    async def prepare_batch(self, payload: EolBatchCreate) -> EolBatchRead:
        existing = await self.repository.batch_by_key(payload.idempotency_key)
        if existing:
            return self._batch(existing, await self._item_count(existing.id))
        now = datetime.now(UTC)
        cutoff = months_before(now, payload.inactivity_months)
        rows, _ = await self.repository.list_candidates(
            cutoff=cutoff,
            supplier_id=None,
            search=None,
            limit=len(payload.identity_keys),
            offset=0,
            identity_keys=payload.identity_keys,
        )
        found = {str(row["identity_key"]): row for row in rows}
        if set(payload.identity_keys) != set(found):
            supplier_error(
                409,
                "eol_candidate_changed",
                "Izbor više nije važeći; osvežite EOL listu",
            )
        if any(not row.get("ean") for row in rows):
            supplier_error(
                409, "eol_ean_required", "Deaktivacija zahteva EAN za svaki artikal"
            )
        if any(
            row.get("export_item_status") in {"PENDING", "SUCCEEDED"}
            and row.get("export_batch_status")
            in {"PREPARED", "PROCESSING", "PARTIALLY_SUCCEEDED", "SUCCEEDED"}
            for row in rows
        ):
            supplier_error(
                409,
                "eol_deactivation_already_prepared",
                "Najmanje jedan artikal je već poslat u paket za deaktivaciju",
            )
        batch = EolExportBatch(
            id=uuid.uuid4(),
            status="PREPARED",
            inactivity_months=payload.inactivity_months,
            target_systems=payload.target_systems,
            idempotency_key=payload.idempotency_key,
            created_by=current_actor_id() or "system",
        )
        items = [
            EolExportItem(
                batch_id=batch.id,
                identity_key=str(row["identity_key"]),
                ean=str(row["ean"]),
                product_name=str(row["product_name"] or "") or None,
                last_seen_at=row["last_seen_at"],
                status="PENDING",
                target_results={},
            )
            for row in rows
        ]
        try:
            await self.repository.add_batch(batch, items)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.repository.batch_by_key(payload.idempotency_key)
            if existing:
                return self._batch(existing, await self._item_count(existing.id))
            supplier_error(
                409,
                "eol_deactivation_concurrent_conflict",
                "Drugi operater je već pripremio izabrani artikal",
            )
        await self.session.refresh(batch)
        return self._batch(batch, len(items))

    async def _item_count(self, batch_id: uuid.UUID) -> int:
        from sqlalchemy import func, select

        return int(
            await self.session.scalar(
                select(func.count(EolExportItem.id)).where(
                    EolExportItem.batch_id == batch_id
                )
            )
            or 0
        )

    @staticmethod
    def _candidate(row: dict[str, object], now: datetime) -> EolCandidateRead:
        last_seen = row["last_seen_at"]
        assert isinstance(last_seen, datetime)
        item_status = str(row.get("export_item_status") or "")
        batch_status = str(row.get("export_batch_status") or "")
        status: Literal["EOL_CANDIDATE", "MARKED_FOR_DEACTIVATION", "DEACTIVATED"] = (
            "EOL_CANDIDATE"
        )
        if item_status == "SUCCEEDED" or batch_status == "SUCCEEDED":
            status = "DEACTIVATED"
        elif item_status == "PENDING" and batch_status in {"PREPARED", "PROCESSING"}:
            status = "MARKED_FOR_DEACTIVATION"
        raw_suppliers = row.get("suppliers")
        suppliers = raw_suppliers if isinstance(raw_suppliers, list) else []
        return EolCandidateRead(
            identity_key=str(row["identity_key"]),
            ean=str(row["ean"]) if row.get("ean") else None,
            product_name=str(row["product_name"]) if row.get("product_name") else None,
            last_seen_at=last_seen,
            inactive_days=max(0, (now - last_seen).days),
            status=status,
            export_batch_code=(
                str(row["export_batch_code"]) if row.get("export_batch_code") else None
            ),
            export_eligible=bool(row.get("ean")) and status == "EOL_CANDIDATE",
            suppliers=[
                EolSupplierPresenceRead.model_validate(item) for item in suppliers
            ],
        )

    @staticmethod
    def _batch(batch: EolExportBatch, count: int) -> EolBatchRead:
        return EolBatchRead(
            id=batch.id,
            batch_code=batch.batch_code,
            status=batch.status,
            inactivity_months=batch.inactivity_months,
            target_systems=batch.target_systems,
            item_count=count,
            created_by=batch.created_by,
            created_at=batch.created_at,
        )


__all__ = ["SupplierEolService", "months_before"]
