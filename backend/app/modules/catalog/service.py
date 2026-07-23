from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.enums import AttributeScope
from app.modules.catalog.models import AttributeDefinition, Category, Product
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    AttributeCreate,
    AttributeTypeCreate,
    AttributeTypeUpdate,
    AttributeUpdate,
    CategoryAttributeReorder,
    CategoryCreate,
    CategoryTree,
    CategoryUpdate,
    ProductCreate,
    ProductUpdate,
)
from app.modules.catalog.utils import stable_code


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CatalogRepository(session)

    async def _get_category_or_404(
        self,
        category_id: uuid.UUID,
    ) -> Category:
        category = await self.repository.get_category(category_id)

        if category is None:
            raise HTTPException(
                status_code=404,
                detail="Kategorija nije pronađena",
            )

        return category

    async def _validate_parent_category(
        self,
        *,
        category_id: uuid.UUID | None,
        parent_id: uuid.UUID | None,
    ) -> None:
        if parent_id is None:
            return

        if category_id is not None and parent_id == category_id:
            raise HTTPException(
                status_code=422,
                detail="Kategorija ne može biti sopstveni roditelj",
            )

        parent = await self.repository.get_category(parent_id)

        if parent is None:
            raise HTTPException(
                status_code=404,
                detail="Roditeljska kategorija ne postoji",
            )

        if category_id is None:
            return

        visited: set[uuid.UUID] = set()
        current: Category | None = parent

        while current is not None:
            if current.id == category_id:
                raise HTTPException(
                    status_code=422,
                    detail="Nije dozvoljena kružna hijerarhija kategorija",
                )

            if current.id in visited:
                raise HTTPException(
                    status_code=422,
                    detail="Otkrivena je neispravna hijerarhija kategorija",
                )

            visited.add(current.id)

            if current.parent_id is None:
                break

            current = await self.repository.get_category(current.parent_id)

    async def create_category(
        self,
        data: CategoryCreate,
    ) -> Category:
        name = data.name.strip()

        if not name:
            raise HTTPException(
                status_code=422,
                detail="Naziv kategorije ne sme biti prazan",
            )

        code = stable_code(data.code or name)

        if await self.repository.get_category_by_code(code):
            raise HTTPException(
                status_code=409,
                detail="Kod kategorije već postoji",
            )

        await self._validate_parent_category(
            category_id=None,
            parent_id=data.parent_id,
        )

        category = Category(
            name=name,
            code=code,
            parent_id=data.parent_id,
            position=data.position,
        )

        try:
            await self.repository.create_category(category)
            await self.repository.link_all_global_attributes(category.id)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Kategorija sa tim nazivom već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(category)
        return category

    async def update_category(
        self,
        category_id: uuid.UUID,
        data: CategoryUpdate,
    ) -> Category:
        category = await self._get_category_or_404(category_id)
        changes = data.model_dump(exclude_unset=True)

        if "name" in changes:
            name = changes["name"].strip()

            if not name:
                raise HTTPException(
                    status_code=422,
                    detail="Naziv kategorije ne sme biti prazan",
                )

            changes["name"] = name

        if "parent_id" in changes:
            await self._validate_parent_category(
                category_id=category_id,
                parent_id=changes["parent_id"],
            )

        actual_changes = {
            field: value
            for field, value in changes.items()
            if getattr(category, field) != value
        }

        if actual_changes:
            actual_changes["version"] = category.version + 1

        try:
            await self.repository.update_category(category, actual_changes)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Kategorija sa tim nazivom već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(category)
        return category

    async def deactivate_category(
        self,
        category_id: uuid.UUID,
    ) -> None:
        category = await self._get_category_or_404(category_id)

        if not category.is_active:
            return

        try:
            await self.repository.deactivate_category(category)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(category)

    async def get_category_tree(self) -> list[CategoryTree]:
        categories = await self.repository.list_all_categories()

        nodes: dict[uuid.UUID, CategoryTree] = {}

        for category in categories:
            nodes[category.id] = CategoryTree(
                id=category.id,
                name=category.name,
                code=category.code,
                parent_id=category.parent_id,
                position=category.position,
                is_active=category.is_active,
                children=[],
            )

        roots: list[CategoryTree] = []

        for node in nodes.values():
            if node.parent_id is None:
                roots.append(node)
                continue

            parent = nodes.get(node.parent_id)

            if parent is not None:
                parent.children.append(node)
            else:
                roots.append(node)

        return roots

    async def create_attribute(
        self,
        data: AttributeCreate,
    ) -> AttributeDefinition:
        name = data.name.strip()

        if not name:
            raise HTTPException(
                status_code=422,
                detail="Naziv atributa ne sme biti prazan",
            )

        code = stable_code(data.code or name)

        if await self.repository.get_attribute_by_code(code):
            raise HTTPException(
                status_code=409,
                detail="Kod atributa već postoji",
            )

        if (
            data.category_id is not None
            and not await self.repository.get_category(data.category_id)
        ):
            raise HTTPException(
                status_code=404,
                detail="Kategorija nije pronađena",
            )

        attribute = AttributeDefinition(
            name=name,
            code=code,
            scope=data.scope.value,
            data_type=data.data_type.value,
            unit=data.unit,
            description=data.description,
            ai_prompt=data.ai_prompt,
            example_value=data.example_value,
            validation_rules=data.validation_rules,
            api_name=stable_code(data.api_name or code),
            is_required=data.is_required,
            is_visible=data.is_visible,
            is_filterable=data.is_filterable,
            is_searchable=data.is_searchable,
            allows_multiple=data.allows_multiple,
        )

        try:
            await self.repository.create_attribute(attribute)

            if data.scope == AttributeScope.GLOBAL:
                await self.repository.link_global_attribute_to_all_categories(
                    attribute.id
                )
            else:
                await self.repository.link_attribute(
                    category_id=data.category_id,
                    attribute_id=attribute.id,
                    position=data.position,
                    group_name=data.group_name,
                )

            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Atribut već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(attribute)
        return attribute

    async def update_attribute(
        self,
        attribute_id: uuid.UUID,
        data: AttributeUpdate,
    ) -> AttributeDefinition:
        attribute = await self.repository.get_attribute(attribute_id)

        if attribute is None:
            raise HTTPException(
                status_code=404,
                detail="Atribut nije pronađen",
            )

        changes = data.model_dump(exclude_unset=True)

        if "name" in changes:
            name = changes["name"].strip()

            if not name:
                raise HTTPException(
                    status_code=422,
                    detail="Naziv atributa ne sme biti prazan",
                )

            changes["name"] = name

        if "data_type" in changes and changes["data_type"] is not None:
            changes["data_type"] = changes["data_type"].value

        actual_changes = {
            field: value
            for field, value in changes.items()
            if getattr(attribute, field) != value
        }

        if actual_changes:
            actual_changes["version"] = attribute.version + 1

        try:
            await self.repository.update_attribute(attribute, actual_changes)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Atribut već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(attribute)
        return attribute

    async def reorder_category_attributes(
        self,
        category_id: uuid.UUID,
        data: CategoryAttributeReorder,
    ) -> None:
        if not await self.repository.get_category(category_id):
            raise HTTPException(
                status_code=404,
                detail="Kategorija nije pronađena",
            )

        try:
            for item in data.items:
                link = await self.repository.get_category_attribute(
                    category_id,
                    item.attribute_id,
                )

                if link is None:
                    raise HTTPException(
                        status_code=404,
                        detail=(
                            f"Atribut {item.attribute_id} "
                            "nije povezan sa kategorijom"
                        ),
                    )

                await self.repository.update_category_attribute(
                    link,
                    position=item.position,
                    group_name=item.group_name,
                )

            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def list_attribute_types(
        self,
        *,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AttributeDefinition], int]:
        return await self.repository.list_attribute_types(
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

    async def _get_attribute_type_or_404(
        self,
        attribute_type_id: uuid.UUID,
    ) -> AttributeDefinition:
        attribute_type = await self.repository.get_attribute_type(
            attribute_type_id
        )

        if attribute_type is None:
            raise HTTPException(
                status_code=404,
                detail="Tip atributa nije pronađen",
            )

        return attribute_type

    async def get_attribute_type(
        self,
        attribute_type_id: uuid.UUID,
    ) -> AttributeDefinition:
        return await self._get_attribute_type_or_404(attribute_type_id)

    async def create_attribute_type(
        self,
        data: AttributeTypeCreate,
    ) -> AttributeDefinition:
        name = data.name.strip()

        if not name:
            raise HTTPException(
                status_code=422,
                detail="Naziv tipa atributa ne sme biti prazan",
            )

        code = stable_code(data.code or name)

        if await self.repository.get_attribute_type_by_code(code):
            raise HTTPException(
                status_code=409,
                detail="Kod tipa atributa već postoji",
            )

        attribute_type = AttributeDefinition(
            name=name,
            code=code,
            scope=data.scope.value,
            data_type=data.data_type.value,
            unit=self._normalize_optional(data.unit),
            description=self._normalize_optional(data.description),
            ai_prompt=self._normalize_optional(data.ai_prompt),
            example_value=self._normalize_optional(data.example_value),
            validation_rules=data.validation_rules,
            api_name=stable_code(data.api_name or code),
            is_required=data.is_required,
            is_visible=data.is_visible,
            is_filterable=data.is_filterable,
            is_searchable=data.is_searchable,
            allows_multiple=data.allows_multiple,
        )

        try:
            await self.repository.create_attribute_type(attribute_type)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Kod tipa atributa već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(attribute_type)
        return attribute_type

    async def update_attribute_type(
        self,
        attribute_type_id: uuid.UUID,
        data: AttributeTypeUpdate,
    ) -> AttributeDefinition:
        attribute_type = await self._get_attribute_type_or_404(
            attribute_type_id
        )
        changes = data.model_dump(exclude_unset=True)

        if "name" in changes:
            changes["name"] = changes["name"].strip()

        if "data_type" in changes and changes["data_type"] is not None:
            changes["data_type"] = changes["data_type"].value

        for field in ("unit", "description", "ai_prompt", "example_value"):
            if field in changes:
                changes[field] = self._normalize_optional(changes[field])

        if "api_name" in changes and changes["api_name"] is not None:
            changes["api_name"] = stable_code(changes["api_name"])

        actual_changes = {
            field: value
            for field, value in changes.items()
            if getattr(attribute_type, field) != value
        }

        if actual_changes:
            actual_changes["version"] = attribute_type.version + 1

        try:
            await self.repository.update_attribute_type(
                attribute_type,
                actual_changes,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Tip atributa već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(attribute_type)
        return attribute_type

    async def deactivate_attribute_type(
        self,
        attribute_type_id: uuid.UUID,
    ) -> None:
        attribute_type = await self._get_attribute_type_or_404(
            attribute_type_id
        )

        if not attribute_type.is_active:
            return

        try:
            await self.repository.deactivate_attribute_type(attribute_type)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(attribute_type)

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    async def _get_product_or_404(
        self,
        product_id: uuid.UUID,
    ) -> Product:
        product = await self.repository.get_product(product_id)

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Proizvod nije pronađen",
            )

        return product

    async def _ensure_unique_product_value(
        self,
        *,
        field: str,
        value: str | None,
        product_id: uuid.UUID | None = None,
    ) -> None:
        if value is None:
            return

        lookups = {
            "code": self.repository.get_product_by_code,
            "sku": self.repository.get_product_by_sku,
            "ean": self.repository.get_product_by_ean,
        }
        details = {
            "code": "Kod proizvoda već postoji",
            "sku": "SKU proizvoda već postoji",
            "ean": "EAN proizvoda već postoji",
        }

        existing = await lookups[field](value)

        if existing is not None and existing.id != product_id:
            raise HTTPException(
                status_code=409,
                detail=details[field],
            )

    async def create_product(
        self,
        data: ProductCreate,
    ) -> Product:
        await self._get_category_or_404(data.category_id)

        name = data.name.strip()

        if not name:
            raise HTTPException(
                status_code=422,
                detail="Naziv proizvoda ne sme biti prazan",
            )

        code = stable_code(data.code or name)
        sku = self._normalize_optional(data.sku)
        ean = self._normalize_optional(data.ean)

        await self._ensure_unique_product_value(field="code", value=code)
        await self._ensure_unique_product_value(field="sku", value=sku)
        await self._ensure_unique_product_value(field="ean", value=ean)

        product = Product(
            category_id=data.category_id,
            name=name,
            code=code,
            sku=sku,
            ean=ean,
            mpn=self._normalize_optional(data.mpn),
            brand=self._normalize_optional(data.brand),
            manufacturer=self._normalize_optional(data.manufacturer),
            status=data.status.strip(),
            is_active=data.is_active,
        )

        try:
            await self.repository.create_product(product)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Proizvod sa tim kodom, SKU ili EAN već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(product)
        return product

    async def update_product(
        self,
        product_id: uuid.UUID,
        data: ProductUpdate,
    ) -> Product:
        product = await self._get_product_or_404(product_id)
        changes = data.model_dump(exclude_unset=True)

        if "category_id" in changes:
            await self._get_category_or_404(changes["category_id"])

        if "name" in changes:
            changes["name"] = changes["name"].strip()

        for field in ("sku", "ean", "mpn", "brand", "manufacturer"):
            if field in changes:
                changes[field] = self._normalize_optional(changes[field])

        if "status" in changes:
            changes["status"] = changes["status"].strip()

        await self._ensure_unique_product_value(
            field="sku",
            value=changes.get("sku"),
            product_id=product_id,
        )
        await self._ensure_unique_product_value(
            field="ean",
            value=changes.get("ean"),
            product_id=product_id,
        )

        actual_changes = {
            field: value
            for field, value in changes.items()
            if getattr(product, field) != value
        }

        if actual_changes:
            actual_changes["version"] = product.version + 1

        try:
            await self.repository.update_product(product, actual_changes)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Proizvod sa tim kodom, SKU ili EAN već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(product)
        return product

    async def deactivate_product(
        self,
        product_id: uuid.UUID,
    ) -> None:
        product = await self._get_product_or_404(product_id)

        if not product.is_active:
            return

        try:
            await self.repository.deactivate_product(product)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(product)
