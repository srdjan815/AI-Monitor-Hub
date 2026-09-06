from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.acquisition_models import (
    SupplierAcquisitionRun,
    SupplierStagedRecord,
)
from app.modules.suppliers.models import Supplier, SupplierSource
from app.modules.suppliers.pipeline_models import (
    SupplierSourceArtifact,
    SupplierSourcePipelineRun,
)
from app.modules.suppliers.price_list_archive_schemas import (
    ArchivedPriceListItem,
    ArchivedPriceListItemPage,
    PriceListArchiveEntry,
    PriceListArchiveFilter,
    PriceListArchiveFilters,
    PriceListArchivePage,
)
from app.modules.system.models import ArtifactArchiveTransfer

VISIBLE_RUN_STATUSES = ("SUCCEEDED", "PARTIALLY_SUCCEEDED")


def _text(value: object) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _first(data: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = _text(data.get(key))
        if value is not None:
            return value
    return None


def _storage_status(transfer_status: str | None) -> str:
    if transfer_status is None:
        return "LOCAL"
    return {
        "VERIFIED": "NAS_VERIFIED",
        "FAILED": "TRANSFER_FAILED",
        "PENDING": "TRANSFER_PENDING",
    }.get(transfer_status, "LOCAL")


class PriceListArchiveService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _base() -> Any:
        return (
            select(
                SupplierAcquisitionRun,
                Supplier.company_name,
                SupplierSource.name,
                SupplierSourceArtifact,
                ArtifactArchiveTransfer,
            )
            .join(Supplier, Supplier.id == SupplierAcquisitionRun.supplier_id)
            .join(
                SupplierSource,
                SupplierSource.id == SupplierAcquisitionRun.source_connection_id,
            )
            .outerjoin(
                SupplierSourcePipelineRun,
                SupplierSourcePipelineRun.acquisition_run_id
                == SupplierAcquisitionRun.id,
            )
            .outerjoin(
                SupplierSourceArtifact,
                SupplierSourceArtifact.id == SupplierSourcePipelineRun.artifact_id,
            )
            .outerjoin(
                ArtifactArchiveTransfer,
                ArtifactArchiveTransfer.artifact_id == SupplierSourceArtifact.id,
            )
            .where(SupplierAcquisitionRun.status.in_(VISIBLE_RUN_STATUSES))
        )

    async def filters(self) -> PriceListArchiveFilters:
        rows = (
            await self.session.execute(
                select(
                    Supplier.id,
                    Supplier.company_name,
                    SupplierSource.id,
                    SupplierSource.name,
                )
                .join(SupplierSource, SupplierSource.supplier_id == Supplier.id)
                .join(
                    SupplierAcquisitionRun,
                    SupplierAcquisitionRun.source_connection_id == SupplierSource.id,
                )
                .where(SupplierAcquisitionRun.status.in_(VISIBLE_RUN_STATUSES))
                .distinct()
                .order_by(Supplier.company_name, SupplierSource.name)
            )
        ).all()
        suppliers: dict[uuid.UUID, str] = {}
        sources: list[PriceListArchiveFilter] = []
        for supplier_id, supplier_name, source_id, source_name in rows:
            suppliers[supplier_id] = supplier_name
            sources.append(
                PriceListArchiveFilter(
                    id=source_id, name=source_name, supplier_id=supplier_id
                )
            )
        return PriceListArchiveFilters(
            suppliers=[
                PriceListArchiveFilter(id=item_id, name=name)
                for item_id, name in suppliers.items()
            ],
            sources=sources,
        )

    async def entries(
        self,
        *,
        supplier_id: uuid.UUID | None,
        source_id: uuid.UUID | None,
        date_from: datetime | None,
        date_to: datetime | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> PriceListArchivePage:
        filters = []
        if supplier_id:
            filters.append(SupplierAcquisitionRun.supplier_id == supplier_id)
        if source_id:
            filters.append(SupplierAcquisitionRun.source_connection_id == source_id)
        if date_from:
            filters.append(SupplierAcquisitionRun.created_at >= date_from)
        if date_to:
            filters.append(SupplierAcquisitionRun.created_at <= date_to)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    SupplierAcquisitionRun.acquisition_code.ilike(pattern),
                    SupplierAcquisitionRun.original_filename.ilike(pattern),
                )
            )
        base = self._base().where(*filters)
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(
                    select(SupplierAcquisitionRun.id)
                    .where(
                        SupplierAcquisitionRun.status.in_(VISIBLE_RUN_STATUSES),
                        *filters,
                    )
                    .subquery()
                )
            )
            or 0
        )
        rows = (
            await self.session.execute(
                base.order_by(
                    SupplierAcquisitionRun.created_at.desc(),
                    SupplierAcquisitionRun.id.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
        ).all()
        items = []
        for run, supplier_name, source_name, artifact, transfer in rows:
            storage_status = _storage_status(transfer.status if transfer else None)
            items.append(
                PriceListArchiveEntry(
                    acquisition_run_id=run.id,
                    acquisition_code=run.acquisition_code,
                    supplier_id=run.supplier_id,
                    supplier_name=supplier_name,
                    source_connection_id=run.source_connection_id,
                    source_name=source_name,
                    original_filename=run.original_filename,
                    imported_at=run.created_at,
                    completed_at=run.completed_at,
                    status=run.status,
                    total_records=run.total_record_count,
                    accepted_records=run.accepted_record_count,
                    rejected_records=run.rejected_record_count,
                    size_bytes=(
                        artifact.size_bytes if artifact else run.artifact_size_bytes
                    ),
                    checksum_sha256=(
                        artifact.checksum_sha256 if artifact else run.checksum
                    ),
                    artifact_code=artifact.artifact_code if artifact else None,
                    storage_status=storage_status,
                    archive_reference=(
                        transfer.archive_reference if transfer else None
                    ),
                )
            )
        return PriceListArchivePage(
            items=items, total=total, limit=limit, offset=offset
        )

    async def items(
        self,
        run_id: uuid.UUID,
        *,
        search: str | None,
        validation_status: str | None,
        limit: int,
        offset: int,
    ) -> ArchivedPriceListItemPage:
        exists = await self.session.scalar(
            select(SupplierAcquisitionRun.id).where(
                SupplierAcquisitionRun.id == run_id,
                SupplierAcquisitionRun.status.in_(VISIBLE_RUN_STATUSES),
            )
        )
        if exists is None:
            raise LookupError("Arhivirani cenovnik nije pronađen")
        filters = [SupplierStagedRecord.acquisition_run_id == run_id]
        if validation_status:
            filters.append(SupplierStagedRecord.validation_status == validation_status)
        if search:
            pattern = f"%{search.strip()}%"
            mapped = SupplierStagedRecord.mapped_data
            filters.append(
                or_(
                    SupplierStagedRecord.source_key.ilike(pattern),
                    SupplierStagedRecord.source_identifier.ilike(pattern),
                    mapped["product_code"].astext.ilike(pattern),
                    mapped["ean"].astext.ilike(pattern),
                    mapped["name"].astext.ilike(pattern),
                    mapped["product_name"].astext.ilike(pattern),
                )
            )
        total = int(
            await self.session.scalar(
                select(func.count(SupplierStagedRecord.id)).where(*filters)
            )
            or 0
        )
        records = (
            await self.session.scalars(
                select(SupplierStagedRecord)
                .where(*filters)
                .order_by(SupplierStagedRecord.record_number)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return ArchivedPriceListItemPage(
            acquisition_run_id=run_id,
            items=[self._item(record) for record in records],
            total=total,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def _item(record: SupplierStagedRecord) -> ArchivedPriceListItem:
        mapped = record.mapped_data
        return ArchivedPriceListItem(
            id=record.id,
            record_number=record.record_number,
            product_code=_first(mapped, "product_code", "supplier_code", "sku", "code")
            or _text(record.source_key),
            ean=_first(mapped, "ean", "barcode", "gtin"),
            name=_first(mapped, "name", "product_name", "title"),
            price=_first(mapped, "price_rsd", "price", "net_price"),
            currency=_first(mapped, "currency", "source_currency"),
            stock=_first(mapped, "stock", "quantity", "available_quantity"),
            category=_first(mapped, "category", "category_name"),
            validation_status=record.validation_status,
            warning_count=record.warning_count,
            error_count=record.error_count,
            raw_data=record.raw_data,
            mapped_data=mapped,
        )


__all__ = [
    "PriceListArchiveService",
    "VISIBLE_RUN_STATUSES",
    "_first",
    "_storage_status",
    "_text",
]
