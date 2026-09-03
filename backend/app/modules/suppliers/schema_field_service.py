from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.schema_field_schemas import (
    SchemaFieldCreate,
    SchemaFieldUpdate,
)
from app.modules.suppliers.schema_profile_models import SupplierSchemaField
from app.modules.suppliers.schema_service_support import SupplierSchemaServiceSupport


class SupplierSchemaFieldService(SupplierSchemaServiceSupport):
    """Transaction owner for DRAFT Schema Field metadata."""

    async def list_fields(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
        *,
        active_only: bool = True,
    ) -> list[SupplierSchemaField]:
        await self._source(supplier_id, source_id)
        await self._profile(source_id, profile_id)
        return await self.repository.list_fields(profile_id, active_only=active_only)

    async def get_field(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
        field_id: uuid.UUID,
    ) -> SupplierSchemaField:
        await self._source(supplier_id, source_id)
        await self._profile(source_id, profile_id)
        field = await self.repository.get_field(profile_id, field_id)
        if field is None:
            supplier_error(404, "schema_field_not_found", "Schema Field nije pronađen")
        return field

    async def create_field(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
        data: SchemaFieldCreate,
    ) -> SupplierSchemaField:
        await self._usable_source(supplier_id, source_id)
        profile = await self._profile(source_id, profile_id, for_update=True)
        self._draft(profile)
        values = self._values(data)
        await self._ensure_no_conflicts(profile_id, values)
        field = SupplierSchemaField(schema_profile_id=profile_id, **values)
        try:
            await self.repository.add(field)
            await self.repository.mutate(
                profile,
                {
                    "field_count": profile.field_count + 1,
                    "version": profile.version + 1,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._integrity(exc)
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(field)
        return field

    async def update_field(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
        field_id: uuid.UUID,
        data: SchemaFieldUpdate,
    ) -> SupplierSchemaField:
        await self._usable_source(supplier_id, source_id)
        profile = await self._profile(source_id, profile_id, for_update=True)
        self._draft(profile)
        field = await self.repository.get_field(profile_id, field_id, for_update=True)
        if field is None:
            supplier_error(404, "schema_field_not_found", "Schema Field nije pronađen")
        if not field.is_active:
            supplier_error(409, "schema_field_inactive", "Polje je arhivirano")
        self._version(field.version, data.version)
        supplied = data.model_dump(exclude_unset=True, exclude={"version"})
        current = {
            name: getattr(field, name) for name in SchemaFieldCreate.model_fields
        }
        current.update(supplied)
        values = self._values(SchemaFieldCreate.model_validate(current))
        await self._ensure_no_conflicts(profile_id, values, field.id)
        changes = {
            key: value for key, value in values.items() if getattr(field, key) != value
        }
        if changes:
            changes["version"] = field.version + 1
            changes_profile: dict[str, object] = {"version": profile.version + 1}
        try:
            if changes:
                await self.repository.mutate(field, changes)
                await self.repository.mutate(profile, changes_profile)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._integrity(exc)
        except StaleDataError:
            await self.session.rollback()
            supplier_error(
                409,
                "schema_field_version_conflict",
                "Polje je u međuvremenu izmenjeno",
            )
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(field)
        return field

    async def deactivate_field(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
        field_id: uuid.UUID,
    ) -> None:
        await self._usable_source(supplier_id, source_id)
        profile = await self._profile(source_id, profile_id, for_update=True)
        self._draft(profile)
        field = await self.repository.get_field(profile_id, field_id, for_update=True)
        if field is None:
            supplier_error(404, "schema_field_not_found", "Schema Field nije pronađen")
        if not field.is_active:
            return
        try:
            await self.repository.mutate(
                field,
                {"is_active": False, "version": field.version + 1},
            )
            await self.repository.mutate(
                profile,
                {
                    "field_count": profile.field_count - 1,
                    "version": profile.version + 1,
                },
            )
            await self.session.commit()
        except StaleDataError:
            await self.session.rollback()
            supplier_error(
                409,
                "schema_field_version_conflict",
                "Polje je u međuvremenu izmenjeno",
            )
        except Exception:
            await self.session.rollback()
            raise

    async def _ensure_no_conflicts(
        self,
        profile_id: uuid.UUID,
        values: dict[str, object],
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        conflicts = await self.repository.field_conflicts(
            profile_id,
            code=str(values["field_code"]),
            position=cast(int, values["position"]),
            is_key=bool(values["is_key"]),
            is_price=bool(values["is_price"]),
            exclude_id=exclude_id,
        )
        messages = {
            "code": ("schema_field_code_conflict", "Šifra polja već postoji"),
            "position": ("schema_field_position_conflict", "Pozicija već postoji"),
            "key": ("schema_field_key_conflict", "Ključno polje već postoji"),
            "price": ("schema_field_price_conflict", "Polje cene već postoji"),
        }
        if conflicts:
            code, message = messages[sorted(conflicts)[0]]
            supplier_error(409, code, message)

    @staticmethod
    def _values(data: SchemaFieldCreate) -> dict[str, object]:
        values = data.model_dump(exclude={"version"})
        values["field_code"] = str(values["field_code"]).strip()
        values["name"] = str(values["name"]).strip()
        values["data_type"] = data.data_type.value
        return values


__all__ = ["SupplierSchemaFieldService"]
