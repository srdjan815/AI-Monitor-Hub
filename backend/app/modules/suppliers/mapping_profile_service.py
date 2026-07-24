from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.mapping_profile_models import (
    SupplierMappingProfile,
    SupplierMappingRule,
)
from app.modules.suppliers.mapping_profile_schemas import (
    MappingProfileAction,
    MappingProfileClone,
    MappingProfileCreate,
    MappingProfileUpdate,
)
from app.modules.suppliers.mapping_service_support import (
    SupplierMappingServiceSupport,
)


class SupplierMappingProfileService(SupplierMappingServiceSupport):
    """Transaction owner for Mapping Profile versions."""

    async def list_profiles(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        *,
        active_only: bool = True,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SupplierMappingProfile], int]:
        await self._lineage(supplier_id, source_id, schema_profile_id)
        return await self.repository.list_profiles(
            schema_profile_id,
            active_only=active_only,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def get_profile(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        mapping_profile_id: uuid.UUID,
    ) -> SupplierMappingProfile:
        await self._lineage(supplier_id, source_id, schema_profile_id)
        return await self._profile(schema_profile_id, mapping_profile_id)

    async def create_profile(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        data: MappingProfileCreate,
    ) -> SupplierMappingProfile:
        await self._usable_schema(supplier_id, source_id, schema_profile_id)
        name = self._name(data.name)
        profile = SupplierMappingProfile(
            schema_profile_id=schema_profile_id,
            name=name,
            description=self._optional(data.description),
            version_number=await self.repository.next_version_number(
                schema_profile_id,
                name,
            ),
            status="DRAFT",
            is_active=True,
            rule_count=0,
        )
        try:
            await self.repository.add(profile)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._integrity(exc)
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(profile)
        return profile

    async def update_profile(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        mapping_profile_id: uuid.UUID,
        data: MappingProfileUpdate,
    ) -> SupplierMappingProfile:
        await self._usable_schema(supplier_id, source_id, schema_profile_id)
        profile = await self._profile(
            schema_profile_id,
            mapping_profile_id,
            for_update=True,
        )
        self._draft(profile)
        self._version(profile.optimistic_version, data.optimistic_version)
        changes: dict[str, object] = {}
        if "name" in data.model_fields_set and data.name is not None:
            changes["name"] = self._name(data.name)
        if "description" in data.model_fields_set:
            changes["description"] = self._optional(data.description)
        changes = {
            key: value
            for key, value in changes.items()
            if getattr(profile, key) != value
        }
        if changes:
            changes["optimistic_version"] = profile.optimistic_version + 1
        await self._commit(profile, changes)
        return profile

    async def clone_profile(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        mapping_profile_id: uuid.UUID,
        data: MappingProfileClone,
    ) -> SupplierMappingProfile:
        await self._usable_schema(supplier_id, source_id, schema_profile_id)
        original = await self._profile(
            schema_profile_id,
            mapping_profile_id,
            for_update=True,
        )
        self._version(original.optimistic_version, data.optimistic_version)
        name = self._name(data.name or original.name)
        clone = SupplierMappingProfile(
            schema_profile_id=schema_profile_id,
            name=name,
            description=(
                self._optional(data.description)
                if "description" in data.model_fields_set
                else original.description
            ),
            version_number=await self.repository.next_version_number(
                schema_profile_id,
                name,
            ),
            status="DRAFT",
            is_active=True,
            rule_count=original.rule_count,
        )
        try:
            await self.repository.add(clone)
            for rule in await self.repository.list_rules(original.id):
                await self.repository.add(self._clone_rule(rule, clone.id))
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._integrity(exc)
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(clone)
        return clone

    async def activate_profile(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        mapping_profile_id: uuid.UUID,
        data: MappingProfileAction,
    ) -> SupplierMappingProfile:
        await self._usable_schema(supplier_id, source_id, schema_profile_id)
        profile = await self._profile(
            schema_profile_id,
            mapping_profile_id,
            for_update=True,
        )
        self._draft(profile)
        self._version(profile.optimistic_version, data.optimistic_version)
        if profile.rule_count == 0:
            supplier_error(
                409,
                "mapping_profile_empty",
                "Prazan Mapping Profile ne može biti aktiviran",
            )
        current = await self.repository.active_profile(
            schema_profile_id,
            for_update=True,
        )
        try:
            if current is not None and current.id != profile.id:
                await self.repository.mutate(
                    current,
                    {
                        "status": "ARCHIVED",
                        "optimistic_version": current.optimistic_version + 1,
                    },
                )
            await self.repository.mutate(
                profile,
                {
                    "status": "ACTIVE",
                    "optimistic_version": profile.optimistic_version + 1,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._integrity(exc)
        except StaleDataError:
            await self.session.rollback()
            self._stale()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(profile)
        return profile

    async def archive_profile(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        mapping_profile_id: uuid.UUID,
        data: MappingProfileAction,
    ) -> SupplierMappingProfile:
        await self._lineage(supplier_id, source_id, schema_profile_id)
        profile = await self._profile(
            schema_profile_id,
            mapping_profile_id,
            for_update=True,
        )
        self._version(profile.optimistic_version, data.optimistic_version)
        if profile.status != "ARCHIVED":
            await self._commit(profile, {"status": "ARCHIVED"})
        return profile

    async def deactivate_profile(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        mapping_profile_id: uuid.UUID,
    ) -> None:
        await self._lineage(supplier_id, source_id, schema_profile_id)
        profile = await self._profile(
            schema_profile_id,
            mapping_profile_id,
            for_update=True,
        )
        if profile.is_active:
            await self._commit(
                profile,
                {"is_active": False, "status": "ARCHIVED"},
            )

    async def _commit(
        self,
        profile: SupplierMappingProfile,
        changes: dict[str, object],
    ) -> None:
        if changes:
            changes.setdefault(
                "optimistic_version",
                profile.optimistic_version + 1,
            )
        try:
            if changes:
                await self.repository.mutate(profile, changes)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._integrity(exc)
        except StaleDataError:
            await self.session.rollback()
            self._stale()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(profile)

    @staticmethod
    def _stale() -> None:
        supplier_error(
            409,
            "mapping_profile_version_conflict",
            "Mapping Profile je u međuvremenu izmenjen",
        )

    @staticmethod
    def _clone_rule(
        rule: SupplierMappingRule,
        profile_id: uuid.UUID,
    ) -> SupplierMappingRule:
        values = {
            column.name: getattr(rule, column.name)
            for column in SupplierMappingRule.__table__.columns
            if column.name
            not in {"id", "mapping_profile_id", "created_at", "updated_at", "version"}
        }
        return SupplierMappingRule(
            mapping_profile_id=profile_id,
            optimistic_version=1,
            **values,
        )


__all__ = ["SupplierMappingProfileService"]
