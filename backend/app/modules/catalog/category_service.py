from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Category
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryTree,
    CategoryUpdate,
)
from app.modules.catalog.utils import stable_code


class CategoryService:
    """Category hierarchy validation and command transactions."""

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
                detail=("Kategorija ne mo\u017ee biti sopstveni roditelj"),
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
                    detail=("Nije dozvoljena kru\u017ena hijerarhija kategorija"),
                )

            if current.id in visited:
                raise HTTPException(
                    status_code=422,
                    detail=("Otkrivena je neispravna hijerarhija kategorija"),
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
                detail="Kod kategorije ve\u0107 postoji",
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
                detail=("Kategorija sa tim nazivom ve\u0107 postoji"),
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
            await self.repository.update_category(
                category,
                actual_changes,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail=("Kategorija sa tim nazivom ve\u0107 postoji"),
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

    async def get_category_tree(
        self,
        *,
        limit: int = 2_000,
    ) -> list[CategoryTree]:
        categories = await self.repository.list_all_categories(limit=limit + 1)
        if len(categories) > limit:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "RESPONSE_LIMIT_EXCEEDED",
                    "message": (
                        "Category tree exceeds the requested node limit; "
                        "use the paginated category list"
                    ),
                },
            )

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


__all__ = ["CategoryService"]
