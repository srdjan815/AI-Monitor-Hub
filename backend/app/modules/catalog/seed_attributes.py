from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.modules.catalog.attribute_service import ProductAttributeService
from app.modules.catalog.enums import AttributeScope, AttributeStorageKind
from app.modules.catalog.schemas.product_attributes import (
    AttributeDefinitionCreate,
    AttributeGroupCreate,
)
from app.modules.catalog.utils import stable_code

GROUPS = (
    ("Osnovne informacije", "basic-information", 10),
    ("Fizičke karakteristike", "physical-characteristics", 20),
    ("Namena i preporuke", "purpose-and-recommendations", 30),
    ("Pakovanje", "packaging", 40),
    ("Sadržaj i dodatni linkovi", "content-and-links", 50),
)

GLOBAL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "Naziv proizvoda",
        "slug": "product_name",
        "scope": "SYSTEM",
        "storage_kind": "CORE_FIELD",
        "source_path": "Product.name",
    },
    {
        "name": "Proizvođač",
        "slug": "manufacturer",
        "scope": "SYSTEM",
        "storage_kind": "RELATION",
        "source_path": "Product.manufacturer",
    },
    {
        "name": "Part Number / MPN",
        "slug": "mpn",
        "scope": "SYSTEM",
        "storage_kind": "CORE_FIELD",
        "source_path": "Product.mpn",
    },
    {
        "name": "SKU",
        "slug": "sku",
        "scope": "SYSTEM",
        "storage_kind": "CORE_FIELD",
        "source_path": "Product.sku",
    },
    {
        "name": "EAN",
        "slug": "ean",
        "scope": "SYSTEM",
        "storage_kind": "CORE_FIELD",
        "source_path": "Product.ean",
    },
    {
        "name": "ID proizvoda / Šifra proizvoda",
        "slug": "product_code",
        "scope": "SYSTEM",
        "storage_kind": "CORE_FIELD",
        "source_path": "Product.code",
    },
    {
        "name": "Kategorija proizvoda",
        "slug": "category",
        "scope": "SYSTEM",
        "storage_kind": "CATEGORY_PATH",
        "source_path": "Category.path",
    },
    {
        "name": "Podkategorija proizvoda 1",
        "slug": "subcategory_level_1",
        "scope": "SYSTEM",
        "storage_kind": "CATEGORY_PATH",
        "source_path": "Category.path[1]",
    },
    {
        "name": "Podkategorija proizvoda 2",
        "slug": "subcategory_level_2",
        "scope": "SYSTEM",
        "storage_kind": "CATEGORY_PATH",
        "source_path": "Category.path[2]",
    },
    {"name": "Garantni rok", "slug": "warranty"},
    {
        "name": "Dimenzije uređaja",
        "slug": "device_dimensions",
        "data_type": "DIMENSION",
    },
    {"name": "Težina uređaja", "slug": "device_weight", "data_type": "WEIGHT"},
    {"name": "Namena", "slug": "intended_use"},
    {"name": "Potrošnja uređaja", "slug": "power_consumption", "data_type": "POWER"},
    {"name": "Preporučeno za", "slug": "recommended_for"},
    {"name": "Boja", "slug": "color"},
    {
        "name": "Težina upakovanog uređaja",
        "slug": "packaged_weight",
        "data_type": "WEIGHT",
    },
    {
        "name": "Dimenzije upakovanog uređaja",
        "slug": "package_dimensions",
        "data_type": "DIMENSION",
    },
    {"name": "Serija", "slug": "series"},
    {"name": "Sadržaj pakovanja", "slug": "package_contents", "data_type": "LONG_TEXT"},
    {"name": "Materijal uređaja", "slug": "material"},
    {"name": "Mini tekst", "slug": "mini_text", "storage_kind": "CONTENT_FIELD"},
    {
        "name": "Landing page",
        "slug": "landing_page",
        "storage_kind": "CONTENT_FIELD",
        "data_type": "URL",
    },
    {
        "name": "YouTube video",
        "slug": "youtube_video",
        "storage_kind": "CONTENT_FIELD",
        "data_type": "URL",
    },
    {
        "name": "Link ka sajtu proizvođača",
        "slug": "manufacturer_url",
        "storage_kind": "CONTENT_FIELD",
        "data_type": "URL",
    },
)


async def seed_global_attributes(session: AsyncSession) -> dict[str, int]:
    service = ProductAttributeService(session)
    created_groups = 0
    created_definitions = 0
    group_ids = {}
    for name, slug, sort_order in GROUPS:
        group = await service.repository.group_by_slug(stable_code(slug))
        if group is None:
            group = await service.create_group(
                AttributeGroupCreate(name=name, slug=slug, sort_order=sort_order)
            )
            created_groups += 1
        group_ids[slug] = group.id

    for order, config in enumerate(GLOBAL_DEFINITIONS):
        slug = config["slug"]
        existing = await service.repository.definition_by_identity(slug)
        storage = AttributeStorageKind(config.get("storage_kind", "ATTRIBUTE_VALUE"))
        group_slug = (
            "content-and-links"
            if storage == AttributeStorageKind.CONTENT_FIELD
            else "basic-information"
        )
        if existing:
            expected = {
                "name": config["name"],
                "scope": config.get("scope", "GLOBAL"),
                "storage_kind": storage.value,
                "source_path": config.get("source_path"),
                "group_id": group_ids[group_slug],
                "default_sort_order": order * 10,
            }
            changes = {
                key: value
                for key, value in expected.items()
                if getattr(existing, key) != value
            }
            if changes:
                changes["version"] = existing.version + 1
                await service.repository.mutate(existing, changes)
                await service._event("ATTRIBUTE_DEFINITION", existing.id, "SEEDED")
                await service._commit(existing)
            continue
        await service.create_definition(
            AttributeDefinitionCreate(
                name=config["name"],
                slug=slug,
                internal_name=slug,
                api_name=slug,
                group_id=group_ids[group_slug],
                scope=AttributeScope(config.get("scope", "GLOBAL")),
                storage_kind=storage,
                data_type=config.get("data_type", "TEXT"),
                source_path=config.get("source_path"),
                default_sort_order=order * 10,
                show_in_mini_specification=order < 10,
            )
        )
        created_definitions += 1
    return {
        "groups_created": created_groups,
        "definitions_created": created_definitions,
    }


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await seed_global_attributes(session)
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
