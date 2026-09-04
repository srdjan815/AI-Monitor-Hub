from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import current_actor_id
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.currency_conversion import convert_supplier_price
from app.modules.suppliers.currency_service import SupplierCurrencyService
from app.modules.suppliers.currency_snapshot_policy import build_snapshot_currency_plan
from app.modules.suppliers.snapshot_fingerprints import (
    item_fingerprint,
    payload_checksum,
    snapshot_fingerprint,
)
from app.modules.suppliers.snapshot_images import extract_image_links
from app.modules.suppliers.snapshot_models import (
    SupplierSnapshot,
    SupplierSnapshotItem,
)
from app.modules.suppliers.snapshot_repository import SupplierSnapshotRepository


class SupplierSnapshotService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierSnapshotRepository(session)

    async def create(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        acquisition_run_id: uuid.UUID,
        *,
        retention_class: str,
        archive_after_days: int | None,
        preserve_online: bool,
        legal_hold: bool,
        archive_notes: str | None,
        pipeline_run_id: uuid.UUID | None = None,
    ) -> SupplierSnapshot:
        run = await self.repository.acquisition_for_update(
            supplier_id, source_id, acquisition_run_id
        )
        if run is None:
            supplier_error(
                404,
                "acquisition_run_not_found",
                "Acquisition Run nije pronađen",
            )
        existing = await self.repository.by_acquisition(acquisition_run_id)
        if existing is not None:
            return existing
        if run.status not in {"SUCCEEDED", "PARTIALLY_SUCCEEDED"}:
            supplier_error(
                409,
                "snapshot_acquisition_ineligible",
                "Snapshot zahteva uspešan ili delimično uspešan Acquisition Run",
            )
        latest = await self.repository.latest_acquisition(supplier_id, source_id)
        if latest is None or latest.id != run.id:
            supplier_error(
                409,
                "snapshot_acquisition_not_latest",
                "Snapshot se može kreirati samo iz poslednjeg importa",
            )
        records = await self.repository.accepted_records(run.id)
        if len(records) != run.accepted_record_count or not records:
            supplier_error(
                409,
                "snapshot_acquisition_count_mismatch",
                "Broj prihvaćenih staged zapisa nije usklađen",
            )
        now = datetime.now(UTC)
        currency_service = SupplierCurrencyService(self.session)
        currency_plan = await build_snapshot_currency_plan(
            currency_service, run.supplier_id, records, run.completed_at or now
        )
        snapshot = SupplierSnapshot(
            supplier_id=run.supplier_id,
            source_connection_id=run.source_connection_id,
            acquisition_run_id=run.id,
            pipeline_run_id=pipeline_run_id,
            schema_profile_id=run.schema_profile_id,
            mapping_profile_id=run.mapping_profile_id,
            schema_version_reference=run.schema_version_reference,
            mapping_version_reference=run.mapping_version_reference,
            currency_setting_id=currency_plan.setting.id if currency_plan else None,
            exchange_rate_id=currency_plan.rate.id if currency_plan else None,
            source_currency=currency_plan.currency_code if currency_plan else None,
            exchange_rate_to_rsd=(
                currency_plan.rate.rate_to_rsd if currency_plan else None
            ),
            status="BUILDING",
            storage_state="ONLINE",
            total_items=0,
            source_artifact_checksum=run.checksum,
            created_from_acquisition_at=run.completed_at,
            created_by=current_actor_id() or "system",
            retention_class=retention_class,
            archive_after_days=archive_after_days,
            preserve_online=preserve_online,
            legal_hold=legal_hold,
            archive_notes=archive_notes,
        )
        try:
            await self.repository.add_snapshot(snapshot)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.repository.by_acquisition(acquisition_run_id)
            if existing is not None:
                return existing
            raise
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(snapshot)
        try:
            pending_items: list[SupplierSnapshotItem] = []
            payloads: list[dict[str, object]] = []
            fingerprints: list[str] = []
            for record in records:
                mapped_data = convert_supplier_price(record.mapped_data, currency_plan)
                links = extract_image_links(mapped_data)
                fingerprint = item_fingerprint(
                    mapped_data,
                    links,
                    record.source_key,
                    record.source_identifier,
                )
                fingerprints.append(fingerprint)
                payloads.append(
                    {
                        "record_number": record.record_number,
                        "item_fingerprint": fingerprint,
                        "mapped_data": mapped_data,
                        "source_image_links": links,
                    }
                )
                pending_items.append(
                    SupplierSnapshotItem(
                        snapshot_id=snapshot.id,
                        source_staged_record_id=record.id,
                        record_number=record.record_number,
                        source_key=record.source_key,
                        source_identifier=record.source_identifier,
                        item_fingerprint=fingerprint,
                        mapped_data=mapped_data,
                        source_image_links=links,
                    )
                )
                if len(pending_items) >= settings.snapshot_batch_size:
                    await self.repository.add_items(pending_items)
                    pending_items = []
            if pending_items:
                await self.repository.add_items(pending_items)
            complete_fingerprint = snapshot_fingerprint(
                item_fingerprints=fingerprints,
                supplier_id=run.supplier_id,
                source_id=run.source_connection_id,
                acquisition_run_id=run.id,
                schema_version=run.schema_version_reference,
                mapping_version=run.mapping_version_reference,
            )
            await self.repository.mutate_snapshot(
                snapshot,
                {
                    "status": "READY",
                    "total_items": len(records),
                    "snapshot_fingerprint": complete_fingerprint,
                    "payload_checksum": payload_checksum(payloads),
                    "finalized_at": now,
                    "version": snapshot.version + 1,
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            failed = await self.repository.get_snapshot(
                supplier_id, source_id, snapshot.id, for_update=True
            )
            if failed is not None and failed.status == "BUILDING":
                await self.repository.mutate_snapshot(
                    failed,
                    {
                        "status": "FAILED",
                        "failure_code": "snapshot_build_failed",
                        "failure_message": "Kreiranje Snapshot-a nije uspelo",
                        "version": failed.version + 1,
                    },
                )
                await self.session.commit()
            raise
        await self.session.refresh(snapshot)
        return snapshot


__all__ = ["SupplierSnapshotService"]
