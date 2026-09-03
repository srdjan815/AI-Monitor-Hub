from __future__ import annotations

import uuid

import httpx
import pytest
from app.core.security import create_access_token


API_ROOT = "http://localhost:8000/api/v1"


@pytest.fixture
def api_client() -> httpx.Client:
    with httpx.Client(
        base_url=API_ROOT,
        timeout=10.0,
        headers={"Authorization": f"Bearer {create_access_token('pytest')}"},
    ) as client:
        yield client


def unique_suffix() -> str:
    return uuid.uuid4().hex[:12]


def item_ids(response: httpx.Response) -> set[str]:
    response.raise_for_status()
    return {item["id"] for item in response.json()["items"]}


def offset_ids(
    client: httpx.Client,
    path: str,
    *,
    active_only: bool,
    limit: int,
    **filters: str,
) -> set[str]:
    offset = 0
    identifiers: set[str] = set()
    while True:
        response = client.get(
            path,
            params={
                "active_only": str(active_only).lower(),
                "limit": limit,
                "offset": offset,
                **filters,
            },
        )
        response.raise_for_status()
        payload = response.json()
        items = payload["items"]
        identifiers.update(item["id"] for item in items)
        offset += len(items)
        if offset >= payload["total"]:
            return identifiers
        assert items, "Offset pagination stopped before the reported total"


def product_ids(
    client: httpx.Client,
    *,
    active_only: bool,
) -> set[str]:
    params: dict[str, str | int] = {
        "active_only": str(active_only).lower(),
        "limit": 500,
        "pagination": "cursor",
    }
    identifiers: set[str] = set()
    while True:
        response = client.get("/products", params=params)
        response.raise_for_status()
        page_ids = {item["id"] for item in response.json()["items"]}
        assert identifiers.isdisjoint(page_ids)
        identifiers.update(page_ids)
        cursor = response.headers.get("x-next-cursor")
        if cursor is None:
            return identifiers
        params["cursor"] = cursor


def test_categories_crud(api_client: httpx.Client) -> None:
    suffix = unique_suffix()
    code = f"category_crud_{suffix}"
    category_id: str | None = None

    try:
        created = api_client.post(
            "/categories",
            json={
                "name": f"Disposable Category {suffix}",
                "code": code,
                "position": 0,
            },
        )
        assert created.status_code == 201
        category = created.json()
        category_id = category["id"]
        assert category["version"] == 1
        assert category["is_active"] is True

        duplicate = api_client.post(
            "/categories",
            json={"name": f"Duplicate Category {suffix}", "code": code},
        )
        assert duplicate.status_code == 409

        fetched = api_client.get(f"/categories/{category_id}")
        assert fetched.status_code == 200
        assert fetched.json()["code"] == code

        updated = api_client.patch(
            f"/categories/{category_id}",
            json={"name": f"Disposable Category Updated {suffix}"},
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2

        missing_id = uuid.uuid4()
        assert api_client.get(f"/categories/{missing_id}").status_code == 404
        assert (
            api_client.patch(
                f"/categories/{missing_id}",
                json={"name": "Missing"},
            ).status_code
            == 404
        )

        deleted = api_client.delete(f"/categories/{category_id}")
        assert deleted.status_code == 204

        inactive = api_client.get(f"/categories/{category_id}")
        assert inactive.status_code == 200
        assert inactive.json()["is_active"] is False
        assert inactive.json()["version"] == 3

        assert category_id not in offset_ids(
            api_client,
            "/categories",
            active_only=True,
            limit=500,
        )
        assert category_id in offset_ids(
            api_client,
            "/categories",
            active_only=False,
            limit=500,
        )
    finally:
        if category_id is not None:
            api_client.delete(f"/categories/{category_id}")


def test_products_crud(api_client: httpx.Client) -> None:
    suffix = unique_suffix()
    code = f"product_crud_{suffix}"
    sku = f"PRODUCT-{suffix}"
    ean = f"99{suffix[:10]}"
    product_id: str | None = None
    category_id: str | None = None

    try:
        category = api_client.post(
            "/categories",
            json={
                "name": f"Disposable Product Category {suffix}",
                "code": f"product_category_{suffix}",
            },
        )
        assert category.status_code == 201
        category_id = category.json()["id"]
        created = api_client.post(
            "/products",
            json={
                "category_id": category_id,
                "name": f"Disposable Product {suffix}",
                "code": code,
                "sku": sku,
                "ean": ean,
                "status": "DRAFT",
            },
        )
        assert created.status_code == 201
        product = created.json()
        product_id = product["id"]
        assert product["version"] == 1

        duplicate = api_client.post(
            "/products",
            json={
                "category_id": product["category_id"],
                "name": f"Duplicate Product {suffix}",
                "code": code,
                "sku": f"DUPLICATE-{suffix}",
                "ean": f"98{suffix[:10]}",
            },
        )
        assert duplicate.status_code == 409

        fetched = api_client.get(f"/products/{product_id}")
        assert fetched.status_code == 200
        assert fetched.json()["code"] == code

        updated = api_client.patch(
            f"/products/{product_id}",
            json={
                "name": f"Disposable Product Updated {suffix}",
                "status": "READY",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2
        assert updated.json()["status"] == "READY"

        missing_id = uuid.uuid4()
        assert api_client.get(f"/products/{missing_id}").status_code == 404
        assert (
            api_client.patch(
                f"/products/{missing_id}",
                json={"name": "Missing"},
            ).status_code
            == 404
        )

        deleted = api_client.delete(f"/products/{product_id}")
        assert deleted.status_code == 204

        inactive = api_client.get(f"/products/{product_id}")
        assert inactive.status_code == 200
        assert inactive.json()["is_active"] is False
        assert inactive.json()["version"] == 3

        assert product_id not in product_ids(api_client, active_only=True)
        assert product_id in product_ids(api_client, active_only=False)
    finally:
        if product_id is not None:
            api_client.delete(f"/products/{product_id}")
        if category_id is not None:
            api_client.delete(f"/categories/{category_id}")


def test_attribute_types_crud(api_client: httpx.Client) -> None:
    suffix = unique_suffix()
    code = f"attribute_type_crud_{suffix}"
    attribute_type_id: str | None = None

    try:
        created = api_client.post(
            "/attribute-types",
            json={
                "name": f"Disposable Attribute Type {suffix}",
                "code": code,
                "scope": "GLOBAL",
                "data_type": "TEXT",
                "api_name": code,
            },
        )
        assert created.status_code == 201
        attribute_type = created.json()
        attribute_type_id = attribute_type["id"]
        assert attribute_type["version"] == 1

        duplicate = api_client.post(
            "/attribute-types",
            json={
                "name": f"Duplicate Attribute Type {suffix}",
                "code": code,
                "scope": "GLOBAL",
                "data_type": "TEXT",
            },
        )
        assert duplicate.status_code == 409

        fetched = api_client.get(f"/attribute-types/{attribute_type_id}")
        assert fetched.status_code == 200
        assert fetched.json()["code"] == code

        updated = api_client.patch(
            f"/attribute-types/{attribute_type_id}",
            json={
                "name": f"Disposable Attribute Type Updated {suffix}",
                "data_type": "LONG_TEXT",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2

        missing_id = uuid.uuid4()
        assert api_client.get(f"/attribute-types/{missing_id}").status_code == 404
        assert (
            api_client.patch(
                f"/attribute-types/{missing_id}",
                json={"name": "Missing"},
            ).status_code
            == 404
        )

        deleted = api_client.delete(f"/attribute-types/{attribute_type_id}")
        assert deleted.status_code == 204

        inactive = api_client.get(f"/attribute-types/{attribute_type_id}")
        assert inactive.status_code == 200
        assert inactive.json()["is_active"] is False
        assert inactive.json()["version"] == 3

        assert attribute_type_id not in offset_ids(
            api_client,
            "/attribute-types",
            active_only=True,
            limit=500,
        )
        assert attribute_type_id in offset_ids(
            api_client,
            "/attribute-types",
            active_only=False,
            limit=500,
        )
    finally:
        if attribute_type_id is not None:
            api_client.delete(f"/attribute-types/{attribute_type_id}")


def test_attributes_supported_crud(api_client: httpx.Client) -> None:
    suffix = unique_suffix()
    code = f"attribute_crud_{suffix}"
    attribute_id: str | None = None

    try:
        created = api_client.post(
            "/attributes",
            json={
                "name": f"Disposable Attribute {suffix}",
                "code": code,
                "scope": "GLOBAL",
                "data_type": "TEXT",
                "api_name": code,
            },
        )
        assert created.status_code == 201
        attribute = created.json()
        attribute_id = attribute["id"]
        assert attribute["version"] == 1

        duplicate = api_client.post(
            "/attributes",
            json={
                "name": f"Duplicate Attribute {suffix}",
                "code": code,
                "scope": "GLOBAL",
                "data_type": "TEXT",
            },
        )
        assert duplicate.status_code == 409

        assert attribute_id in offset_ids(
            api_client,
            "/attributes",
            active_only=True,
            limit=1000,
            scope="GLOBAL",
        )

        updated = api_client.patch(
            f"/attributes/{attribute_id}",
            json={
                "name": f"Disposable Attribute Updated {suffix}",
                "data_type": "LONG_TEXT",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2

        missing_id = uuid.uuid4()
        assert (
            api_client.patch(
                f"/attributes/{missing_id}",
                json={"name": "Missing"},
            ).status_code
            == 404
        )

        deactivated = api_client.patch(
            f"/attributes/{attribute_id}",
            json={"is_active": False},
        )
        assert deactivated.status_code == 200
        assert deactivated.json()["is_active"] is False
        assert deactivated.json()["version"] == 3

        assert attribute_id not in offset_ids(
            api_client,
            "/attributes",
            active_only=True,
            limit=1000,
        )
        assert attribute_id in offset_ids(
            api_client,
            "/attributes",
            active_only=False,
            limit=1000,
        )
    finally:
        if attribute_id is not None:
            api_client.patch(
                f"/attributes/{attribute_id}",
                json={"is_active": False},
            )
