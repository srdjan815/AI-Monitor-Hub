from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Category, Product
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import ProductCreate, ProductUpdate
from app.modules.catalog.utils import stable_code


class ProductService:
    """Product validation, uniqueness enforcement, and command transactions."""

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
                detail="Kategorija nije prona\u0111ena",
            )

        return category

    async def _get_product_or_404(
        self,
        product_id: uuid.UUID,
    ) -> Product:
        product = await self.repository.get_product(product_id)

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Proizvod nije prona\u0111en",
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
            "code": "Kod proizvoda ve\u0107 postoji",
            "sku": "SKU proizvoda ve\u0107 postoji",
            "ean": "EAN proizvoda ve\u0107 postoji",
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

        await self._ensure_unique_product_value(
            field="code",
            value=code,
        )
        await self._ensure_unique_product_value(
            field="sku",
            value=sku,
        )
        await self._ensure_unique_product_value(
            field="ean",
            value=ean,
        )

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
                detail=("Proizvod sa tim kodom, SKU ili EAN ve\u0107 postoji"),
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

        for field in (
            "sku",
            "ean",
            "mpn",
            "brand",
            "manufacturer",
        ):
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
            await self.repository.update_product(
                product,
                actual_changes,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail=("Proizvod sa tim kodom, SKU ili EAN ve\u0107 postoji"),
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

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None


__all__ = ["ProductService"]
