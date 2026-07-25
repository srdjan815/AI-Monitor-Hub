from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import current_actor_id
from app.modules.suppliers.delta_anomalies import anomaly_signals
from app.modules.suppliers.delta_comparison import (
    ValueChange, compare_values, decimal_value, field_role, identity_index, preview,
    value_hash, value_type,
)
from app.modules.suppliers.delta_models import (
    SupplierDeltaFieldChange, SupplierDeltaItem, SupplierDeltaRun,
)
from app.modules.suppliers.delta_repository import SupplierDeltaRepository
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.snapshot_fingerprints import item_fingerprint, snapshot_fingerprint
from app.modules.suppliers.snapshot_models import SupplierSnapshot, SupplierSnapshotItem

COMPARISON_VERSION = 1


class SupplierDeltaService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierDeltaRepository(session)

    async def compatibility(
        self, supplier_id: uuid.UUID, source_id: uuid.UUID,
        previous_id: uuid.UUID, current_id: uuid.UUID,
    ) -> tuple[SupplierSnapshot, SupplierSnapshot]:
        previous = await self.repository.snapshot(previous_id)
        current = await self.repository.snapshot(current_id)
        if previous is None or current is None:
            supplier_error(404, "snapshot_not_found", "Snapshot nije pronađen")
        if previous.id == current.id:
            supplier_error(409, "delta_same_snapshot", "Snapshot se ne može porediti sam sa sobom")
        if previous.supplier_id != supplier_id or current.supplier_id != supplier_id:
            supplier_error(409, "delta_supplier_mismatch", "Snapshot-i ne pripadaju istom dobavljaču")
        if previous.source_connection_id != source_id or current.source_connection_id != source_id:
            supplier_error(409, "delta_source_mismatch", "Snapshot-i ne pripadaju istom izvoru")
        if previous.status != "READY" or current.status != "READY":
            supplier_error(409, "delta_snapshot_not_ready", "Oba Snapshot-a moraju biti READY")
        if previous.storage_state != "ONLINE" or current.storage_state != "ONLINE":
            supplier_error(409, "SNAPSHOT_RESTORATION_REQUIRED", "Arhivirani Snapshot mora biti eksplicitno obnovljen")
        if (previous.created_at, previous.id) >= (current.created_at, current.id):
            supplier_error(409, "delta_chronology_invalid", "Prethodni Snapshot mora biti stariji")
        if not previous.snapshot_fingerprint or not current.snapshot_fingerprint:
            supplier_error(409, "delta_snapshot_integrity", "Snapshot fingerprint nedostaje")
        return previous, current

    async def calculate_previous(
        self, supplier_id: uuid.UUID, source_id: uuid.UUID,
        current_id: uuid.UUID, idempotency_key: str | None,
    ) -> SupplierDeltaRun:
        current = await self.repository.snapshot(current_id)
        if current is None or current.supplier_id != supplier_id or current.source_connection_id != source_id:
            supplier_error(404, "snapshot_not_found", "Snapshot nije pronađen")
        previous = await self.repository.previous_ready(current)
        if previous is None:
            supplier_error(409, "delta_previous_snapshot_not_found", "Ne postoji prethodni odgovarajući Snapshot")
        return await self.calculate(supplier_id, source_id, previous.id, current.id, idempotency_key)

    async def calculate(
        self, supplier_id: uuid.UUID, source_id: uuid.UUID,
        previous_id: uuid.UUID, current_id: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> SupplierDeltaRun:
        previous, current = await self.compatibility(supplier_id, source_id, previous_id, current_id)
        existing = await self.repository.successful(previous.id, current.id, COMPARISON_VERSION)
        if existing:
            return existing
        if idempotency_key:
            keyed = await self.repository.by_idempotency(supplier_id, source_id, idempotency_key)
            if keyed:
                if keyed.previous_snapshot_id != previous.id or keyed.current_snapshot_id != current.id:
                    supplier_error(409, "delta_idempotency_conflict", "Idempotency ključ je već upotrebljen")
                return keyed
        run = SupplierDeltaRun(
            supplier_id=supplier_id, source_connection_id=source_id,
            previous_snapshot_id=previous.id, current_snapshot_id=current.id,
            previous_snapshot_fingerprint=previous.snapshot_fingerprint,
            current_snapshot_fingerprint=current.snapshot_fingerprint,
            previous_schema_profile_id=previous.schema_profile_id,
            current_schema_profile_id=current.schema_profile_id,
            previous_mapping_profile_id=previous.mapping_profile_id,
            current_mapping_profile_id=current.mapping_profile_id,
            status="PENDING", comparison_version=COMPARISON_VERSION,
            idempotency_key=idempotency_key, created_by=current_actor_id() or "system",
        )
        previous_snapshot_id = previous.id
        current_snapshot_id = current.id
        try:
            await self.repository.add_run(run)
            run_id = run.id
            await self.session.commit()
            await self.session.refresh(run)
            await self.repository.mutate_run(run, {"status": "RUNNING", "started_at": datetime.now(UTC), "version": run.version + 1})
            await self.session.commit()
            previous_items = await self.repository.items(previous.id)
            current_items = await self.repository.items(current.id)
            if max(len(previous_items), len(current_items)) > settings.delta_max_comparison_items:
                raise ValueError("DELTA_ITEM_LIMIT_EXCEEDED")
            self._verify_snapshot(previous, previous_items)
            self._verify_snapshot(current, current_items)
            delta_items, fields, stats = self._compare(run.id, previous_items, current_items)
            signals = anomaly_signals(
                previous_total=len(previous_items), current_total=len(current_items),
                added=stats["added_items"], removed=stats["removed_items"],
                modified=stats["modified_items"],
                schema_changed=previous.schema_version_reference != current.schema_version_reference,
                mapping_changed=previous.mapping_version_reference != current.mapping_version_reference,
                minimum_items=settings.delta_ratio_signal_minimum_items,
                high_removal_ratio=settings.delta_high_removal_ratio,
                high_addition_ratio=settings.delta_high_addition_ratio,
                unusual_modified_ratio=settings.delta_unusual_modified_ratio,
            )
            self._reconcile(len(previous_items), len(current_items), stats)
            await self.repository.add_results(delta_items, fields)
            await self.repository.mutate_run(run, {
                **stats, "total_previous_items": len(previous_items),
                "total_current_items": len(current_items), "anomaly_signals": signals,
                "warning_count": len(signals), "status": "SUCCEEDED",
                "completed_at": datetime.now(UTC), "version": run.version + 1,
            })
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.repository.successful(previous_snapshot_id, current_snapshot_id, COMPARISON_VERSION)
            if existing:
                return existing
            await self._fail(run_id, "delta_integrity_error")
            raise
        except Exception as exc:
            await self.session.rollback()
            code = self._failure_code(exc)
            await self._fail(run_id, code)
            if code in {
                "DUPLICATE_IDENTITY",
                "SNAPSHOT_INTEGRITY_FAILURE",
                "DELTA_IDENTITY_MISSING",
                "DELTA_ITEM_LIMIT_EXCEEDED",
                "DELTA_FIELD_LIMIT_EXCEEDED",
            }:
                supplier_error(409, code, "Delta poređenje nije bezbedno moguće")
            raise
        await self.session.refresh(run)
        return run

    def _verify_snapshot(
        self, snapshot: SupplierSnapshot, items: list[SupplierSnapshotItem],
    ) -> None:
        fingerprints: list[str] = []
        for item in items:
            actual = item_fingerprint(item.mapped_data, item.source_image_links, item.source_key, item.source_identifier)
            if actual != item.item_fingerprint:
                raise ValueError("SNAPSHOT_INTEGRITY_FAILURE")
            fingerprints.append(actual)
        complete = snapshot_fingerprint(
            item_fingerprints=fingerprints,
            supplier_id=snapshot.supplier_id,
            source_id=snapshot.source_connection_id,
            acquisition_run_id=snapshot.acquisition_run_id,
            schema_version=snapshot.schema_version_reference,
            mapping_version=snapshot.mapping_version_reference,
        )
        if complete != snapshot.snapshot_fingerprint or len(items) != snapshot.total_items:
            raise ValueError("SNAPSHOT_INTEGRITY_FAILURE")

    def _compare(
        self, run_id: uuid.UUID, previous: list[SupplierSnapshotItem], current: list[SupplierSnapshotItem],
    ) -> tuple[list[SupplierDeltaItem], list[SupplierDeltaFieldChange], dict[str, int]]:
        old = identity_index(list(previous))
        new = identity_index(list(current))
        delta_items: list[SupplierDeltaItem] = []
        fields: list[SupplierDeltaFieldChange] = []
        stats = {name: 0 for name in (
            "added_items", "removed_items", "modified_items", "unchanged_items",
            "price_increased_items", "price_decreased_items", "price_unchanged_items",
            "stock_increased_items", "stock_decreased_items", "became_available_items",
            "became_unavailable_items", "image_changed_items", "identifier_changed_items",
        )}
        for key in sorted(new.keys() - old.keys()):
            item = new[key]
            delta_items.append(self._item(run_id, "ADDED", key, None, item))
            stats["added_items"] += 1
        for key in sorted(old.keys() - new.keys()):
            item = old[key]
            delta_items.append(self._item(run_id, "REMOVED", key, item, None))
            stats["removed_items"] += 1
        for key in sorted(old.keys() & new.keys()):
            prior, latest = old[key], new[key]
            if prior.item_fingerprint == latest.item_fingerprint:
                stats["unchanged_items"] += 1
                continue
            changes = compare_values(prior.mapped_data, latest.mapped_data)
            images_changed = prior.source_image_links != latest.source_image_links
            if images_changed:
                changes.append(ValueChange("source_image_links", "ARRAY_CHANGED", prior.source_image_links, latest.source_image_links))
            if len(changes) > settings.delta_max_changed_fields_per_item:
                raise ValueError("DELTA_FIELD_LIMIT_EXCEEDED")
            delta = self._item(run_id, "MODIFIED", key, prior, latest)
            price_direction = 0
            stock_direction = 0
            for change in changes:
                role = field_role(change.path)
                field = self._field(delta.id, change, role)
                fields.append(field)
                if role == "PRICE" and field.previous_numeric_value is not None and field.current_numeric_value is not None:
                    price_direction = (field.current_numeric_value > field.previous_numeric_value) - (field.current_numeric_value < field.previous_numeric_value)
                if role == "STOCK" and field.previous_numeric_value is not None and field.current_numeric_value is not None:
                    stock_direction = (field.current_numeric_value > field.previous_numeric_value) - (field.current_numeric_value < field.previous_numeric_value)
                    if field.previous_numeric_value <= 0 < field.current_numeric_value:
                        stats["became_available_items"] += 1
                    if field.previous_numeric_value > 0 >= field.current_numeric_value:
                        stats["became_unavailable_items"] += 1
            delta.changed_field_count = len(changes)
            delta.has_price_change = price_direction != 0
            delta.has_stock_change = stock_direction != 0
            delta.has_image_change = images_changed
            delta.has_identifier_change = any(field_role(change.path) == "IDENTIFIER" for change in changes)
            stats["price_increased_items"] += price_direction > 0
            stats["price_decreased_items"] += price_direction < 0
            stats["stock_increased_items"] += stock_direction > 0
            stats["stock_decreased_items"] += stock_direction < 0
            stats["image_changed_items"] += images_changed
            stats["identifier_changed_items"] += delta.has_identifier_change
            stats["modified_items"] += 1
            delta_items.append(delta)
        return delta_items, fields, stats

    @staticmethod
    def _item(run_id: uuid.UUID, change_type: str, key: tuple[str, str], previous: SupplierSnapshotItem | None, current: SupplierSnapshotItem | None) -> SupplierDeltaItem:
        return SupplierDeltaItem(
            id=uuid.uuid4(), delta_run_id=run_id, change_type=change_type,
            matching_key_type=key[0], matching_key_value=key[1],
            previous_snapshot_item_id=previous.id if previous else None,
            current_snapshot_item_id=current.id if current else None,
            previous_item_fingerprint=previous.item_fingerprint if previous else None,
            current_item_fingerprint=current.item_fingerprint if current else None,
            change_summary={"classification": change_type},
        )

    @staticmethod
    def _field(item_id: uuid.UUID, change: object, role: str | None) -> SupplierDeltaFieldChange:
        previous = getattr(change, "previous")
        current = getattr(change, "current")
        old_num, new_num = decimal_value(previous), decimal_value(current)
        absolute = new_num - old_num if old_num is not None and new_num is not None else None
        percentage = absolute / old_num * Decimal(100) if absolute is not None and old_num else None
        return SupplierDeltaFieldChange(
            delta_item_id=item_id, field_path=getattr(change, "path") or "$",
            field_role=role, change_type=getattr(change, "change_type"),
            previous_value_type=value_type(previous), current_value_type=value_type(current),
            previous_value_hash=value_hash(previous), current_value_hash=value_hash(current),
            previous_value_preview=preview(previous), current_value_preview=preview(current),
            previous_numeric_value=old_num, current_numeric_value=new_num,
            absolute_numeric_change=absolute, percentage_numeric_change=percentage,
        )

    @staticmethod
    def _reconcile(previous: int, current: int, stats: dict[str, int]) -> None:
        matched = stats["modified_items"] + stats["unchanged_items"]
        if previous != stats["removed_items"] + matched or current != stats["added_items"] + matched:
            raise ValueError("DELTA_COUNT_INVARIANT")

    async def _fail(self, run_id: uuid.UUID, code: str) -> None:
        run = await self.repository.get_run(run_id, lock=True)
        if run and run.status not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            await self.repository.mutate_run(run, {"status": "FAILED", "failure_code": code, "failure_message": "Delta poređenje nije uspelo", "error_count": 1, "completed_at": datetime.now(UTC), "version": run.version + 1})
            await self.session.commit()

    @staticmethod
    def _failure_code(exc: Exception) -> str:
        message = str(exc)
        if message.startswith("DELTA_DUPLICATE_IDENTITY"):
            return "DUPLICATE_IDENTITY"
        if message in {
            "SNAPSHOT_INTEGRITY_FAILURE",
            "DELTA_IDENTITY_MISSING",
            "DELTA_COUNT_INVARIANT",
            "DELTA_ITEM_LIMIT_EXCEEDED",
            "DELTA_FIELD_LIMIT_EXCEEDED",
        }:
            return message
        return "DELTA_CALCULATION_FAILED"

    async def cancel(self, run_id: uuid.UUID) -> SupplierDeltaRun:
        run = await self.repository.get_run(run_id, lock=True)
        if run is None:
            supplier_error(404, "delta_not_found", "Delta Run nije pronađen")
        if run.status not in {"PENDING", "RUNNING"}:
            supplier_error(409, "delta_terminal", "Završen Delta Run je nepromenljiv")
        await self.repository.mutate_run(run, {"status": "CANCELLED", "cancelled_at": datetime.now(UTC), "version": run.version + 1})
        await self.session.commit()
        await self.session.refresh(run)
        return run


__all__ = ["COMPARISON_VERSION", "SupplierDeltaService"]
