from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from app.core.config import settings
from app.modules.suppliers.acquisition_context import AcquisitionContext
from app.modules.suppliers.acquisition_contracts import (
    AcquiredPayload,
    AcquisitionFailure,
)
from app.modules.suppliers.acquisition_models import SupplierAcquisitionRun
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.acquisition_service_support import (
    TERMINAL,
    SupplierAcquisitionServiceSupport,
)


class SupplierAcquisitionService(SupplierAcquisitionServiceSupport):
    async def execute_artifact(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        payload: AcquiredPayload,
        *,
        idempotency_key: str,
    ) -> SupplierAcquisitionRun:
        context = await self.contexts.resolve(supplier_id, source_id)
        return await self.execute_artifact_context(
            context,
            payload,
            idempotency_key=idempotency_key,
        )

    async def execute_artifact_context(
        self,
        context: AcquisitionContext,
        payload: AcquiredPayload,
        *,
        idempotency_key: str,
    ) -> SupplierAcquisitionRun:
        """Process an Artifact with an already resolved immutable contract."""
        checksum = hashlib.sha256(payload.content).hexdigest()
        fingerprint = self._fingerprint(context, "API_REQUEST", checksum)
        existing = await self._idempotent(
            context.source.id, idempotency_key, fingerprint
        )
        if existing:
            return existing
        run, created = await self._create_run(
            context,
            "API_REQUEST",
            idempotency_key,
            fingerprint,
        )
        if not created:
            return run
        try:
            return await self._process(run, context, payload)
        except AcquisitionFailure as exc:
            return await self._fail(run, exc)
        except Exception:
            return await self._fail(
                run,
                AcquisitionFailure(
                    "acquisition_unexpected_failure",
                    "Acquisition nije uspeo",
                ),
            )

    async def execute(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        *,
        idempotency_key: str | None,
    ) -> SupplierAcquisitionRun:
        context = await self.contexts.resolve(supplier_id, source_id)
        fingerprint = self._fingerprint(context, "API_REQUEST", None)
        existing = await self._idempotent(source_id, idempotency_key, fingerprint)
        if existing:
            return existing
        run, created = await self._create_run(
            context,
            "API_REQUEST",
            idempotency_key,
            fingerprint,
        )
        if not created:
            return run
        try:
            payload = await self.adapters.resolve(context.source.source_type).acquire(
                context.source
            )
            return await self._process(run, context, payload)
        except AcquisitionFailure as exc:
            return await self._fail(run, exc)
        except Exception:
            return await self._fail(
                run,
                AcquisitionFailure(
                    "acquisition_unexpected_failure",
                    "Acquisition nije uspeo",
                ),
            )

    async def upload(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        *,
        content: bytes,
        filename: str,
        content_type: str | None,
        idempotency_key: str | None,
    ) -> SupplierAcquisitionRun:
        context = await self.contexts.resolve(supplier_id, source_id)
        checksum = hashlib.sha256(content).hexdigest()
        fingerprint = self._fingerprint(context, "MANUAL_UPLOAD", checksum)
        existing = await self._idempotent(source_id, idempotency_key, fingerprint)
        if existing:
            return existing
        run, created = await self._create_run(
            context,
            "MANUAL_UPLOAD",
            idempotency_key,
            fingerprint,
        )
        if not created:
            return run
        payload = AcquiredPayload(
            content=content,
            content_type=content_type,
            original_filename=filename,
            source_metadata={"transport": "manual-upload"},
        )
        try:
            acquired = await self.adapters.resolve(context.source.source_type).acquire(
                context.source, payload
            )
            return await self._process(run, context, acquired)
        except AcquisitionFailure as exc:
            return await self._fail(run, exc)
        except Exception:
            return await self._fail(
                run,
                AcquisitionFailure(
                    "acquisition_unexpected_failure",
                    "Acquisition nije uspeo",
                ),
            )

    async def retry(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        idempotency_key: str | None,
    ) -> SupplierAcquisitionRun:
        original = await self._run(supplier_id, source_id, run_id)
        if original.status not in TERMINAL:
            supplier_error(
                409,
                "acquisition_retry_not_allowed",
                "Samo terminalni run može biti ponovljen",
            )
        if original.artifact_reference:
            return await self.upload(
                supplier_id,
                source_id,
                content=self.storage.load(original.artifact_reference),
                filename=original.original_filename or "retry.bin",
                content_type=original.content_type,
                idempotency_key=idempotency_key,
            )
        return await self.execute(
            supplier_id,
            source_id,
            idempotency_key=idempotency_key,
        )

    async def cancel(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> SupplierAcquisitionRun:
        run = await self._run(supplier_id, source_id, run_id, for_update=True)
        if run.status not in {"PENDING", "RUNNING"}:
            supplier_error(
                409,
                "acquisition_cancel_not_allowed",
                "Terminalni run se ne može otkazati",
            )
        await self._mutate_commit(
            run,
            {
                "status": "CANCELLED",
                "cancelled_at": datetime.now(UTC),
            },
        )
        return run

    async def _process(
        self,
        run: SupplierAcquisitionRun,
        context: AcquisitionContext,
        payload: AcquiredPayload,
    ) -> SupplierAcquisitionRun:
        await self._mutate_commit(
            run,
            {"status": "RUNNING", "started_at": datetime.now(UTC)},
        )
        artifact = self.storage.store(payload)
        await self._mutate_commit(
            run,
            {
                "artifact_reference": artifact.reference,
                "checksum": artifact.checksum,
                "artifact_size_bytes": artifact.size_bytes,
                "content_type": artifact.content_type,
                "original_filename": artifact.original_filename,
            },
        )
        parser_configuration = dict(context.source.configuration)
        if context.schema.record_path:
            parser_configuration["item_path"] = context.schema.record_path
        if context.schema.root_path:
            parser_configuration["root_path"] = context.schema.root_path
        if context.schema.encoding:
            parser_configuration["encoding"] = context.schema.encoding
        if context.schema.delimiter:
            parser_configuration["delimiter"] = context.schema.delimiter
        header_row = context.schema.analysis_metadata.get("header_row")
        if isinstance(header_row, int):
            parser_configuration["header_row"] = header_row
            parser_configuration["data_start_row"] = header_row + 1
        parser = self.parsers.resolve(
            context.source.source_type,
            artifact.content_type,
            artifact.original_filename,
            parser_configuration,
        )
        rows = parser.parse(payload.content, parser_configuration)
        if not rows:
            raise AcquisitionFailure(
                "acquisition_no_records",
                "Ulaz ne sadrži zapise",
            )
        if len(rows) > settings.acquisition_max_records:
            raise AcquisitionFailure(
                "acquisition_record_limit",
                "Broj zapisa prelazi dozvoljeni limit",
            )
        result = self.processor.process(run.id, rows, context)
        if result.accepted == 0:
            status = "FAILED"
        elif result.rejected:
            status = "PARTIALLY_SUCCEEDED"
        else:
            status = "SUCCEEDED"
        try:
            await self.repository.add_results(result.records, result.issues)
            await self.repository.mutate_run(
                run,
                {
                    "status": status,
                    "total_record_count": len(result.records),
                    "accepted_record_count": result.accepted,
                    "rejected_record_count": result.rejected,
                    "warning_count": result.warnings,
                    "error_count": result.errors,
                    "completed_at": datetime.now(UTC),
                    "failure_code": (
                        "acquisition_all_records_rejected"
                        if status == "FAILED"
                        else None
                    ),
                    "failure_message": (
                        "Svi ulazni zapisi su odbijeni" if status == "FAILED" else None
                    ),
                    "version": run.version + 1,
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(run)
        return run


__all__ = ["SupplierAcquisitionService"]
