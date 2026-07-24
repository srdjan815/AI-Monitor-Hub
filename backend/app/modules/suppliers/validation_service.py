from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.modules.suppliers.enums import SupplierStatus
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.repository import SupplierRepository


class SupplierValidationService:
    """Shared Supplier normalization and conflict validation."""

    def __init__(self, repository: SupplierRepository) -> None:
        self.repository = repository

    async def ensure_identifiers_unique(
        self,
        *,
        tax_identifier: str | None,
        registration_number: str | None,
        supplier_id: uuid.UUID | None = None,
    ) -> None:
        if tax_identifier is not None:
            existing = await self.repository.get_supplier_by_tax_identifier(
                tax_identifier
            )
            if existing is not None and existing.id != supplier_id:
                supplier_error(
                    409,
                    "supplier_tax_identifier_conflict",
                    "Aktivan dobavljač sa tim poreskim identifikatorom već postoji",
                )
        if registration_number is not None:
            existing = await self.repository.get_supplier_by_registration_number(
                registration_number
            )
            if existing is not None and existing.id != supplier_id:
                supplier_error(
                    409,
                    "supplier_registration_number_conflict",
                    "Aktivan dobavljač sa tim registracionim brojem već postoji",
                )

    @staticmethod
    def validate_status_transition(current: str, target: str) -> None:
        allowed = {
            SupplierStatus.ACTIVE.value: {
                SupplierStatus.INACTIVE.value,
                SupplierStatus.SUSPENDED.value,
            },
            SupplierStatus.INACTIVE.value: {
                SupplierStatus.ACTIVE.value,
                SupplierStatus.SUSPENDED.value,
            },
            SupplierStatus.SUSPENDED.value: {
                SupplierStatus.ACTIVE.value,
                SupplierStatus.INACTIVE.value,
            },
        }
        if target != current and target not in allowed[current]:
            supplier_error(
                409,
                "supplier_invalid_status_transition",
                "Promena statusa dobavljača nije dozvoljena",
            )

    @staticmethod
    def required(value: str, label: str) -> str:
        normalized = re.sub(r"\s+", " ", value.strip())
        if not normalized:
            supplier_error(
                422,
                "supplier_contact_invalid"
                if label == "Ime kontakta"
                else "supplier_invalid",
                f"{label} ne sme biti prazan",
            )
        return normalized

    @staticmethod
    def optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = re.sub(r"\s+", " ", value.strip())
        return normalized or None

    @classmethod
    def identifier(cls, value: str | None) -> str | None:
        normalized = cls.optional(value)
        return normalized.upper() if normalized is not None else None

    @classmethod
    def email(cls, value: str | None) -> str | None:
        normalized = cls.optional(value)
        return normalized.lower() if normalized is not None else None

    @classmethod
    def phone(cls, value: str | None) -> str | None:
        return cls.optional(value)

    @staticmethod
    def require_contact_channel(
        email: str | None,
        phone: str | None,
    ) -> None:
        if email is None and phone is None:
            supplier_error(
                422,
                "supplier_contact_invalid",
                "Kontakt mora imati email ili telefon",
            )

    @staticmethod
    def _constraint_name(exc: IntegrityError) -> str:
        current: Any = exc.orig
        for _ in range(3):
            name = getattr(current, "constraint_name", None)
            if isinstance(name, str):
                return name
            current = getattr(current, "__cause__", None)
            if current is None:
                break
        return str(exc.orig)

    @classmethod
    def raise_supplier_integrity(cls, exc: IntegrityError) -> None:
        constraint = cls._constraint_name(exc)
        if "tax_identifier" in constraint:
            supplier_error(
                409,
                "supplier_tax_identifier_conflict",
                "Aktivan dobavljač sa tim poreskim identifikatorom već postoji",
            )
        if "registration_number" in constraint:
            supplier_error(
                409,
                "supplier_registration_number_conflict",
                "Aktivan dobavljač sa tim registracionim brojem već postoji",
            )
        supplier_error(
            409,
            "supplier_code_conflict",
            "Interna šifra dobavljača već postoji",
        )

    @classmethod
    def raise_contact_integrity(cls, exc: IntegrityError) -> None:
        constraint = cls._constraint_name(exc)
        if "active_primary" in constraint:
            supplier_error(
                409,
                "supplier_contact_primary_conflict",
                "Aktivan glavni kontakt za tu vrstu već postoji",
            )
        supplier_error(
            409,
            "supplier_contact_invalid",
            "Kontakt dobavljača nije validan",
        )


__all__ = ["SupplierValidationService"]
