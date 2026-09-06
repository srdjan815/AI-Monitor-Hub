from __future__ import annotations

import uuid
import hashlib
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
)
from app.modules.suppliers.acquisition_storage import LocalArtifactStorage
from app.modules.suppliers.pipeline_models import SupplierSourceArtifact
from app.modules.suppliers.pipeline_repository import SupplierPipelineRepository
from app.modules.suppliers.schema_inference_engine import SchemaStructureDetector

SENSITIVE_MARKERS = {
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "korisnickoime",
    "lozinka",
    "password",
    "secret",
    "token",
    "username",
}


class SupplierSourceArtifactService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierPipelineRepository(session)
        self.storage = LocalArtifactStorage(
            Path(settings.supplier_artifact_root),
            settings.acquisition_max_artifact_bytes,
        )

    async def store(
        self,
        source_id: uuid.UUID,
        payload: AcquiredPayload,
    ) -> SupplierSourceArtifact:
        structure = SchemaStructureDetector.detect(payload)
        checksum = hashlib.sha256(payload.content).hexdigest()
        await self.repository.lock_artifact_checksum(checksum)
        existing = await self.repository.artifact_by_checksum(
            checksum, len(payload.content)
        )
        stored = None
        if existing is not None:
            try:
                self.storage.load(existing.storage_reference)
                stored = self.storage.link(existing.storage_reference, payload)
            except AcquisitionFailure:
                existing = None
        if existing is None:
            stored = self.storage.store(payload)
        assert stored is not None
        artifact = SupplierSourceArtifact(
            source_connection_id=source_id,
            storage_reference=stored.reference,
            original_filename=payload.original_filename,
            content_type=payload.content_type,
            detected_format=self._format(structure.detected_format),
            encoding=structure.encoding,
            size_bytes=len(payload.content),
            checksum_sha256=checksum,
            record_count=structure.record_count,
            source_metadata=self._sanitize(payload.source_metadata),
            retention_status="ONLINE",
        )
        try:
            await self.repository.add(artifact)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            if stored is not None:
                self.storage.delete(stored.reference)
            raise
        await self.session.refresh(artifact)
        return artifact

    def load(self, artifact: SupplierSourceArtifact) -> AcquiredPayload:
        return AcquiredPayload(
            content=self.storage.load(artifact.storage_reference),
            content_type=artifact.content_type,
            original_filename=artifact.original_filename,
            source_metadata={"artifact_id": str(artifact.id)},
        )

    @staticmethod
    def _format(value: str) -> str:
        return "XLSX" if value == "EXCEL" else value

    @staticmethod
    def _sanitize(metadata: dict[str, object]) -> dict[str, object]:
        clean: dict[str, object] = {}
        for key, value in metadata.items():
            normalized = key.lower().replace("-", "_")
            if any(marker in normalized for marker in SENSITIVE_MARKERS):
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                clean[key] = value[:500] if isinstance(value, str) else value
        return clean


__all__ = ["SupplierSourceArtifactService"]
