from __future__ import annotations

import re
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.enums import SupplierStatus
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.models import Supplier, SupplierSource
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.source_repository import SupplierSourceRepository
from app.modules.suppliers.source_schemas import SupplierSourceUpdate
from app.modules.suppliers.source_validation_service import (
    SupplierSourceValidationService,
)


class SupplierSourceServiceSupport:
    """Shared Source Connection validation and lookup support."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierSourceRepository(session)
        self.suppliers = SupplierRepository(session)
        self.validator = SupplierSourceValidationService()

    async def _proposed_changes(
        self,
        source: SupplierSource,
        data: SupplierSourceUpdate,
    ) -> dict[str, object]:
        supplied = data.model_fields_set - {"version", "source_type"}
        proposed: dict[str, object] = {}
        if "name" in supplied:
            assert data.name is not None
            name = self._required_name(data.name)
            await self._ensure_name_unique(source.supplier_id, name, source.id)
            proposed["name"] = name
        if "configuration" in supplied:
            assert data.configuration is not None
            proposed["configuration"] = self.validator.normalize_configuration(
                source.source_type,
                data.configuration,
            )
            proposed["last_validation_at"] = None
            proposed["last_validation_status"] = None
            proposed["last_validation_message"] = None
        if "secret_reference" in supplied:
            proposed["secret_reference"] = data.secret_reference
            proposed["last_validation_at"] = None
            proposed["last_validation_status"] = None
            proposed["last_validation_message"] = None
        if "description" in supplied:
            proposed["description"] = self._optional(data.description)
        if "status" in supplied:
            assert data.status is not None
            proposed["status"] = data.status.value
        return proposed

    async def _supplier(self, supplier_id: uuid.UUID) -> Supplier:
        supplier = await self.suppliers.get_supplier(supplier_id)
        if supplier is None:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        return supplier

    async def _usable_supplier(self, supplier_id: uuid.UUID) -> Supplier:
        supplier = await self._supplier(supplier_id)
        self._ensure_supplier_active(supplier)
        return supplier

    @staticmethod
    def _ensure_supplier_active(supplier: Supplier) -> None:
        if not supplier.is_active or supplier.status != SupplierStatus.ACTIVE.value:
            supplier_error(
                409,
                "supplier_source_supplier_inactive",
                "Izvor zahteva aktivnog dobavljača",
            )

    async def _ensure_name_unique(
        self,
        supplier_id: uuid.UUID,
        name: str,
        source_id: uuid.UUID | None = None,
    ) -> None:
        existing = await self.repository.get_active_by_name(supplier_id, name)
        if existing is not None and existing.id != source_id:
            supplier_error(
                409,
                "supplier_source_name_conflict",
                "Aktivan izvor sa tim nazivom već postoji kod dobavljača",
            )

    @staticmethod
    def _validate_transition(current: str, target: str) -> None:
        allowed = {
            "DRAFT": {"ACTIVE", "INACTIVE"},
            "ACTIVE": {"INACTIVE"},
            "INACTIVE": {"ACTIVE", "DRAFT"},
            "ERROR": {"DRAFT", "INACTIVE", "ACTIVE"},
        }
        if target != current and target not in allowed[current]:
            supplier_error(
                409,
                "supplier_source_invalid_status_transition",
                "Promena statusa izvora nije dozvoljena",
            )

    @staticmethod
    def _required_name(value: str) -> str:
        normalized = re.sub(r"\s+", " ", value.strip())
        if not normalized:
            supplier_error(
                422,
                "supplier_source_invalid_configuration",
                "Naziv izvora ne sme biti prazan",
            )
        return normalized

    @staticmethod
    def _optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = re.sub(r"\s+", " ", value.strip())
        return normalized or None

    @staticmethod
    def _constraint_name(exc: IntegrityError) -> str:
        name = getattr(exc.orig, "constraint_name", None)
        return name if isinstance(name, str) else str(exc.orig)

    @classmethod
    def _raise_integrity(cls, exc: IntegrityError) -> None:
        constraint = cls._constraint_name(exc)
        if "active_supplier_name" in constraint:
            supplier_error(
                409,
                "supplier_source_name_conflict",
                "Aktivan izvor sa tim nazivom već postoji kod dobavljača",
            )
        supplier_error(
            409,
            "supplier_source_code_conflict",
            "Interna šifra izvora već postoji",
        )

    @staticmethod
    def _version_conflict() -> None:
        supplier_error(
            409,
            "supplier_source_version_conflict",
            "Izvor je u međuvremenu izmenjen",
        )


__all__ = ["SupplierSourceServiceSupport"]
