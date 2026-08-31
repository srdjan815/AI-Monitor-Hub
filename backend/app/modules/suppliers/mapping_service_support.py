from __future__ import annotations

import re
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.mapping_profile_models import SupplierMappingProfile
from app.modules.suppliers.mapping_profile_repository import SupplierMappingRepository
from app.modules.suppliers.schema_profile_repository import SupplierSchemaRepository
from app.modules.suppliers.source_repository import SupplierSourceRepository


class SupplierMappingServiceSupport:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierMappingRepository(session)
        self.schemas = SupplierSchemaRepository(session)
        self.sources = SupplierSourceRepository(session)

    async def _lineage(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
    ) -> None:
        source = await self.sources.get_source(supplier_id, source_id)
        if source is None:
            supplier_error(404, "supplier_source_not_found", "Izvor nije pronađen")
        schema = await self.schemas.get_profile(source_id, schema_profile_id)
        if schema is None:
            supplier_error(
                404, "schema_profile_not_found", "Schema Profile nije pronađen"
            )

    async def _usable_schema(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        *,
        require_active: bool = False,
    ) -> None:
        source = await self.sources.get_source(supplier_id, source_id)
        if source is None:
            supplier_error(404, "supplier_source_not_found", "Izvor nije pronađen")
        if not source.is_active:
            supplier_error(
                409,
                "mapping_profile_source_inactive",
                "Mapping Profile zahteva aktivan Source Connection",
            )
        schema = await self.schemas.get_profile(source_id, schema_profile_id)
        if schema is None:
            supplier_error(
                404, "schema_profile_not_found", "Schema Profile nije pronađen"
            )
        if not schema.is_active or schema.status not in {"DRAFT", "ACTIVE"}:
            supplier_error(
                409,
                "mapping_profile_schema_inactive",
                "Mapping Profile zahteva DRAFT ili ACTIVE Schema Profile",
            )
        if require_active and schema.status != "ACTIVE":
            supplier_error(
                409,
                "mapping_profile_schema_not_active",
                "Pre aktiviranja Mapping-a prvo aktivirajte Schema Profile.",
            )

    async def _profile(
        self,
        schema_profile_id: uuid.UUID,
        mapping_profile_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierMappingProfile:
        profile = await self.repository.get_profile(
            schema_profile_id,
            mapping_profile_id,
            for_update=for_update,
        )
        if profile is None:
            supplier_error(
                404,
                "mapping_profile_not_found",
                "Mapping Profile nije pronađen",
            )
        return profile

    @staticmethod
    def _draft(profile: SupplierMappingProfile) -> None:
        if not profile.is_active or profile.status != "DRAFT":
            supplier_error(
                409,
                "mapping_profile_immutable",
                "Samo DRAFT Mapping Profile može biti izmenjen",
            )

    @staticmethod
    def _version(actual: int, expected: int) -> None:
        if actual != expected:
            supplier_error(
                409,
                "mapping_profile_version_conflict",
                "Zapis je u međuvremenu izmenjen",
            )

    @staticmethod
    def _name(value: str) -> str:
        normalized = re.sub(r"\s+", " ", value.strip())
        if not normalized:
            supplier_error(422, "mapping_profile_invalid", "Naziv ne sme biti prazan")
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
        errors = {
            "active_schema": (
                "mapping_profile_active_conflict",
                "Schema Profile već ima aktivnu Mapping Profile verziju",
            ),
            "schema_name_version": (
                "mapping_profile_version_conflict",
                "Verzija mapiranja sa tim nazivom već postoji",
            ),
            "active_field": (
                "mapping_rule_field_conflict",
                "Schema Field je već mapiran",
            ),
            "active_target": (
                "mapping_rule_target_conflict",
                "Ciljni atribut je već mapiran",
            ),
            "active_priority": (
                "mapping_rule_priority_conflict",
                "Prioritet već postoji",
            ),
        }
        for marker, (code, message) in errors.items():
            if marker in constraint:
                supplier_error(409, code, message)
        supplier_error(409, "mapping_profile_conflict", "Konflikt mapiranja")


__all__ = ["SupplierMappingServiceSupport"]
