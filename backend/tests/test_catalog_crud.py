from __future__ import annotations

import uuid

import httpx
import pytest


API_ROOT = "http://localhost:8000/api/v1"


@pytest.fixture
def api_client() -> httpx.Client:
    with httpx.Client(base_url=API_ROOT, timeout=10.0) as client:
        yield client


def unique_suffix() -> str:
    return uuid.uuid4().hex[:12]


def item_ids(response: httpx.Response) -> set[str]:
    response.raise_for_status()
    return {item["id"] for item in response.json()["items"]}


def active_category_id(client: httpx.Client) -> str:
    response = client.get("/categories", params={"limit": 1})
    response.raise_for_status()
    items = response.json()["items"]
    assert items, "Product CRUD tests require one active category"
    return items[0]["id"]


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

        active_list = api_client.get("/categories", params={"limit": 500})
        assert category_id not in item_ids(active_list)

        all_list = api_client.get(
            "/categories",
            params={"active_only": "false", "limit": 500},
        )
        assert category_id in item_ids(all_list)
    finally:
        if category_id is not None:
            api_client.delete(f"/categories/{category_id}")


def test_products_crud(api_client: httpx.Client) -> None:
    suffix = unique_suffix()
    code = f"product_crud_{suffix}"
    sku = f"PRODUCT-{suffix}"
    ean = f"99{suffix[:10]}"
    product_id: str | None = None

    try:
        created = api_client.post(
            "/products",
            json={
                "category_id": active_category_id(api_client),
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

        assert product_id not in item_ids(
            api_client.get("/products", params={"limit": 500})
        )
        assert product_id in item_ids(
            api_client.get(
                "/products",
                params={"active_only": "false", "limit": 500},
            )
        )
    finally:
        if product_id is not None:
            api_client.delete(f"/products/{product_id}")


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
        assert (
            api_client.get(f"/attribute-types/{missing_id}").status_code == 404
        )
        assert (
            api_client.patch(
                f"/attribute-types/{missing_id}",
                json={"name": "Missing"},
            ).status_code
            == 404
        )

        deleted = api_client.delete(
            f"/attribute-types/{attribute_type_id}"
        )
        assert deleted.status_code == 204

        inactive = api_client.get(
            f"/attribute-types/{attribute_type_id}"
        )
        assert inactive.status_code == 200
        assert inactive.json()["is_active"] is False
        assert inactive.json()["version"] == 3

        assert attribute_type_id not in item_ids(
            api_client.get("/attribute-types", params={"limit": 500})
        )
        assert attribute_type_id in item_ids(
            api_client.get(
                "/attribute-types",
                params={"active_only": "false", "limit": 500},
            )
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

        active_list = api_client.get(
            "/attributes",
            params={"scope": "GLOBAL", "limit": 1000},
        )
        assert attribute_id in item_ids(active_list)

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

        assert attribute_id not in item_ids(
            api_client.get("/attributes", params={"limit": 1000})
        )
        assert attribute_id in item_ids(
            api_client.get(
                "/attributes",
                params={"active_only": "false", "limit": 1000},
            )
        )
    finally:
        if attribute_id is not None:
            api_client.patch(
                f"/attributes/{attribute_id}",
                json={"is_active": False},
            )
