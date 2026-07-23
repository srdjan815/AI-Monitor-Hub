from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

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
    active_only: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> ProductList:
    rows, total = await CatalogRepository(session).list_products(
        active_only=active_only,
        limit=limit,
        offset=offset,
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