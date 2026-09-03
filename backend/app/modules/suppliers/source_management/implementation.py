from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.core.security import current_actor_id
from app.modules.suppliers.acquisition_contracts import AcquisitionFailure
from app.modules.suppliers.enums import (
    SupplierSourceStatus,
    SupplierSourceValidationStatus,
)
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.models import SupplierSource
from app.modules.suppliers.pipeline_repository import SupplierPipelineRepository
from app.modules.suppliers.source_schemas import (
    SupplierSourceCreate,
    SupplierSourceUpdate,
    SupplierSourceValidationResponse,
)
from app.modules.suppliers.source_probe_schemas import (
    SourceCredentialState,
    SourceCredentialWrite,
)
from app.modules.suppliers.source_secrets import source_secret_provider
from app.modules.suppliers.source_service_support import (
    SupplierSourceServiceSupport,
)

logger = logging.getLogger(__name__)


class SupplierSourceService(SupplierSourceServiceSupport):
    """Source Connection lifecycle and transaction owner."""

    async def list_sources(
        self,
        supplier_id: uuid.UUID,
        **filters: Any,
    ) -> tuple[list[SupplierSource], int]:
        await self._supplier(supplier_id)
        return await self.repository.list_sources(supplier_id, **filters)

    async def get_source(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> SupplierSource:
        await self._supplier(supplier_id)
        source = await self.repository.get_source(supplier_id, source_id)
        if source is None:
            supplier_error(
                404,
                "supplier_source_not_found",
                "Izvor dobavljača nije pronađen",
            )
        return source

    async def create_source(
        self,
        supplier_id: uuid.UUID,
        data: SupplierSourceCreate,
    ) -> SupplierSource:
        await self._usable_supplier(supplier_id)
        if data.status not in {
            SupplierSourceStatus.DRAFT,
            SupplierSourceStatus.INACTIVE,
        }:
            supplier_error(
                409,
                "supplier_source_invalid_status_transition",
                "Novi izvor može biti samo DRAFT ili INACTIVE",
            )
        name = self._required_name(data.name)
        await self._ensure_name_unique(supplier_id, name)
        configuration = self.validator.normalize_configuration(
            data.source_type,
            data.configuration,
        )
        source = SupplierSource(
            supplier_id=supplier_id,
            name=name,
            source_type=data.source_type.value,
            status=data.status.value,
            is_active=True,
            configuration=configuration,
            secret_reference=data.secret_reference,
            description=self._optional(data.description),
        )
        try:
            await self.repository.create_source(source)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._raise_integrity(exc)
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(source)
        logger.info(
            "Supplier source created: source_id=%s supplier_id=%s actor=%s",
            source.id,
            supplier_id,
            current_actor_id(),
        )
        return source

    async def update_source(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        data: SupplierSourceUpdate,
    ) -> SupplierSource:
        supplier = await self._supplier(supplier_id)
        source = await self.repository.get_source(
            supplier_id,
            source_id,
            for_update=True,
        )
        if source is None:
            supplier_error(
                404,
                "supplier_source_not_found",
                "Izvor dobavljača nije pronađen",
            )
        if not source.is_active:
            supplier_error(
                409,
                "supplier_source_inactive",
                "Arhivirani izvor se ne može menjati",
            )
        if source.version != data.version:
            supplier_error(
                409,
                "supplier_source_version_conflict",
                "Izvor je u međuvremenu izmenjen",
            )
        if data.source_type is not None:
            supplier_error(
                409,
                "supplier_source_type_immutable",
                "Vrsta izvora se ne može menjati",
            )

        proposed = await self._proposed_changes(source, data)
        target_status = str(proposed.get("status", source.status))
        self._validate_transition(source.status, target_status)
        target_configuration = proposed.get("configuration", source.configuration)
        target_secret = proposed.get("secret_reference", source.secret_reference)
        assert isinstance(target_configuration, dict)
        if target_status == SupplierSourceStatus.ACTIVE.value:
            self._ensure_supplier_active(supplier)
            self.validator.ensure_secret_policy(
                source.source_type,
                target_configuration,
                target_secret if isinstance(target_secret, str) else None,
            )
            if (
                source.last_validation_status
                != SupplierSourceValidationStatus.VALID.value
                or not (source.last_validation_message or "").startswith("PROBE_OK:")
            ):
                supplier_error(
                    409,
                    "supplier_source_probe_required",
                    "Konekcija mora uspešno probno preuzeti cenovnik pre aktivacije",
                )

        changes = {
            field: value
            for field, value in proposed.items()
            if getattr(source, field) != value
        }
        if changes:
            changes["version"] = source.version + 1
        try:
            if changes:
                await self.repository.update_source(source, changes)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._raise_integrity(exc)
        except StaleDataError:
            await self.session.rollback()
            self._version_conflict()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(source)
        return source

    async def write_credentials(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        data: SourceCredentialWrite,
    ) -> SourceCredentialState:
        await self._usable_supplier(supplier_id)
        source = await self.repository.get_source(
            supplier_id, source_id, for_update=True
        )
        if source is None:
            supplier_error(404, "supplier_source_not_found", "Konekcija nije pronađena")
        if not source.is_active:
            supplier_error(409, "supplier_source_inactive", "Arhivirana konekcija se ne može menjati")
        prefix = {
            "QUERY": "query:",
            "PORTAL_FORM": "portal:",
            "SOAP_BODY": "soap:",
        }.get(data.placement, "header:")
        values: dict[str, str] = {}
        if data.username:
            values[f"{prefix}{data.username_parameter}"] = data.username
        if data.password:
            values[f"{prefix}{data.password_parameter}"] = data.password
        if data.token:
            token = f"Bearer {data.token}" if data.placement == "HEADER" else data.token
            values[f"{prefix}{data.token_parameter}"] = token
        if data.api_key:
            values[f"{prefix}{data.api_key_parameter}"] = data.api_key
        if data.imap_username and data.imap_password:
            values["imap:username"] = data.imap_username
            values["imap:password"] = data.imap_password
        try:
            reference = source_secret_provider.write(values)
        except AcquisitionFailure as exc:
            supplier_error(409, exc.code, exc.safe_message)
        try:
            await self.repository.update_source(
                source,
                {
                    "secret_reference": reference,
                    "last_validation_at": None,
                    "last_validation_status": None,
                    "last_validation_message": None,
                    "version": source.version + 1,
                },
            )
            pipeline_repository = SupplierPipelineRepository(self.session)
            schedule = await pipeline_repository.schedule(
                source_id,
                for_update=True,
            )
            if schedule is not None and schedule.status == "ENABLED":
                await pipeline_repository.mutate(
                    schedule,
                    {
                        "status": "PAUSED",
                        "next_run_at": None,
                        "version": schedule.version + 1,
                    },
                )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return SourceCredentialState(configured=True)

    async def deactivate_source(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> None:
        await self._supplier(supplier_id)
        source = await self.repository.get_source(
            supplier_id,
            source_id,
            for_update=True,
        )
        if source is None:
            supplier_error(
                404,
                "supplier_source_not_found",
                "Izvor dobavljača nije pronađen",
            )
        if not source.is_active:
            return
        try:
            await self.repository.update_source(
                source,
                {
                    "is_active": False,
                    "status": SupplierSourceStatus.INACTIVE.value,
                    "version": source.version + 1,
                },
            )
            await self.session.commit()
        except StaleDataError:
            await self.session.rollback()
            self._version_conflict()
        except Exception:
            await self.session.rollback()
            raise

    async def validate_source(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> SupplierSourceValidationResponse:
        await self._supplier(supplier_id)
        source = await self.repository.get_source(
            supplier_id,
            source_id,
            for_update=True,
        )
        if source is None:
            supplier_error(
                404,
                "supplier_source_not_found",
                "Izvor dobavljača nije pronađen",
            )
        if not source.is_active:
            supplier_error(
                409,
                "supplier_source_inactive",
                "Arhivirani izvor se ne može proveravati",
            )
        valid = not self.validator.requires_secret(
            source.source_type,
            source.configuration,
        ) or bool(source.secret_reference)
        status = (
            SupplierSourceValidationStatus.VALID
            if valid
            else SupplierSourceValidationStatus.INVALID
        )
        message = (
            "Konfiguracija je ispravna; spoljna konekcija nije izvršena"
            if valid
            else "Nedostaje obavezna referenca na poverljive podatke"
        )
        validated_at = datetime.now(UTC)
        try:
            await self.repository.update_source(
                source,
                {
                    "last_validation_at": validated_at,
                    "last_validation_status": status.value,
                    "last_validation_message": message,
                    "version": source.version + 1,
                },
            )
            await self.session.commit()
        except StaleDataError:
            await self.session.rollback()
            self._version_conflict()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(source)
        return SupplierSourceValidationResponse(
            valid=valid,
            status=status,
            message=message,
            validated_at=validated_at,
            version=source.version,
        )


__all__ = ["SupplierSourceService"]
