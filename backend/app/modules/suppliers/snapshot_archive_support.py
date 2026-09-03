from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.suppliers.acquisition_storage import LocalArtifactStorage
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.snapshot_archive_format import SnapshotArchiveFormat
from app.modules.suppliers.snapshot_archive_storage import (
    LocalSnapshotArchiveStorage,
)
from app.modules.suppliers.snapshot_contracts import (
    SnapshotFailure,
    SnapshotItemPayload,
)
from app.modules.suppliers.snapshot_fingerprints import (
    item_fingerprint,
    snapshot_fingerprint,
)
from app.modules.suppliers.snapshot_models import (
    SupplierSnapshot,
    SupplierSnapshotArchiveOperation,
    SupplierSnapshotItem,
)
from app.modules.suppliers.snapshot_query_service import SupplierSnapshotQueryService
from app.modules.suppliers.snapshot_repository import SupplierSnapshotRepository


class SupplierSnapshotArchiveSupport:
    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: LocalSnapshotArchiveStorage | None = None,
        artifact_storage: LocalArtifactStorage | None = None,
    ) -> None:
        self.session = session
        self.repository = SupplierSnapshotRepository(session)
        self.queries = SupplierSnapshotQueryService(session)
        self.storage = storage or LocalSnapshotArchiveStorage(
            Path(settings.snapshot_archive_root),
            settings.snapshot_archive_max_bytes,
        )
        self.artifacts = artifact_storage or LocalArtifactStorage(
            Path(settings.acquisition_artifact_root),
            settings.acquisition_max_artifact_bytes,
        )
        self.format = SnapshotArchiveFormat()

    async def _artifact(
        self,
        snapshot: SupplierSnapshot,
        include: bool,
    ) -> tuple[bytes | None, dict[str, object] | None]:
        if not include:
            return None, None
        run = await self.repository.acquisition(
            snapshot.supplier_id,
            snapshot.source_connection_id,
            snapshot.acquisition_run_id,
        )
        if run is None or not run.artifact_reference or not run.checksum:
            raise SnapshotFailure(
                "snapshot_source_artifact_missing",
                "Originalni Acquisition artefakt nije dostupan",
            )
        content = self.artifacts.load(run.artifact_reference)
        checksum = hashlib.sha256(content).hexdigest()
        if checksum != run.checksum:
            raise SnapshotFailure(
                "snapshot_source_artifact_checksum",
                "Checksum originalnog Acquisition artefakta nije ispravan",
            )
        return content, {
            "checksum": checksum,
            "display_filename": run.original_filename,
            "size_bytes": len(content),
        }

    async def _commit_operation(
        self,
        operation: SupplierSnapshotArchiveOperation,
    ) -> None:
        try:
            await self.repository.add_operation(operation)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(operation)

    async def _fail_operation(
        self,
        operation: SupplierSnapshotArchiveOperation,
        failure: SnapshotFailure,
    ) -> None:
        await self.session.rollback()
        current = await self.repository.get_operation(
            operation.snapshot_id, operation.id
        )
        if current is not None:
            await self.repository.mutate_operation(
                current,
                {
                    "status": "FAILED",
                    "failure_code": failure.code,
                    "failure_message": failure.safe_message,
                    "completed_at": datetime.now(UTC),
                },
            )
            await self.session.commit()

    async def _locked(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        snapshot_id: uuid.UUID,
    ) -> SupplierSnapshot:
        snapshot = await self.repository.get_snapshot(
            supplier_id, source_id, snapshot_id, for_update=True
        )
        if snapshot is None:
            supplier_error(404, "snapshot_not_found", "Snapshot nije pronađen")
        return snapshot

    async def _operation(
        self,
        snapshot_id: uuid.UUID,
        operation_id: uuid.UUID,
    ) -> SupplierSnapshotArchiveOperation:
        operation = await self.repository.get_operation(snapshot_id, operation_id)
        if operation is None:
            supplier_error(
                404,
                "snapshot_archive_operation_not_found",
                "Operacija arhiviranja nije pronađena",
            )
        return operation

    async def _set_state(self, snapshot: SupplierSnapshot, state: str) -> None:
        await self.repository.mutate_snapshot(
            snapshot,
            {"storage_state": state, "version": snapshot.version + 1},
        )
        await self.session.commit()
        await self.session.refresh(snapshot)

    @staticmethod
    def _require_exportable(snapshot: SupplierSnapshot) -> None:
        if snapshot.status != "READY" or snapshot.storage_state != "ONLINE":
            supplier_error(
                409,
                "snapshot_archive_not_allowed",
                "Izvoz zahteva READY i ONLINE Snapshot",
            )

    @staticmethod
    def _snapshot_payload(snapshot: SupplierSnapshot) -> dict[str, object]:
        return {
            "id": str(snapshot.id),
            "snapshot_code": snapshot.snapshot_code,
            "supplier_id": str(snapshot.supplier_id),
            "source_connection_id": str(snapshot.source_connection_id),
            "acquisition_run_id": str(snapshot.acquisition_run_id),
            "schema_profile_id": str(snapshot.schema_profile_id),
            "mapping_profile_id": str(snapshot.mapping_profile_id),
            "schema_version_reference": snapshot.schema_version_reference,
            "mapping_version_reference": snapshot.mapping_version_reference,
            "snapshot_fingerprint": snapshot.snapshot_fingerprint,
            "payload_checksum": snapshot.payload_checksum,
            "total_items": snapshot.total_items,
        }

    @staticmethod
    def _item_payload(item: SupplierSnapshotItem) -> SnapshotItemPayload:
        return SnapshotItemPayload(
            id=str(item.id),
            source_staged_record_id=str(item.source_staged_record_id),
            record_number=item.record_number,
            source_key=item.source_key,
            source_identifier=item.source_identifier,
            item_fingerprint=item.item_fingerprint,
            mapped_data=item.mapped_data,
            source_image_links=item.source_image_links,
        )

    @staticmethod
    def _verify_restored_fingerprints(
        snapshot: SupplierSnapshot,
        items: Iterable[SnapshotItemPayload],
    ) -> None:
        fingerprints: list[str] = []
        for item in items:
            calculated = item_fingerprint(
                item.mapped_data,
                item.source_image_links,
                item.source_key,
                item.source_identifier,
            )
            if calculated != item.item_fingerprint:
                raise SnapshotFailure(
                    "snapshot_archive_item_fingerprint",
                    "Fingerprint stavke iz arhive nije ispravan",
                )
            fingerprints.append(calculated)
        complete = snapshot_fingerprint(
            item_fingerprints=fingerprints,
            supplier_id=snapshot.supplier_id,
            source_id=snapshot.source_connection_id,
            acquisition_run_id=snapshot.acquisition_run_id,
            schema_version=snapshot.schema_version_reference,
            mapping_version=snapshot.mapping_version_reference,
        )
        if complete != snapshot.snapshot_fingerprint:
            raise SnapshotFailure(
                "snapshot_archive_fingerprint_mismatch",
                "Fingerprint obnovljenog Snapshot-a nije ispravan",
            )

    @staticmethod
    def _file_checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()


__all__ = ["SupplierSnapshotArchiveSupport"]
