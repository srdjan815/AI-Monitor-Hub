from __future__ import annotations

import re
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.schema_profile_models import SupplierSchemaProfile
from app.modules.suppliers.schema_profile_repository import SupplierSchemaRepository
from app.modules.suppliers.source_repository import SupplierSourceRepository


class SupplierSchemaServiceSupport:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierSchemaRepository(session)
        self.sources = SupplierSourceRepository(session)

    async def _source(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> None:
        source = await self.sources.get_source(supplier_id, source_id)
        if source is None:
            supplier_error(
                404,
                "supplier_source_not_found",
                "Izvor dobavljača nije pronađen",
            )

    async def _usable_source(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> None:
        source = await self.sources.get_source(supplier_id, source_id)
        if source is None:
            supplier_error(
                404,
                "supplier_source_not_found",
                "Izvor dobavljača nije pronađen",
            )
        if not source.is_active:
            supplier_error(
                409,
                "schema_profile_source_inactive",
                "Schema Profile zahteva aktivan Source Connection zapis",
            )

    async def _profile(
        self,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierSchemaProfile:
        profile = await self.repository.get_profile(
            source_id,
            profile_id,
            for_update=for_update,
        )
        if profile is None:
            supplier_error(
                404,
                "schema_profile_not_found",
                "Schema Profile nije pronađen",
            )
        return profile

    @staticmethod
    def _draft(profile: SupplierSchemaProfile) -> None:
        if not profile.is_active or profile.status != "DRAFT":
            supplier_error(
                409,
                "schema_profile_immutable",
                "Samo DRAFT verzija može menjati strukturu",
            )

    @staticmethod
    def _name(value: str) -> str:
        normalized = re.sub(r"\s+", " ", value.strip())
        if not normalized:
            supplier_error(422, "schema_profile_invalid", "Naziv ne sme biti prazan")
        return normalized

    @staticmethod
    def _optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = re.sub(r"\s+", " ", value.strip())
        return normalized or None

    @staticmethod
    def _constraint(exc: IntegrityError) -> str:
        value = getattr(exc.orig, "constraint_name", None)
        return value if isinstance(value, str) else str(exc.orig)

    @classmethod
    def _integrity(cls, exc: IntegrityError) -> None:
        constraint = cls._constraint(exc)
        if "active_source" in constraint:
            supplier_error(
                409,
                "schema_profile_active_conflict",
                "Source Connection već ima aktivnu Schema Profile verziju",
            )
        if "source_name_version" in constraint:
            supplier_error(
                409,
                "schema_profile_version_conflict",
                "Verzija profila sa tim nazivom već postoji",
            )
        if "active_code" in constraint:
            supplier_error(
                409,
                "schema_field_code_conflict",
                "Šifra polja već postoji u verziji",
            )
        if "active_position" in constraint:
            supplier_error(
                409,
                "schema_field_position_conflict",
                "Pozicija polja već postoji u verziji",
            )
        if "active_key" in constraint:
            supplier_error(
                409,
                "schema_field_key_conflict",
                "Verzija može imati samo jedno ključno polje",
            )
        if "active_price" in constraint:
            supplier_error(
                409,
                "schema_field_price_conflict",
                "Verzija može imati samo jedno polje cene",
            )
        supplier_error(409, "schema_profile_conflict", "Konflikt Schema Profile zapisa")

    @staticmethod
    def _version(actual: int, expected: int) -> None:
        if actual != expected:
            supplier_error(
                409,
                "schema_profile_version_conflict",
                "Zapis je u međuvremenu izmenjen",
            )


__all__ = ["SupplierSchemaServiceSupport"]
