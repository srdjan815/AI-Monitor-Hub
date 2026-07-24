from __future__ import annotations

import json
import uuid
from collections.abc import Iterator

import httpx
import pytest

from app.core.security import create_access_token


API_ROOT = "http://localhost:8000/api/v1"


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    with httpx.Client(
        base_url=API_ROOT,
        timeout=30.0,
        headers={"Authorization": f"Bearer {create_access_token('cursor-tests')}"},
    ) as api_client:
        yield api_client


def _suffix() -> str:
    return uuid.uuid4().hex[:12]


def _create_definition(
    client: httpx.Client,
    suffix: str,
    index: int,
    *,
    scope: str,
) -> dict[str, object]:
    response = client.post(
        "/catalog/attribute-definitions",
        json={
            "name": f"Cursor Attribute {index} {suffix}",
            "slug": f"cursor_attribute_{index}_{suffix}",
            "scope": scope,
            "storage_kind": "ATTRIBUTE_VALUE",
            "data_type": "TEXT",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _definition_ids(page: httpx.Response) -> list[str]:
    return [item["definition"]["id"] for item in page.json()["items"]]


def test_resolved_cursor_snapshot_and_legacy_contract(
    client: httpx.Client,
) -> None:
    suffix = _suffix()
    category = client.post(
        "/categories",
        json={
            "name": f"Cursor Category {suffix}",
            "code": f"cursor_category_{suffix}",
        },
    )
    assert category.status_code == 201, category.text
    category_id = category.json()["id"]
    product = client.post(
        "/products",
        json={
            "category_id": category_id,
            "name": f"Cursor Product {suffix}",
            "code": f"cursor_product_{suffix}",
            "sku": f"CURSOR-{suffix}",
        },
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    definitions = [
        _create_definition(client, suffix, index, scope="CATEGORY")
        for index in range(4)
    ]
    definition_ids = [str(item["id"]) for item in definitions]
    for definition_id in definition_ids:
        assignment = client.post(
            f"/catalog/categories/{category_id}/attributes",
            json={"attribute_definition_id": definition_id},
        )
        assert assignment.status_code == 201, assignment.text

    params = {"scope": "CATEGORY", "limit": 2}
    first = client.get(
        f"/catalog/products/{product_id}/attributes/resolved",
        params=params,
    )
    assert first.status_code == 200, first.text
    assert first.json()["total"] == 4
    assert first.json()["limit"] == 2
    assert first.json()["snapshot_at"]
    cursor = first.json()["next_cursor"]
    assert cursor

    updated_id = _definition_ids(first)[0]
    updated = client.patch(
        f"/catalog/attribute-definitions/{updated_id}",
        json={"name": f"Renamed without reordering {suffix}"},
    )
    assert updated.status_code == 200, updated.text

    inserted = _create_definition(client, suffix, 5, scope="CATEGORY")
    inserted_id = str(inserted["id"])
    assignment = client.post(
        f"/catalog/categories/{category_id}/attributes",
        json={"attribute_definition_id": inserted_id},
    )
    assert assignment.status_code == 201, assignment.text

    second = client.get(
        f"/catalog/products/{product_id}/attributes/resolved",
        params={**params, "cursor": cursor},
    )
    assert second.status_code == 200, second.text
    assert second.json()["next_cursor"] is None
    paged_ids = _definition_ids(first) + _definition_ids(second)
    assert len(paged_ids) == len(set(paged_ids)) == 4
    assert set(paged_ids) == set(definition_ids)
    assert inserted_id not in paged_ids

    repeated = client.get(
        f"/catalog/products/{product_id}/attributes/resolved",
        params={**params, "cursor": cursor},
    )
    assert repeated.status_code == 200
    assert _definition_ids(repeated) == _definition_ids(second)

    changed_filter = client.get(
        f"/catalog/products/{product_id}/attributes/resolved",
        params={
            "scope": "CATEGORY",
            "limit": 3,
            "cursor": cursor,
        },
    )
    assert changed_filter.status_code == 400
    assert changed_filter.json()["code"] == "INVALID_CURSOR"

    tampered = client.get(
        f"/catalog/products/{product_id}/attributes/resolved",
        params={**params, "cursor": f"{cursor[:-1]}x"},
    )
    assert tampered.status_code == 400
    assert tampered.json()["code"] == "INVALID_CURSOR"

    legacy = client.get(
        f"/catalog/products/{product_id}/attributes",
        params={"scope": "CATEGORY", "limit": 2},
    )
    assert legacy.status_code == 200
    assert isinstance(legacy.json(), list)
    assert legacy.headers["x-total-count"] == "5"
    assert legacy.headers["x-next-cursor"]
    assert len(legacy.json()) == 2

    maximum = client.get(
        f"/catalog/products/{product_id}/attributes/resolved",
        params={"scope": "CATEGORY", "limit": 500},
    )
    assert maximum.status_code == 200
    over_maximum = client.get(
        f"/catalog/products/{product_id}/attributes/resolved",
        params={"scope": "CATEGORY", "limit": 501},
    )
    assert over_maximum.status_code == 422

    for definition_id in [*definition_ids, inserted_id]:
        client.delete(f"/catalog/attribute-definitions/{definition_id}")
    client.delete(f"/products/{product_id}")
    client.delete(f"/categories/{category_id}")


def test_resolved_filters_streaming_boundaries_and_authorization(
    client: httpx.Client,
) -> None:
    suffix = _suffix()
    category = client.post(
        "/categories",
        json={
            "name": f"Resolved Filter Category {suffix}",
            "code": f"resolved_filter_category_{suffix}",
        },
    )
    assert category.status_code == 201, category.text
    category_id = category.json()["id"]
    product = client.post(
        "/products",
        json={
            "category_id": category_id,
            "name": f"Resolved Filter Product {suffix}",
            "code": f"resolved_filter_product_{suffix}",
            "sku": f"RESOLVED-{suffix}",
        },
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    populated = _create_definition(client, suffix, 10, scope="GLOBAL")
    unset = _create_definition(client, suffix, 11, scope="GLOBAL")
    populated_id = str(populated["id"])
    unset_id = str(unset["id"])

    empty = client.get(
        f"/catalog/products/{product_id}/attributes/resolved",
        params={"scope": "CATEGORY"},
    )
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    write = client.put(
        f"/catalog/products/{product_id}/attributes/{populated_id}",
        json={"raw_value": "populated"},
    )
    assert write.status_code == 200, write.text
    default_page = client.get(
        f"/catalog/products/{product_id}/attributes/resolved",
        params={"scope": "GLOBAL"},
    )
    assert default_page.status_code == 200, default_page.text
    default_ids = set(_definition_ids(default_page))
    assert populated_id in default_ids
    assert unset_id not in default_ids

    expanded = client.get(
        f"/catalog/products/{product_id}/attributes/resolved",
        params={"scope": "GLOBAL", "include_unset": True, "limit": 100},
    )
    assert expanded.status_code == 200, expanded.text
    assert len(expanded.content) < 1_000_000

    family = client.post(
        "/catalog/attribute-families",
        json={"name": f"Cursor Family {suffix}", "slug": f"cursor_family_{suffix}"},
    )
    assert family.status_code == 201, family.text
    family_id = family.json()["id"]
    family_item = client.post(
        f"/catalog/attribute-families/{family_id}/items",
        json={"attribute_definition_id": populated_id},
    )
    assert family_item.status_code == 201, family_item.text
    family_page = client.get(
        f"/catalog/products/{product_id}/attributes/resolved",
        params={
            "include_unset": True,
            "family_id": family_id,
        },
    )
    assert family_page.status_code == 200, family_page.text
    assert _definition_ids(family_page) == [populated_id]

    parent_template = client.post(
        "/catalog/attribute-templates",
        json={
            "name": f"Cursor Parent Template {suffix}",
            "slug": f"cursor_parent_template_{suffix}",
        },
    )
    assert parent_template.status_code == 201, parent_template.text
    parent_template_id = parent_template.json()["id"]
    template_item = client.post(
        f"/catalog/attribute-templates/{parent_template_id}/items",
        json={"attribute_definition_id": populated_id},
    )
    assert template_item.status_code == 201, template_item.text
    child_template = client.post(
        "/catalog/attribute-templates",
        json={
            "name": f"Cursor Child Template {suffix}",
            "slug": f"cursor_child_template_{suffix}",
            "parent_template_id": parent_template_id,
        },
    )
    assert child_template.status_code == 201, child_template.text
    child_template_id = child_template.json()["id"]
    template_page = client.get(
        f"/catalog/products/{product_id}/attributes/resolved",
        params={
            "include_unset": True,
            "template_id": child_template_id,
        },
    )
    assert template_page.status_code == 200, template_page.text
    assert _definition_ids(template_page) == [populated_id]

    export = client.get(
        f"/catalog/products/{product_id}/attributes/resolved/export",
        params={"scope": "GLOBAL"},
    )
    assert export.status_code == 200, export.text
    assert export.headers["content-type"].startswith("application/x-ndjson")
    assert "attachment;" in export.headers["content-disposition"]
    exported = [json.loads(line) for line in export.text.splitlines()]
    exported_ids = {item["definition"]["id"] for item in exported}
    assert populated_id in exported_ids
    assert unset_id in exported_ids

    missing = client.get(f"/catalog/products/{uuid.uuid4()}/attributes/resolved")
    assert missing.status_code == 404
    with httpx.Client(base_url=API_ROOT, timeout=15.0) as anonymous:
        unauthorized = anonymous.get(
            f"/catalog/products/{product_id}/attributes/resolved/export"
        )
    assert unauthorized.status_code == 401

    client.delete(f"/catalog/attribute-templates/{child_template_id}")
    client.delete(f"/catalog/attribute-templates/{parent_template_id}")
    client.delete(f"/catalog/attribute-families/{family_id}")
    client.delete(f"/catalog/attribute-definitions/{populated_id}")
    client.delete(f"/catalog/attribute-definitions/{unset_id}")
    client.delete(f"/products/{product_id}")
    client.delete(f"/categories/{category_id}")
