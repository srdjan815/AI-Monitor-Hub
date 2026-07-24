from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.modules.suppliers.enums import SupplierStatus
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.models import Supplier, SupplierContact
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.schemas import (
    SupplierContactCreate,
    SupplierContactUpdate,
)
from app.modules.suppliers.validation_service import SupplierValidationService


class SupplierContactService:
    """Supplier Contact validation and transaction ownership."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierRepository(session)
        self.validation = SupplierValidationService(self.repository)

    async def get_contact(
        self,
        supplier_id: uuid.UUID,
        contact_id: uuid.UUID,
    ) -> SupplierContact:
        await self._get_supplier(supplier_id)
        contact = await self.repository.get_contact(supplier_id, contact_id)
        if contact is None:
            supplier_error(
                404,
                "supplier_contact_not_found",
                "Kontakt dobavljača nije pronađen",
            )
        return contact

    async def list_contacts(
        self,
        supplier_id: uuid.UUID,
        **filters: Any,
    ) -> tuple[list[SupplierContact], int]:
        await self._get_supplier(supplier_id)
        return await self.repository.list_contacts(supplier_id, **filters)

    async def create_contact(
        self,
        supplier_id: uuid.UUID,
        data: SupplierContactCreate,
    ) -> SupplierContact:
        supplier = await self.repository.get_supplier(supplier_id, for_update=True)
        if supplier is None:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        if not supplier.is_active or supplier.status == SupplierStatus.INACTIVE.value:
            supplier_error(
                409,
                "supplier_inactive",
                "Neaktivan ili arhiviran dobavljač ne može dobiti novi kontakt",
            )
        email = self.validation.email(data.email)
        phone = self.validation.phone(data.phone)
        self.validation.require_contact_channel(email, phone)
        if data.is_primary:
            await self._ensure_primary_available(
                supplier_id,
                data.contact_type.value,
            )
        contact = SupplierContact(
            supplier_id=supplier_id,
            contact_type=data.contact_type.value,
            name=self.validation.required(data.name, "Ime kontakta"),
            email=email,
            phone=phone,
            position=self.validation.optional(data.position),
            is_primary=data.is_primary,
            is_active=True,
        )
        try:
            await self.repository.create_contact(contact)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self.validation.raise_contact_integrity(exc)
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(contact)
        return contact

    async def update_contact(
        self,
        supplier_id: uuid.UUID,
        contact_id: uuid.UUID,
        data: SupplierContactUpdate,
    ) -> SupplierContact:
        supplier = await self._get_supplier(supplier_id)
        if not supplier.is_active:
            supplier_error(
                409,
                "supplier_inactive",
                "Kontakt arhiviranog dobavljača se ne može menjati",
            )
        contact = await self.repository.get_contact(
            supplier_id,
            contact_id,
            for_update=True,
        )
        if contact is None:
            supplier_error(
                404,
                "supplier_contact_not_found",
                "Kontakt dobavljača nije pronađen",
            )
        if not contact.is_active:
            supplier_error(
                409,
                "supplier_contact_invalid",
                "Arhivirani kontakt se ne može menjati",
            )
        if contact.version != data.version:
            supplier_error(
                409,
                "supplier_contact_version_conflict",
                "Kontakt je u međuvremenu izmenjen",
            )

        proposed = self._contact_changes(data)
        email = proposed.get("email", contact.email)
        phone = proposed.get("phone", contact.phone)
        self.validation.require_contact_channel(
            email if isinstance(email, (str, type(None))) else contact.email,
            phone if isinstance(phone, (str, type(None))) else contact.phone,
        )
        target_type = proposed.get("contact_type", contact.contact_type)
        target_primary = proposed.get("is_primary", contact.is_primary)
        if target_primary is True:
            assert isinstance(target_type, str)
            await self._ensure_primary_available(
                supplier_id,
                target_type,
                contact_id=contact.id,
            )

        changes = {
            field: value
            for field, value in proposed.items()
            if getattr(contact, field) != value
        }
        if changes:
            changes["version"] = contact.version + 1
        try:
            if changes:
                await self.repository.update_contact(contact, changes)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self.validation.raise_contact_integrity(exc)
        except StaleDataError:
            await self.session.rollback()
            supplier_error(
                409,
                "supplier_contact_version_conflict",
                "Kontakt je u međuvremenu izmenjen",
            )
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(contact)
        return contact

    async def deactivate_contact(
        self,
        supplier_id: uuid.UUID,
        contact_id: uuid.UUID,
    ) -> None:
        await self._get_supplier(supplier_id)
        contact = await self.repository.get_contact(
            supplier_id,
            contact_id,
            for_update=True,
        )
        if contact is None:
            supplier_error(
                404,
                "supplier_contact_not_found",
                "Kontakt dobavljača nije pronađen",
            )
        if not contact.is_active:
            return
        try:
            await self.repository.update_contact(
                contact,
                {
                    "is_active": False,
                    "is_primary": False,
                    "version": contact.version + 1,
                },
            )
            await self.session.commit()
        except StaleDataError:
            await self.session.rollback()
            supplier_error(
                409,
                "supplier_contact_version_conflict",
                "Kontakt je u međuvremenu izmenjen",
            )
        except Exception:
            await self.session.rollback()
            raise

    async def _get_supplier(self, supplier_id: uuid.UUID) -> Supplier:
        supplier = await self.repository.get_supplier(supplier_id)
        if supplier is None:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        return supplier

    async def _ensure_primary_available(
        self,
        supplier_id: uuid.UUID,
        contact_type: str,
        *,
        contact_id: uuid.UUID | None = None,
    ) -> None:
        existing = await self.repository.get_active_primary_contact(
            supplier_id,
            contact_type,
        )
        if existing is not None and existing.id != contact_id:
            supplier_error(
                409,
                "supplier_contact_primary_conflict",
                "Aktivan glavni kontakt za tu vrstu već postoji",
            )

    def _contact_changes(
        self,
        data: SupplierContactUpdate,
    ) -> dict[str, object]:
        supplied = data.model_fields_set - {"version"}
        proposed: dict[str, object] = {}
        if "contact_type" in supplied:
            assert data.contact_type is not None
            proposed["contact_type"] = data.contact_type.value
        if "name" in supplied:
            assert data.name is not None
            proposed["name"] = self.validation.required(data.name, "Ime kontakta")
        if "email" in supplied:
            proposed["email"] = self.validation.email(data.email)
        if "phone" in supplied:
            proposed["phone"] = self.validation.phone(data.phone)
        if "position" in supplied:
            proposed["position"] = self.validation.optional(data.position)
        if "is_primary" in supplied:
            assert data.is_primary is not None
            proposed["is_primary"] = data.is_primary
        return proposed


__all__ = ["SupplierContactService"]
