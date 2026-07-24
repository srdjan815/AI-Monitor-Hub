from __future__ import annotations

import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.core.security import current_actor_id
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.schema_profile_models import (
    SupplierSchemaField,
    SupplierSchemaProfile,
)
from app.modules.suppliers.schema_profile_schemas import (
    SchemaProfileAction,
    SchemaProfileClone,
    SchemaProfileCreate,
    SchemaProfileUpdate,
)
from app.modules.suppliers.schema_service_support import SupplierSchemaServiceSupport

logger = logging.getLogger(__name__)


class SupplierSchemaProfileService(SupplierSchemaServiceSupport):
    """Transaction owner for profile versions and lifecycle."""

    async def list_profiles(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        *,
        active_only: bool = True,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SupplierSchemaProfile], int]:
        await self._source(supplier_id, source_id)
        return await self.repository.list_profiles(
            source_id,
            active_only=active_only,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def get_profile(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
    ) -> SupplierSchemaProfile:
        await self._source(supplier_id, source_id)
        return await self._profile(source_id, profile_id)

    async def create_profile(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        data: SchemaProfileCreate,
    ) -> SupplierSchemaProfile:
        await self._usable_source(supplier_id, source_id)
        name = self._name(data.name)
        number = await self.repository.next_version_number(source_id, name)
        profile = SupplierSchemaProfile(
            source_connection_id=source_id,
            name=name,
            description=self._optional(data.description),
            version_number=number,
            status="DRAFT",
            is_active=True,
            field_count=0,
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
        logger.info(
            "Schema profile created: profile_id=%s source_id=%s actor=%s",
            profile.id,
            source_id,
            current_actor_id(),
        )
        return profile

    async def update_profile(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
        data: SchemaProfileUpdate,
    ) -> SupplierSchemaProfile:
        await self._usable_source(supplier_id, source_id)
        profile = await self._profile(source_id, profile_id, for_update=True)
        self._draft(profile)
        self._version(profile.version, data.version)
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
            changes["version"] = profile.version + 1
        try:
            if changes:
                await self.repository.mutate(profile, changes)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._integrity(exc)
        except StaleDataError:
            await self.session.rollback()
            supplier_error(
                409,
                "schema_profile_version_conflict",
                "Zapis je u međuvremenu izmenjen",
            )
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(profile)
        return profile

    async def clone_profile(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
        data: SchemaProfileClone,
    ) -> SupplierSchemaProfile:
        await self._usable_source(supplier_id, source_id)
        original = await self._profile(source_id, profile_id, for_update=True)
        self._version(original.version, data.version)
        name = self._name(data.name or original.name)
        clone = SupplierSchemaProfile(
            source_connection_id=source_id,
            name=name,
            description=(
                self._optional(data.description)
                if "description" in data.model_fields_set
                else original.description
            ),
            version_number=await self.repository.next_version_number(source_id, name),
            status="DRAFT",
            is_active=True,
            field_count=original.field_count,
        )
        try:
            await self.repository.add(clone)
            for field in await self.repository.list_fields(original.id):
                await self.repository.add(self._clone_field(field, clone.id))
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
        profile_id: uuid.UUID,
        data: SchemaProfileAction,
    ) -> SupplierSchemaProfile:
        await self._usable_source(supplier_id, source_id)
        profile = await self._profile(source_id, profile_id, for_update=True)
        self._draft(profile)
        self._version(profile.version, data.version)
        if profile.field_count == 0:
            supplier_error(
                409,
                "schema_profile_empty",
                "Prazan Schema Profile ne može biti aktiviran",
            )
        current = await self.repository.active_profile(source_id, for_update=True)
        try:
            if current is not None and current.id != profile.id:
                await self.repository.mutate(
                    current,
                    {"status": "ARCHIVED", "version": current.version + 1},
                )
            await self.repository.mutate(
                profile,
                {"status": "ACTIVE", "version": profile.version + 1},
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._integrity(exc)
        except StaleDataError:
            await self.session.rollback()
            supplier_error(
                409,
                "schema_profile_version_conflict",
                "Zapis je u međuvremenu izmenjen",
            )
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(profile)
        return profile

    async def archive_profile(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
        data: SchemaProfileAction,
    ) -> SupplierSchemaProfile:
        await self._usable_source(supplier_id, source_id)
        profile = await self._profile(source_id, profile_id, for_update=True)
        self._version(profile.version, data.version)
        if profile.status != "ARCHIVED":
            await self._mutate_commit(profile, {"status": "ARCHIVED"})
        return profile

    async def deactivate_profile(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
    ) -> None:
        await self._usable_source(supplier_id, source_id)
        profile = await self._profile(source_id, profile_id, for_update=True)
        if not profile.is_active:
            return
        await self._mutate_commit(
            profile,
            {"is_active": False, "status": "ARCHIVED"},
        )

    async def _mutate_commit(
        self,
        profile: SupplierSchemaProfile,
        changes: dict[str, object],
    ) -> None:
        changes["version"] = profile.version + 1
        try:
            await self.repository.mutate(profile, changes)
            await self.session.commit()
        except StaleDataError:
            await self.session.rollback()
            supplier_error(
                409,
                "schema_profile_version_conflict",
                "Zapis je u međuvremenu izmenjen",
            )
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(profile)

    @staticmethod
    def _clone_field(
        field: SupplierSchemaField,
        profile_id: uuid.UUID,
    ) -> SupplierSchemaField:
        values = {
            column.name: getattr(field, column.name)
            for column in SupplierSchemaField.__table__.columns
            if column.name
            not in {"id", "schema_profile_id", "created_at", "updated_at", "version"}
        }
        return SupplierSchemaField(schema_profile_id=profile_id, version=1, **values)


__all__ = ["SupplierSchemaProfileService"]
