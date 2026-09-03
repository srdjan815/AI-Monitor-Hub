from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    AttributeCreate,
    AttributeTypeCreate,
    CategoryCreate,
    ProductCreate,
)
from app.modules.catalog.service import CatalogService


def persistence_error() -> IntegrityError:
    return IntegrityError("INSERT", {}, RuntimeError("forced failure"))


def service_with_mocks() -> tuple[
    CatalogService,
    AsyncMock,
    AsyncMock,
]:
    session = AsyncMock()
    service = CatalogService(session)
    repository = AsyncMock(spec=CatalogRepository)
    service.repository = repository
    return service, session, repository


@pytest.mark.asyncio
async def test_category_create_rolls_back_on_persistence_failure() -> None:
    service, session, repository = service_with_mocks()
    repository.get_category_by_code.return_value = None
    repository.create_category.side_effect = persistence_error()

    with pytest.raises(HTTPException) as error:
        await service.create_category(CategoryCreate(name="Rollback Category"))

    assert error.value.status_code == 409
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_product_create_rolls_back_on_persistence_failure() -> None:
    service, session, repository = service_with_mocks()
    repository.get_category.return_value = SimpleNamespace()
    repository.get_product_by_code.return_value = None
    repository.get_product_by_sku.return_value = None
    repository.get_product_by_ean.return_value = None
    repository.create_product.side_effect = persistence_error()

    with pytest.raises(HTTPException) as error:
        await service.create_product(
            ProductCreate(
                category_id="e2b00af1-c567-4c1d-b881-3d79fd165365",
                name="Rollback Product",
            )
        )

    assert error.value.status_code == 409
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_attribute_type_create_rolls_back_on_failure() -> None:
    service, session, repository = service_with_mocks()
    repository.get_attribute_type_by_code.return_value = None
    repository.create_attribute_type.side_effect = persistence_error()

    with pytest.raises(HTTPException) as error:
        await service.create_attribute_type(
            AttributeTypeCreate(
                name="Rollback Attribute Type",
                scope="GLOBAL",
            )
        )

    assert error.value.status_code == 409
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_attribute_create_rolls_back_on_persistence_failure() -> None:
    service, session, repository = service_with_mocks()
    repository.get_attribute_by_code.return_value = None
    repository.create_attribute.side_effect = persistence_error()

    with pytest.raises(HTTPException) as error:
        await service.create_attribute(
            AttributeCreate(
                name="Rollback Attribute",
                scope="GLOBAL",
            )
        )

    assert error.value.status_code == 409
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
