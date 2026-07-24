from __future__ import annotations

import logging
import uuid
from typing import Any, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.core.security import current_actor_id
from app.modules.suppliers.enums import SupplierStatus
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.models import Supplier
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.schemas import SupplierCreate, SupplierUpdate
from app.modules.suppliers.validation_service import SupplierValidationService

logger = logging.getLogger(__name__)


class SupplierService:
    """Supplier validation, state transitions, and transaction ownership."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierRepository(session)
        self.validation = SupplierValidationService(self.repository)

    async def list_suppliers(self, **filters: Any) -> tuple[list[Supplier], int]:
        return await self.repository.list_suppliers(**filters)

    async def get_supplier(self, supplier_id: uuid.UUID) -> Supplier:
        supplier = await self.repository.get_supplier(supplier_id)
        if supplier is None:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        return supplier

    async def create_supplier(self, data: SupplierCreate) -> Supplier:
        company_name = self.validation.required(
            data.company_name,
            "Naziv dobavljača",
        )
        tax_identifier = self.validation.identifier(data.tax_identifier)
        registration_number = self.validation.identifier(data.registration_number)
        await self.validation.ensure_identifiers_unique(
            tax_identifier=tax_identifier,
            registration_number=registration_number,
        )
        supplier = Supplier(
            company_name=company_name,
            address=self.validation.optional(data.address),
            tax_identifier=tax_identifier,
            registration_number=registration_number,
            status=data.status.value,
            is_active=True,
        )
        try:
            await self.repository.create_supplier(supplier)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self.validation.raise_supplier_integrity(exc)
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(supplier)
        logger.info(
            "Supplier created: supplier_id=%s actor=%s",
            supplier.id,
            current_actor_id(),
        )
        return supplier

    async def update_supplier(
        self,
        supplier_id: uuid.UUID,
        data: SupplierUpdate,
    ) -> Supplier:
        supplier = await self.repository.get_supplier(supplier_id, for_update=True)
        if supplier is None:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        if not supplier.is_active:
            supplier_error(
                409,
                "supplier_inactive",
                "Arhivirani dobavljač se ne može menjati",
            )
        if supplier.version != data.version:
            supplier_error(
                409,
                "supplier_version_conflict",
                "Dobavljač je u međuvremenu izmenjen",
            )

        supplied = data.model_fields_set - {"version"}
        proposed: dict[str, object] = {}
        if "company_name" in supplied:
            assert data.company_name is not None
            proposed["company_name"] = self.validation.required(
                data.company_name,
                "Naziv dobavljača",
            )
        if "address" in supplied:
            proposed["address"] = self.validation.optional(data.address)
        if "tax_identifier" in supplied:
            proposed["tax_identifier"] = self.validation.identifier(data.tax_identifier)
        if "registration_number" in supplied:
            proposed["registration_number"] = self.validation.identifier(
                data.registration_number
            )
        if "status" in supplied:
            assert data.status is not None
            self.validation.validate_status_transition(
                supplier.status,
                data.status.value,
            )
            proposed["status"] = data.status.value

        await self.validation.ensure_identifiers_unique(
            tax_identifier=cast(
                str | None,
                proposed.get("tax_identifier", supplier.tax_identifier),
            ),
            registration_number=cast(
                str | None,
                proposed.get(
                    "registration_number",
                    supplier.registration_number,
                ),
            ),
            supplier_id=supplier.id,
        )
        changes = {
            field: value
            for field, value in proposed.items()
            if getattr(supplier, field) != value
        }
        if changes:
            changes["version"] = supplier.version + 1

        try:
            if changes:
                await self.repository.update_supplier(supplier, changes)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self.validation.raise_supplier_integrity(exc)
        except StaleDataError:
            await self.session.rollback()
            supplier_error(
                409,
                "supplier_version_conflict",
                "Dobavljač je u međuvremenu izmenjen",
            )
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(supplier)
        return supplier

    async def deactivate_supplier(self, supplier_id: uuid.UUID) -> None:
        supplier = await self.repository.get_supplier(supplier_id, for_update=True)
        if supplier is None:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        if not supplier.is_active:
            return
        try:
            await self.repository.update_supplier(
                supplier,
                {
                    "is_active": False,
                    "status": SupplierStatus.INACTIVE.value,
                    "version": supplier.version + 1,
                },
            )
            await self.session.commit()
        except StaleDataError:
            await self.session.rollback()
            supplier_error(
                409,
                "supplier_version_conflict",
                "Dobavljač je u međuvremenu izmenjen",
            )
        except Exception:
            await self.session.rollback()
            raise


__all__ = ["SupplierService"]
