from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keyset_pagination import (
    encode_time_keyset,
    resolve_time_keyset,
)
from app.core.limits import MAX_CURSOR_CHARS, MAX_LEGACY_OFFSET
from app.core.pagination import InvalidCursorError
from app.db.session import get_db
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    ProductCreate,
    ProductList,
    ProductRead,
    ProductUpdate,
)
from app.modules.catalog.service import CatalogService

router = APIRouter(prefix="/products", tags=["catalog-products"])


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    session: AsyncSession = Depends(get_db),
) -> ProductRead:
    product = await CatalogService(session).create_product(payload)
    return ProductRead.model_validate(product)


@router.get("", response_model=ProductList)
async def list_products(
    response: Response,
    active_only: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> ProductList:
    cursor_mode = cursor is not None or pagination == "cursor"
    if not cursor_mode:
        rows, total = await CatalogRepository(session).list_products(
            active_only=active_only,
            limit=limit,
            offset=offset,
        )
        return ProductList(
            items=[ProductRead.model_validate(row) for row in rows],
            total=total,
        )

    if pagination == "offset" or offset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CURSOR",
                "message": "Cursor pagination cannot use offset mode or offset",
            },
        )

    cursor_filters = {
        "active_only": active_only,
        "limit": limit,
        "pagination": "cursor",
        "order": "created_at_desc,id_desc",
    }
    try:
        keyset = await resolve_time_keyset(
            session,
            cursor=cursor,
            resource="catalog.products",
            filters=cursor_filters,
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CURSOR", "message": str(exc)},
        ) from exc

    rows, total = await CatalogRepository(session).list_products(
        active_only=active_only,
        limit=limit + 1,
        offset=offset,
        snapshot_at=keyset.snapshot_at,
        after=(
            (keyset.after_at, keyset.after_id)
            if keyset.after_at is not None and keyset.after_id is not None
            else None
        ),
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    response.headers["X-Snapshot-At"] = keyset.snapshot_at.isoformat()
    if has_more:
        last = rows[-1]
        response.headers["X-Next-Cursor"] = encode_time_keyset(
            resource="catalog.products",
            filters=cursor_filters,
            after_at=last.created_at,
            after_id=last.id,
            snapshot_at=keyset.snapshot_at,
        )

    return ProductList(
        items=[ProductRead.model_validate(row) for row in rows],
        total=total,
    )


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ProductRead:
    product = await CatalogRepository(session).get_product(product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proizvod nije pronađen",
        )

    return ProductRead.model_validate(product)


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    session: AsyncSession = Depends(get_db),
) -> ProductRead:
    product = await CatalogService(session).update_product(
        product_id,
        payload,
    )

    return ProductRead.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_product(
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await CatalogService(session).deactivate_product(product_id)

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
