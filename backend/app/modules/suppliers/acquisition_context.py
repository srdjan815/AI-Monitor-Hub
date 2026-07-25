from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.mapping_profile_models import (
    SupplierMappingProfile,
    SupplierMappingRule,
)
from app.modules.suppliers.mapping_profile_repository import SupplierMappingRepository
from app.modules.suppliers.models import Supplier, SupplierSource
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.schema_profile_models import (
    SupplierSchemaField,
    SupplierSchemaProfile,
)
from app.modules.suppliers.schema_profile_repository import SupplierSchemaRepository
from app.modules.suppliers.source_repository import SupplierSourceRepository


@dataclass(frozen=True, slots=True)
class AcquisitionContext:
    supplier: Supplier
    source: SupplierSource
    schema: SupplierSchemaProfile
    fields: list[SupplierSchemaField]
    mapping: SupplierMappingProfile
    rules: list[SupplierMappingRule]


class AcquisitionContextResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.suppliers = SupplierRepository(session)
        self.sources = SupplierSourceRepository(session)
        self.schemas = SupplierSchemaRepository(session)
        self.mappings = SupplierMappingRepository(session)

    async def resolve(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> AcquisitionContext:
        supplier = await self.suppliers.get_supplier(supplier_id)
        if supplier is None:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        if not supplier.is_active or supplier.status != "ACTIVE":
            supplier_error(
                409,
                "acquisition_supplier_inactive",
                "Acquisition zahteva aktivnog dobavljača",
            )
        source = await self.sources.get_source(supplier_id, source_id)
        if source is None:
            supplier_error(404, "supplier_source_not_found", "Izvor nije pronađen")
        if not source.is_active or source.status != "ACTIVE":
            supplier_error(
                409,
                "acquisition_source_inactive",
                "Acquisition zahteva ACTIVE Source Connection",
            )
        schema = await self.schemas.active_profile(source_id)
        if schema is None:
            supplier_error(
                409,
                "acquisition_schema_missing",
                "Aktivni Schema Profile nije pronađen",
            )
        fields = await self.schemas.list_fields(schema.id)
        mapping = await self.mappings.active_profile(schema.id)
        if mapping is None:
            supplier_error(
                409,
                "acquisition_mapping_missing",
                "Kompatibilni aktivni Mapping Profile nije pronađen",
            )
        rules = await self.mappings.list_rules(mapping.id)
        if not fields or not rules:
            supplier_error(
                409,
                "acquisition_configuration_empty",
                "Aktivna šema i mapiranje moraju sadržati definicije",
            )
        return AcquisitionContext(
            supplier=supplier,
            source=source,
            schema=schema,
            fields=fields,
            mapping=mapping,
            rules=rules,
        )


__all__ = ["AcquisitionContext", "AcquisitionContextResolver"]
