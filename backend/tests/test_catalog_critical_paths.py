from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.modules.catalog.category_service import CategoryService
from app.modules.catalog.product_service import ProductService
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryUpdate,
    ProductCreate,
    ProductUpdate,
)


def persistence_error() -> IntegrityError:
    return IntegrityError("statement", {}, RuntimeError("forced constraint"))


def category_service() -> tuple[CategoryService, AsyncMock, AsyncMock]:
    session = AsyncMock()
    service = CategoryService(session)
    repository = AsyncMock()
    service.repository = repository
    return service, session, repository


def product_service() -> tuple[ProductService, AsyncMock, AsyncMock]:
    session = AsyncMock()
    service = ProductService(session)
    repository = AsyncMock()
    service.repository = repository
    return service, session, repository


def category(
    entity_id: uuid.UUID,
    *,
    name: str = "Category",
    code: str = "category",
    parent_id: uuid.UUID | None = None,
    position: int = 0,
    is_active: bool = True,
    version: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=entity_id,
        name=name,
        code=code,
        parent_id=parent_id,
        position=position,
        is_active=is_active,
        version=version,
    )


def product(
    entity_id: uuid.UUID,
    category_id: uuid.UUID,
    *,
    is_active: bool = True,
    version: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=entity_id,
        category_id=category_id,
        name="Product",
        code="product",
        sku=None,
        ean=None,
        mpn=None,
        brand=None,
        manufacturer=None,
        status="DRAFT",
        is_active=is_active,
        version=version,
    )


@pytest.mark.asyncio
async def test_category_parent_guards_cover_missing_self_cycle_and_corruption() -> None:
    service, _, repository = category_service()
    category_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    grandparent_id = uuid.uuid4()

    await service._validate_parent_category(category_id=None, parent_id=None)

    with pytest.raises(HTTPException) as self_parent:
        await service._validate_parent_category(
            category_id=category_id,
            parent_id=category_id,
        )
    assert self_parent.value.status_code == 422

    repository.get_category.return_value = None
    with pytest.raises(HTTPException) as missing:
        await service._validate_parent_category(
            category_id=category_id,
            parent_id=parent_id,
        )
    assert missing.value.status_code == 404

    repository.get_category.side_effect = [
        category(parent_id, parent_id=category_id),
        category(category_id),
    ]
    with pytest.raises(HTTPException) as cycle:
        await service._validate_parent_category(
            category_id=category_id,
            parent_id=parent_id,
        )
    assert cycle.value.status_code == 422

    repository.get_category.side_effect = [
        category(parent_id, parent_id=grandparent_id),
        category(grandparent_id, parent_id=parent_id),
        category(parent_id, parent_id=grandparent_id),
    ]
    with pytest.raises(HTTPException) as corrupt:
        await service._validate_parent_category(
            category_id=category_id,
            parent_id=parent_id,
        )
    assert corrupt.value.status_code == 422

    repository.get_category.side_effect = [
        category(parent_id, parent_id=grandparent_id),
        category(grandparent_id),
    ]
    await service._validate_parent_category(
        category_id=category_id,
        parent_id=parent_id,
    )


@pytest.mark.asyncio
async def test_category_create_guardrails_success_and_failure_transactions() -> None:
    service, session, repository = category_service()

    with pytest.raises(HTTPException) as blank:
        await service.create_category(CategoryCreate(name="   "))
    assert blank.value.status_code == 422

    repository.get_category_by_code.return_value = category(uuid.uuid4())
    with pytest.raises(HTTPException) as duplicate:
        await service.create_category(CategoryCreate(name="Duplicate"))
    assert duplicate.value.status_code == 409

    service, session, repository = category_service()
    repository.get_category_by_code.return_value = None
    created = await service.create_category(
        CategoryCreate(name="  Čista kategorija  ", code="  Čista kategorija  ")
    )
    assert created.name == "Čista kategorija"
    assert created.code == "cista_kategorija"
    repository.create_category.assert_awaited_once_with(created)
    repository.link_all_global_attributes.assert_awaited_once_with(created.id)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(created)

    for error, expected_status in (
        (persistence_error(), 409),
        (RuntimeError("write failed"), None),
    ):
        service, session, repository = category_service()
        repository.get_category_by_code.return_value = None
        repository.create_category.side_effect = error
        if expected_status is None:
            with pytest.raises(RuntimeError, match="write failed"):
                await service.create_category(CategoryCreate(name="Failure"))
        else:
            with pytest.raises(HTTPException) as failure:
                await service.create_category(CategoryCreate(name="Failure"))
            assert failure.value.status_code == expected_status
        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_category_update_deactivate_and_tree_behavior() -> None:
    category_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    service, session, repository = category_service()
    repository.get_category.return_value = None
    with pytest.raises(HTTPException) as missing:
        await service.update_category(category_id, CategoryUpdate(position=1))
    assert missing.value.status_code == 404

    current = category(category_id, name="Same", parent_id=parent_id)
    repository.get_category.return_value = current
    with pytest.raises(HTTPException) as blank:
        await service.update_category(category_id, CategoryUpdate(name="   "))
    assert blank.value.status_code == 422

    service, session, repository = category_service()
    current = category(category_id, name="Same", parent_id=parent_id)
    repository.get_category.side_effect = [current, category(parent_id)]
    unchanged = await service.update_category(
        category_id,
        CategoryUpdate(name="Same", parent_id=parent_id),
    )
    assert unchanged is current
    repository.update_category.assert_awaited_once_with(current, {})
    session.commit.assert_awaited_once()

    service, session, repository = category_service()
    current = category(category_id, name="Old", position=0)
    repository.get_category.return_value = current
    updated = await service.update_category(
        category_id,
        CategoryUpdate(name="  New  ", position=4),
    )
    assert updated is current
    repository.update_category.assert_awaited_once_with(
        current,
        {"name": "New", "position": 4, "version": 2},
    )

    for error, expected_status in (
        (persistence_error(), 409),
        (RuntimeError("update failed"), None),
    ):
        service, session, repository = category_service()
        repository.get_category.return_value = category(category_id)
        repository.update_category.side_effect = error
        if expected_status is None:
            with pytest.raises(RuntimeError, match="update failed"):
                await service.update_category(
                    category_id,
                    CategoryUpdate(position=2),
                )
        else:
            with pytest.raises(HTTPException) as failure:
                await service.update_category(
                    category_id,
                    CategoryUpdate(position=2),
                )
            assert failure.value.status_code == expected_status
        session.rollback.assert_awaited_once()

    service, session, repository = category_service()
    repository.get_category.return_value = category(category_id, is_active=False)
    await service.deactivate_category(category_id)
    repository.deactivate_category.assert_not_awaited()
    session.commit.assert_not_awaited()

    service, session, repository = category_service()
    active = category(category_id)
    repository.get_category.return_value = active
    await service.deactivate_category(category_id)
    repository.deactivate_category.assert_awaited_once_with(active)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(active)

    service, session, repository = category_service()
    repository.get_category.return_value = category(category_id)
    repository.deactivate_category.side_effect = RuntimeError("deactivate failed")
    with pytest.raises(RuntimeError, match="deactivate failed"):
        await service.deactivate_category(category_id)
    session.rollback.assert_awaited_once()

    root_id = uuid.uuid4()
    child_id = uuid.uuid4()
    orphan_parent = uuid.uuid4()
    service, _, repository = category_service()
    repository.list_all_categories.return_value = [
        category(root_id, position=2),
        category(child_id, parent_id=root_id),
        category(uuid.uuid4(), parent_id=orphan_parent),
    ]
    roots = await service.get_category_tree(limit=3)
    assert len(roots) == 2
    assert [node.id for node in roots[0].children] == [child_id]

    repository.list_all_categories.return_value = [
        category(root_id),
        category(child_id),
    ]
    with pytest.raises(HTTPException) as oversized:
        await service.get_category_tree(limit=1)
    assert oversized.value.status_code == 413


@pytest.mark.asyncio
async def test_product_lookup_uniqueness_and_normalization_guards() -> None:
    service, _, repository = product_service()
    category_id = uuid.uuid4()
    product_id = uuid.uuid4()

    repository.get_category.return_value = None
    with pytest.raises(HTTPException) as missing_category:
        await service._get_category_or_404(category_id)
    assert missing_category.value.status_code == 404

    repository.get_product.return_value = None
    with pytest.raises(HTTPException) as missing_product:
        await service._get_product_or_404(product_id)
    assert missing_product.value.status_code == 404

    await service._ensure_unique_product_value(field="sku", value=None)
    for field in ("code", "sku", "ean"):
        existing = product(uuid.uuid4(), category_id)
        getattr(repository, f"get_product_by_{field}").return_value = existing
        with pytest.raises(HTTPException) as duplicate:
            await service._ensure_unique_product_value(
                field=field,
                value=f"{field}-value",
                product_id=product_id,
            )
        assert duplicate.value.status_code == 409
        existing.id = product_id
        await service._ensure_unique_product_value(
            field=field,
            value=f"{field}-value",
            product_id=product_id,
        )

    assert service._normalize_optional(None) is None
    assert service._normalize_optional("   ") is None
    assert service._normalize_optional(" value ") == "value"


@pytest.mark.asyncio
async def test_product_create_update_and_deactivate_transactions() -> None:
    category_id = uuid.uuid4()
    product_id = uuid.uuid4()
    service, session, repository = product_service()
    repository.get_category.return_value = category(category_id)
    repository.get_product_by_code.return_value = None
    repository.get_product_by_sku.return_value = None
    repository.get_product_by_ean.return_value = None

    with pytest.raises(HTTPException) as blank:
        await service.create_product(ProductCreate(category_id=category_id, name="   "))
    assert blank.value.status_code == 422

    created = await service.create_product(
        ProductCreate(
            category_id=category_id,
            name="  Product Name  ",
            sku=" SKU ",
            ean=" 12345678 ",
            mpn="   ",
            brand=" Brand ",
            manufacturer=" Maker ",
            status=" READY ",
        )
    )
    assert created.name == "Product Name"
    assert created.code == "product_name"
    assert created.sku == "SKU"
    assert created.ean == "12345678"
    assert created.mpn is None
    assert created.brand == "Brand"
    assert created.manufacturer == "Maker"
    assert created.status == "READY"
    repository.create_product.assert_awaited_once_with(created)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(created)

    for error, expected_status in (
        (persistence_error(), 409),
        (RuntimeError("create failed"), None),
    ):
        service, session, repository = product_service()
        repository.get_category.return_value = category(category_id)
        repository.get_product_by_code.return_value = None
        repository.get_product_by_sku.return_value = None
        repository.get_product_by_ean.return_value = None
        repository.create_product.side_effect = error
        payload = ProductCreate(category_id=category_id, name="Failure")
        if expected_status is None:
            with pytest.raises(RuntimeError, match="create failed"):
                await service.create_product(payload)
        else:
            with pytest.raises(HTTPException) as failure:
                await service.create_product(payload)
            assert failure.value.status_code == expected_status
        session.rollback.assert_awaited_once()

    service, session, repository = product_service()
    current = product(product_id, category_id)
    repository.get_product.return_value = current
    repository.get_category.return_value = category(category_id)
    repository.get_product_by_sku.return_value = None
    repository.get_product_by_ean.return_value = None
    updated = await service.update_product(
        product_id,
        ProductUpdate(
            category_id=category_id,
            name="  Updated  ",
            sku=" NEW-SKU ",
            ean=" 87654321 ",
            mpn=" MPN ",
            brand=" Brand ",
            manufacturer=" Maker ",
            status=" READY ",
            is_active=False,
        ),
    )
    assert updated is current
    repository.update_product.assert_awaited_once_with(
        current,
        {
            "name": "Updated",
            "sku": "NEW-SKU",
            "ean": "87654321",
            "mpn": "MPN",
            "brand": "Brand",
            "manufacturer": "Maker",
            "status": "READY",
            "is_active": False,
            "version": 2,
        },
    )

    service, session, repository = product_service()
    current = product(product_id, category_id)
    repository.get_product.return_value = current
    repository.get_product_by_sku.return_value = None
    repository.get_product_by_ean.return_value = None
    await service.update_product(product_id, ProductUpdate(name="Product"))
    repository.update_product.assert_awaited_once_with(current, {})

    for error, expected_status in (
        (persistence_error(), 409),
        (RuntimeError("update failed"), None),
    ):
        service, session, repository = product_service()
        repository.get_product.return_value = product(product_id, category_id)
        repository.get_product_by_sku.return_value = None
        repository.get_product_by_ean.return_value = None
        repository.update_product.side_effect = error
        payload = ProductUpdate(name="Changed")
        if expected_status is None:
            with pytest.raises(RuntimeError, match="update failed"):
                await service.update_product(product_id, payload)
        else:
            with pytest.raises(HTTPException) as failure:
                await service.update_product(product_id, payload)
            assert failure.value.status_code == expected_status
        session.rollback.assert_awaited_once()

    service, session, repository = product_service()
    repository.get_product.return_value = product(
        product_id,
        category_id,
        is_active=False,
    )
    await service.deactivate_product(product_id)
    repository.deactivate_product.assert_not_awaited()

    service, session, repository = product_service()
    active = product(product_id, category_id)
    repository.get_product.return_value = active
    await service.deactivate_product(product_id)
    repository.deactivate_product.assert_awaited_once_with(active)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(active)

    service, session, repository = product_service()
    repository.get_product.return_value = product(product_id, category_id)
    repository.deactivate_product.side_effect = RuntimeError("deactivate failed")
    with pytest.raises(RuntimeError, match="deactivate failed"):
        await service.deactivate_product(product_id)
    session.rollback.assert_awaited_once()
