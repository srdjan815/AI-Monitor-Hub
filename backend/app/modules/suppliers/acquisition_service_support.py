from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import settings
from app.modules.suppliers.acquisition_adapters import SourceAdapterRegistry, UrllibHttpClient
from app.modules.suppliers.acquisition_context import (
    AcquisitionContext,
    AcquisitionContextResolver,
)
from app.modules.suppliers.acquisition_contracts import AcquisitionFailure
from app.modules.suppliers.acquisition_models import SupplierAcquisitionRun
from app.modules.suppliers.acquisition_parsers import ParserRegistry
from app.modules.suppliers.acquisition_processing import AcquisitionProcessor
from app.modules.suppliers.acquisition_repository import SupplierAcquisitionRepository
from app.modules.suppliers.acquisition_storage import LocalArtifactStorage
from app.modules.suppliers.source_secrets import source_secret_provider
from app.modules.suppliers.errors import supplier_error

TERMINAL = {"SUCCEEDED", "PARTIALLY_SUCCEEDED", "FAILED", "CANCELLED"}


class SupplierAcquisitionServiceSupport:
    def __init__(
        self,
        session: AsyncSession,
        *,
        adapters: SourceAdapterRegistry | None = None,
        storage: LocalArtifactStorage | None = None,
    ) -> None:
        self.session = session
        self.repository = SupplierAcquisitionRepository(session)
        self.contexts = AcquisitionContextResolver(session)
        self.parsers = ParserRegistry()
        self.processor = AcquisitionProcessor()
        self.storage = storage or LocalArtifactStorage(
            Path(settings.acquisition_artifact_root),
            settings.acquisition_max_artifact_bytes,
        )
        self.adapters = adapters or SourceAdapterRegistry(
            UrllibHttpClient(),
            source_secret_provider,
            settings.acquisition_max_artifact_bytes,
        )

    async def _create_run(
        self,
        context: AcquisitionContext,
        trigger: str,
        key: str | None,
        fingerprint: str,
    ) -> tuple[SupplierAcquisitionRun, bool]:
        run = SupplierAcquisitionRun(
            supplier_id=context.supplier.id,
            source_connection_id=context.source.id,
            schema_profile_id=context.schema.id,
            mapping_profile_id=context.mapping.id,
            schema_version_reference=context.schema.version_number,
            mapping_version_reference=context.mapping.version_number,
            trigger_type=trigger,
            status="PENDING",
            idempotency_key=key,
            request_fingerprint=fingerprint if key else None,
            source_type=context.source.source_type,
        )
        try:
            await self.repository.add_run(run)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            if key:
                existing = await self._idempotent(
                    context.source.id,
                    key,
                    fingerprint,
                )
                if existing:
                    return existing, False
            raise
        await self.session.refresh(run)
        return run, True

    async def _idempotent(
        self,
        source_id: uuid.UUID,
        key: str | None,
        fingerprint: str,
    ) -> SupplierAcquisitionRun | None:
        if not key:
            return None
        existing = await self.repository.by_idempotency(source_id, key)
        if existing and existing.request_fingerprint != fingerprint:
            supplier_error(
                409,
                "acquisition_idempotency_conflict",
                "Idempotency ključ je već korišćen za drugi zahtev",
            )
        return existing

    async def _fail(
        self,
        run: SupplierAcquisitionRun,
        failure: AcquisitionFailure,
    ) -> SupplierAcquisitionRun:
        await self._mutate_commit(
            run,
            {
                "status": "FAILED",
                "failure_code": failure.code[:100],
                "failure_message": failure.safe_message,
                "completed_at": datetime.now(UTC),
            },
        )
        return run

    async def _run(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierAcquisitionRun:
        run = await self.repository.get_run(
            supplier_id,
            source_id,
            run_id,
            for_update=for_update,
        )
        if run is None:
            supplier_error(
                404,
                "acquisition_run_not_found",
                "Acquisition Run nije pronađen",
            )
        return run

    async def _mutate_commit(
        self,
        run: SupplierAcquisitionRun,
        changes: dict[str, object],
    ) -> None:
        if run.status in TERMINAL:
            supplier_error(
                409,
                "acquisition_terminal_immutable",
                "Terminalni Acquisition Run je nepromenljiv",
            )
        changes["version"] = run.version + 1
        try:
            await self.repository.mutate_run(run, changes)
            await self.session.commit()
        except StaleDataError:
            await self.session.rollback()
            supplier_error(
                409,
                "acquisition_version_conflict",
                "Acquisition Run je u međuvremenu izmenjen",
            )
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(run)

    @staticmethod
    def _fingerprint(
        context: AcquisitionContext,
        trigger: str,
        checksum: str | None,
    ) -> str:
        value = {
            "source": str(context.source.id),
            "source_version": context.source.version,
            "schema": str(context.schema.id),
            "mapping": str(context.mapping.id),
            "trigger": trigger,
            "checksum": checksum,
        }
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


__all__ = ["SupplierAcquisitionServiceSupport", "TERMINAL"]
