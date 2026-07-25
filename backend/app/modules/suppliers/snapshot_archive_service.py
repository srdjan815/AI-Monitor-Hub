from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings
from app.core.security import current_actor_id
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.snapshot_archive_format import (
    FORMAT_VERSION,
    MANIFEST_VERSION,
)
from app.modules.suppliers.snapshot_archive_support import (
    SupplierSnapshotArchiveSupport,
)
from app.modules.suppliers.snapshot_contracts import (
    SnapshotFailure,
    StoredSnapshotArchive,
)
from app.modules.suppliers.snapshot_models import (
    SupplierSnapshot,
    SupplierSnapshotArchiveOperation,
    SupplierSnapshotItem,
)


class SupplierSnapshotArchiveService(SupplierSnapshotArchiveSupport):
    async def export(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        snapshot_id: uuid.UUID,
        *,
        include_source_artifact: bool,
    ) -> SupplierSnapshotArchiveOperation:
        snapshot = await self.queries.get(supplier_id, source_id, snapshot_id)
        self._require_exportable(snapshot)
        _, valid, _ = await self.queries.verify_integrity(
            supplier_id, source_id, snapshot_id
        )
        if not valid:
            supplier_error(
                409,
                "snapshot_integrity_failed",
                "Snapshot nije prošao proveru integriteta",
            )
        items = await self.repository.all_items(snapshot.id)
        if len(items) != snapshot.total_items:
            supplier_error(
                409,
                "snapshot_integrity_failed",
                "Snapshot nema očekivani broj aktivnih stavki",
            )
        operation = SupplierSnapshotArchiveOperation(
            snapshot_id=snapshot.id,
            status="EXPORTING",
            include_source_artifact=include_source_artifact,
            created_by=current_actor_id() or "system",
            format_version=FORMAT_VERSION,
            manifest_version=MANIFEST_VERSION,
        )
        await self._commit_operation(operation)
        temporary: Path | None = None
        stored: StoredSnapshotArchive | None = None
        try:
            temporary, destination = self.storage.allocate(snapshot.snapshot_code)
            artifact, artifact_metadata = await self._artifact(
                snapshot, include_source_artifact
            )
            await self.session.commit()
            self.format.write(
                temporary,
                snapshot=self._snapshot_payload(snapshot),
                items=(self._item_payload(item) for item in items),
                item_count=len(items),
                acquisition_artifact=artifact,
                acquisition_artifact_metadata=artifact_metadata,
            )
            stored = self.storage.finalize(temporary, destination)
            self.format.verify(
                stored.path,
                expected_snapshot_id=str(snapshot.id),
                expected_fingerprint=str(snapshot.snapshot_fingerprint),
                expected_item_count=snapshot.total_items,
            )
            now = datetime.now(UTC)
            await self.repository.mutate_operation(
                operation,
                {
                    "status": "VERIFIED",
                    "archive_reference": stored.reference,
                    "archive_checksum": stored.checksum,
                    "archive_size_bytes": stored.size_bytes,
                    "verified_at": now,
                },
            )
            await self.repository.mutate_snapshot(
                snapshot,
                {
                    "archive_reference": stored.reference,
                    "archive_checksum": stored.checksum,
                    "archive_size_bytes": stored.size_bytes,
                    "archive_format_version": FORMAT_VERSION,
                    "archive_manifest_version": MANIFEST_VERSION,
                    "version": snapshot.version + 1,
                },
            )
            await self.session.commit()
        except SnapshotFailure as exc:
            if temporary is not None:
                self.storage.remove_temporary(temporary)
            if stored is not None:
                self.storage.delete(stored.reference)
            await self._fail_operation(operation, exc)
        except Exception:
            if temporary is not None:
                self.storage.remove_temporary(temporary)
            if stored is not None:
                self.storage.delete(stored.reference)
            await self._fail_operation(
                operation,
                SnapshotFailure(
                    "snapshot_archive_export_failed",
                    "Izvoz Snapshot arhive nije uspeo",
                ),
            )
        await self.session.refresh(operation)
        return operation

    async def confirm_offload(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        snapshot_id: uuid.UUID,
        operation_id: uuid.UUID,
        *,
        archive_reference: str,
        archive_checksum: str,
        override_preserve_online: bool,
    ) -> SupplierSnapshot:
        initial = await self.queries.get(supplier_id, source_id, snapshot_id)
        operation = await self._operation(initial.id, operation_id)
        if initial.legal_hold:
            supplier_error(
                409,
                "snapshot_legal_hold",
                "Legal hold sprečava uklanjanje aktivnog Snapshot payload-a",
            )
        if initial.preserve_online and not override_preserve_online:
            supplier_error(
                409,
                "snapshot_preserve_online",
                "Snapshot je označen da ostane u aktivnom skladištu",
            )
        if initial.storage_state != "ONLINE" or operation.status != "VERIFIED":
            supplier_error(
                409,
                "snapshot_offload_not_allowed",
                "Offload zahteva ONLINE Snapshot i verifikovanu arhivu",
            )
        if (
            operation.archive_reference != archive_reference
            or operation.archive_checksum != archive_checksum
        ):
            supplier_error(
                409,
                "snapshot_archive_confirmation_mismatch",
                "Potvrda arhive se ne podudara sa verifikovanim izvozom",
            )
        path = self.storage.resolve(archive_reference)
        if self._file_checksum(path) != archive_checksum:
            supplier_error(
                409,
                "snapshot_archive_checksum_mismatch",
                "Checksum arhive se više ne podudara",
            )
        self.format.verify(
            path,
            expected_snapshot_id=str(initial.id),
            expected_fingerprint=str(initial.snapshot_fingerprint),
            expected_item_count=initial.total_items,
        )
        expected_version = initial.version
        expected_fingerprint = initial.snapshot_fingerprint
        await self.session.rollback()
        snapshot = await self._locked(supplier_id, source_id, snapshot_id)
        operation = await self._operation(snapshot.id, operation_id)
        if (
            snapshot.version != expected_version
            or snapshot.snapshot_fingerprint != expected_fingerprint
            or snapshot.legal_hold
            or (snapshot.preserve_online and not override_preserve_online)
            or snapshot.storage_state != "ONLINE"
            or operation.status != "VERIFIED"
            or operation.archive_reference != archive_reference
            or operation.archive_checksum != archive_checksum
        ):
            supplier_error(
                409,
                "snapshot_offload_state_changed",
                "Snapshot ili verifikovana arhiva su izmenjeni tokom potvrde",
            )
        try:
            await self.repository.delete_items(snapshot.id)
            now = datetime.now(UTC)
            await self.repository.mutate_snapshot(
                snapshot,
                {
                    "storage_state": "ARCHIVED",
                    "archived_at": now,
                    "version": snapshot.version + 1,
                },
            )
            await self.repository.mutate_operation(
                operation,
                {"status": "OFFLOADED", "completed_at": now},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(snapshot)
        return snapshot

    async def restore(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        snapshot_id: uuid.UUID,
    ) -> SupplierSnapshot:
        initial = await self.queries.get(supplier_id, source_id, snapshot_id)
        if initial.storage_state != "ARCHIVED" or not initial.archive_reference:
            supplier_error(
                409,
                "snapshot_restore_not_allowed",
                "Samo ARCHIVED Snapshot može biti obnovljen",
            )
        path = self.storage.resolve(initial.archive_reference)
        if self._file_checksum(path) != initial.archive_checksum:
            supplier_error(
                409,
                "snapshot_archive_checksum_mismatch",
                "Checksum Snapshot arhive nije ispravan",
            )
        self.format.verify(
            path,
            expected_snapshot_id=str(initial.id),
            expected_fingerprint=str(initial.snapshot_fingerprint),
            expected_item_count=initial.total_items,
        )
        self._verify_restored_fingerprints(initial, self.format.iter_items(path))
        expected_version = initial.version
        expected_fingerprint = initial.snapshot_fingerprint
        expected_reference = initial.archive_reference
        expected_checksum = initial.archive_checksum
        await self.session.rollback()
        snapshot = await self._locked(supplier_id, source_id, snapshot_id)
        if (
            snapshot.version != expected_version
            or snapshot.snapshot_fingerprint != expected_fingerprint
            or snapshot.storage_state != "ARCHIVED"
            or snapshot.archive_reference != expected_reference
            or snapshot.archive_checksum != expected_checksum
        ):
            supplier_error(
                409,
                "snapshot_restore_state_changed",
                "Snapshot ili arhiva su izmenjeni tokom verifikacije",
            )
        await self._set_state(snapshot, "RESTORING")
        try:
            batch: list[SupplierSnapshotItem] = []
            for item in self.format.iter_items(path):
                batch.append(
                    SupplierSnapshotItem(
                        id=uuid.UUID(item.id),
                        snapshot_id=snapshot.id,
                        source_staged_record_id=uuid.UUID(item.source_staged_record_id),
                        record_number=item.record_number,
                        source_key=item.source_key,
                        source_identifier=item.source_identifier,
                        item_fingerprint=item.item_fingerprint,
                        mapped_data=item.mapped_data,
                        source_image_links=item.source_image_links,
                    )
                )
                if len(batch) >= settings.snapshot_batch_size:
                    await self.repository.add_items(batch)
                    batch = []
            if batch:
                await self.repository.add_items(batch)
            operation = SupplierSnapshotArchiveOperation(
                snapshot_id=snapshot.id,
                status="RESTORED",
                archive_reference=snapshot.archive_reference,
                archive_checksum=snapshot.archive_checksum,
                archive_size_bytes=snapshot.archive_size_bytes,
                format_version=FORMAT_VERSION,
                manifest_version=MANIFEST_VERSION,
                include_source_artifact=False,
                completed_at=datetime.now(UTC),
                created_by=current_actor_id() or "system",
            )
            await self.repository.add_operation(operation)
            await self.repository.mutate_snapshot(
                snapshot,
                {
                    "storage_state": "ONLINE",
                    "restored_at": datetime.now(UTC),
                    "version": snapshot.version + 1,
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            failed = await self.repository.get_snapshot(
                supplier_id, source_id, snapshot_id, for_update=True
            )
            if failed is not None and failed.storage_state == "RESTORING":
                await self.repository.mutate_snapshot(
                    failed,
                    {
                        "storage_state": "ARCHIVED",
                        "version": failed.version + 1,
                    },
                )
                await self.session.commit()
            raise
        await self.session.refresh(snapshot)
        return snapshot


__all__ = ["SupplierSnapshotArchiveService"]
