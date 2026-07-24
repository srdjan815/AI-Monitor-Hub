from __future__ import annotations

import ast
import uuid
from pathlib import Path

import httpx
import pytest
from app.core.security import create_access_token

from app.modules.catalog import attribute_validation
from app.modules.catalog.attribute_models import AttributeNormalizationRule
from app.modules.catalog.attribute_validation import AttributeValueValidator
from app.modules.catalog.models import AttributeDefinition

API_ROOT = "http://localhost:8000/api/v1"
CATALOG_ROOT = Path(__file__).resolve().parents[1] / "app" / "modules" / "catalog"


@pytest.fixture
def client() -> httpx.Client:
    with httpx.Client(
        base_url=API_ROOT,
        timeout=15.0,
        headers={"Authorization": f"Bearer {create_access_token('pytest')}"},
    ) as api_client:
        yield api_client


def _suffix() -> str:
    return uuid.uuid4().hex[:12]


def _definition_by_slug(
    client: httpx.Client,
    slug: str,
) -> dict[str, object]:
    response = client.get(
        "/catalog/attribute-definitions",
        params={
            "active_only": False,
            "search": slug,
            "limit": 100,
        },
    )
    assert response.status_code == 200, response.text
    matches = [item for item in response.json() if item["slug"] == slug]
    assert len(matches) == 1
    return matches[0]


def _resolved_rows_by_id(
    client: httpx.Client,
    path: str,
    target_ids: set[str],
    *,
    scope: str,
) -> dict[str, dict[str, object]]:
    cursor: str | None = None
    found: dict[str, dict[str, object]] = {}
    seen_cursors: set[str] = set()
    while True:
        params = {"limit": 500, "scope": scope}
        if cursor is not None:
            params["cursor"] = cursor
        response = client.get(path, params=params)
        assert response.status_code == 200, response.text
        for row in response.json():
            definition_id = row["definition"]["id"]
            if definition_id in target_ids:
                found[definition_id] = row
        if found.keys() >= target_ids:
            return found
        cursor = response.headers.get("X-Next-Cursor")
        assert cursor is not None
        assert cursor not in seen_cursors
        seen_cursors.add(cursor)


def _definition(**overrides: object) -> AttributeDefinition:
    values = {
        "name": "Test",
        "code": "test",
        "slug": "test",
        "internal_name": "test",
        "api_name": "test",
        "scope": "GLOBAL",
        "storage_kind": "ATTRIBUTE_VALUE",
        "data_type": "TEXT",
        "status": "ACTIVE",
        "validation_rules": {},
        "accepted_units": [],
        "examples": [],
        "forbidden_values": [],
        "confidence_threshold": 0.8,
    }
    values.update(overrides)
    return AttributeDefinition(**values)


def test_deterministic_normalization_examples() -> None:
    validator = AttributeValueValidator()
    capacity = _definition(
        data_type="CAPACITY", default_unit="TB", accepted_units=["TB", "GB"]
    )
    frequency = _definition(data_type="FREQUENCY", accepted_units=["GHz", "MHz"])
    exact = AttributeNormalizationRule(
        attribute_definition_id=uuid.uuid4(),
        rule_type="CASE_INSENSITIVE_EXACT",
        pattern="1024 GB",
        replacement="1 TB",
        priority=1,
        case_sensitive=False,
        is_active=True,
    )

    assert validator.normalize(capacity, "1 TB").canonical_value == "1TB"
    assert validator.normalize(capacity, "1 tb").canonical_value == "1TB"
    assert (
        validator.normalize(capacity, "1024 GB", rules=[exact]).canonical_value == "1TB"
    )
    assert validator.normalize(frequency, "5.6 Ghz").canonical_value == "5.6GHz"
    assert validator.normalize(frequency, "5600 mhz").canonical_value == "5600MHz"


def test_rule_priority_inactive_rule_and_invalid_regex() -> None:
    validator = AttributeValueValidator()
    definition = _definition()
    first = AttributeNormalizationRule(
        attribute_definition_id=uuid.uuid4(),
        rule_type="EXACT",
        pattern="WiFi7",
        replacement="Wi-Fi 7",
        priority=1,
        case_sensitive=True,
        is_active=True,
    )
    inactive = AttributeNormalizationRule(
        attribute_definition_id=first.attribute_definition_id,
        rule_type="EXACT",
        pattern="Wi-Fi 7",
        replacement="wrong",
        priority=2,
        case_sensitive=True,
        is_active=False,
    )
    invalid = AttributeNormalizationRule(
        attribute_definition_id=first.attribute_definition_id,
        rule_type="REGEX",
        pattern="[",
        replacement="x",
        priority=3,
        case_sensitive=False,
        is_active=True,
    )
    result = validator.normalize(definition, "WiFi7", rules=[invalid, inactive, first])
    assert result.canonical_value is None
    assert "Wi-Fi 7" in str(result.raw_value) or result.rules_applied
    assert any(
        "Invalid normalization regex" in item for item in result.validation_messages
    )


def test_user_regex_has_a_hard_execution_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(attribute_validation, "REGEX_TIMEOUT_SECONDS", 0.001)
    definition = _definition(regex_pattern="(a+)+$")

    result = AttributeValueValidator().normalize(
        definition,
        ("a" * 50_000) + "!",
    )

    assert result.canonical_value is None
    assert any("execution limit" in message for message in result.validation_messages)


def test_group_and_definition_crud_validation(client: httpx.Client) -> None:
    suffix = _suffix()
    group = client.post(
        "/catalog/attribute-groups",
        json={
            "name": f"Test Group {suffix}",
            "slug": f"test_group_{suffix}",
            "sort_order": 900,
        },
    )
    assert group.status_code == 201, group.text
    group_id = group.json()["id"]
    assert (
        client.post(
            "/catalog/attribute-groups",
            json={"name": "Duplicate", "slug": f"test_group_{suffix}"},
        ).status_code
        == 409
    )
    assert client.get(f"/catalog/attribute-groups/{group_id}").status_code == 200
    updated = client.patch(
        f"/catalog/attribute-groups/{group_id}",
        json={"sort_order": 901},
    )
    assert updated.status_code == 200
    assert updated.json()["sort_order"] == 901

    definition = client.post(
        "/catalog/attribute-definitions",
        json={
            "name": f"Test Attribute {suffix}",
            "slug": f"test_attribute_{suffix}",
            "api_name": f"test_attribute_{suffix}",
            "internal_name": f"test_attribute_{suffix}",
            "group_id": group_id,
            "scope": "GLOBAL",
            "storage_kind": "ATTRIBUTE_VALUE",
            "data_type": "TEXT",
            "minimum_length": 2,
            "maximum_length": 20,
        },
    )
    assert definition.status_code == 201, definition.text
    definition_id = definition.json()["id"]
    duplicate = client.post(
        "/catalog/attribute-definitions",
        json={
            "name": "Duplicate",
            "slug": f"test_attribute_{suffix}",
            "scope": "GLOBAL",
        },
    )
    assert duplicate.status_code == 409
    invalid_range = client.post(
        "/catalog/attribute-definitions",
        json={
            "name": "Invalid Range",
            "slug": f"invalid_range_{suffix}",
            "scope": "GLOBAL",
            "minimum_value": 10,
            "maximum_value": 1,
        },
    )
    assert invalid_range.status_code == 422
    invalid_filter = client.post(
        "/catalog/attribute-definitions",
        json={
            "name": "Invalid Filter",
            "slug": f"invalid_filter_{suffix}",
            "scope": "GLOBAL",
            "is_filter": True,
        },
    )
    assert invalid_filter.status_code == 422
    assert (
        client.post(
            "/catalog/attribute-definitions/reorder",
            json={"items": [{"id": definition_id, "sort_order": 5}]},
        ).status_code
        == 200
    )
    assert (
        client.delete(f"/catalog/attribute-definitions/{definition_id}").status_code
        == 204
    )
    assert client.delete(f"/catalog/attribute-groups/{group_id}").status_code == 204


def test_three_level_inheritance_and_deepest_override(
    client: httpx.Client,
) -> None:
    suffix = _suffix()
    category_ids = []
    parent_id = None
    for depth in range(3):
        response = client.post(
            "/categories",
            json={
                "name": f"Attribute Tree {depth} {suffix}",
                "code": f"attribute_tree_{depth}_{suffix}",
                "parent_id": parent_id,
            },
        )
        assert response.status_code == 201, response.text
        parent_id = response.json()["id"]
        category_ids.append(parent_id)
    definition = client.post(
        "/catalog/attribute-definitions",
        json={
            "name": f"Inherited {suffix}",
            "slug": f"inherited_{suffix}",
            "scope": "CATEGORY",
            "storage_kind": "ATTRIBUTE_VALUE",
            "data_type": "TEXT",
        },
    )
    assert definition.status_code == 201
    attribute_id = definition.json()["id"]
    root_assignment = client.post(
        f"/catalog/categories/{category_ids[0]}/attributes",
        json={"attribute_definition_id": attribute_id, "sort_order": 50},
    )
    assert root_assignment.status_code == 201, root_assignment.text
    leaf_assignment = client.post(
        f"/catalog/categories/{category_ids[2]}/attributes",
        json={
            "attribute_definition_id": attribute_id,
            "sort_order": 5,
            "is_required_override": True,
        },
    )
    assert leaf_assignment.status_code == 201
    item = _resolved_rows_by_id(
        client,
        f"/catalog/categories/{category_ids[2]}/attributes/resolved",
        {attribute_id},
        scope="CATEGORY",
    )[attribute_id]
    assert item["inherited_from_category_id"] == category_ids[2]
    assert item["sort_order"] == 5
    assert (
        client.post(
            f"/catalog/categories/{category_ids[2]}/attributes",
            json={"attribute_definition_id": attribute_id},
        ).status_code
        == 409
    )
    assert (
        client.delete(
            f"/catalog/categories/{category_ids[2]}/attributes/"
            f"{leaf_assignment.json()['id']}"
        ).status_code
        == 204
    )
    for category_id in reversed(category_ids):
        client.delete(f"/categories/{category_id}")
    client.delete(f"/catalog/attribute-definitions/{attribute_id}")


def test_product_values_history_delta_export_and_system_read_only(
    client: httpx.Client,
) -> None:
    suffix = _suffix()
    category = client.post(
        "/categories",
        json={
            "name": f"Value Category {suffix}",
            "code": f"value_category_{suffix}",
        },
    )
    assert category.status_code == 201
    category_id = category.json()["id"]
    product = client.post(
        "/products",
        json={
            "category_id": category_id,
            "name": f"Value Product {suffix}",
            "code": f"value_product_{suffix}",
            "sku": f"VALUE-{suffix}",
        },
    )
    assert product.status_code == 201
    product_id = product.json()["id"]
    definition = client.post(
        "/catalog/attribute-definitions",
        json={
            "name": f"Value Attribute {suffix}",
            "slug": f"value_attribute_{suffix}",
            "scope": "GLOBAL",
            "storage_kind": "ATTRIBUTE_VALUE",
            "data_type": "INTEGER",
            "minimum_value": 1,
            "maximum_value": 100,
        },
    )
    assert definition.status_code == 201
    attribute_id = definition.json()["id"]
    invalid = client.put(
        f"/catalog/products/{product_id}/attributes/{attribute_id}",
        json={"raw_value": 101},
    )
    assert invalid.status_code == 422
    created = client.put(
        f"/catalog/products/{product_id}/attributes/{attribute_id}",
        json={"raw_value": 42, "source_type": "MANUAL"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["canonical_value"] == 42
    updated = client.patch(
        f"/catalog/products/{product_id}/attributes/{attribute_id}",
        json={"raw_value": 43, "source_type": "API"},
    )
    assert updated.status_code == 200
    approved = client.post(
        f"/catalog/products/{product_id}/attributes/{attribute_id}/approve",
        json={"actor": "pytest"},
    )
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "APPROVED"
    history = client.get(f"/catalog/products/{product_id}/attributes/history")
    assert history.status_code == 200
    assert [row["action"] for row in history.json()][-3:] == [
        "CREATED",
        "UPDATED",
        "APPROVED",
    ]
    product_name = _definition_by_slug(client, "product_name")
    read_only = client.put(
        f"/catalog/products/{product_id}/attributes/{product_name['id']}",
        json={"raw_value": "Wrong"},
    )
    assert read_only.status_code == 409
    layout = client.get(f"/catalog/products/{product_id}/attributes")
    assert layout.status_code == 200
    system_name = next(
        row for row in layout.json() if row["definition"]["slug"] == "product_name"
    )
    assert system_name["value"] == f"Value Product {suffix}"
    export = client.get(f"/catalog/products/{product_id}/export")
    assert export.status_code == 200
    assert "inventory" not in str(export.json()).lower()
    assert "pricing" not in str(export.json()).lower()
    changes = client.get(
        "/catalog/attribute-changes",
        params={"cursor": 0, "product_id": product_id},
    )
    assert changes.status_code == 200
    cursors = [row["cursor"] for row in changes.json()]
    assert cursors == sorted(cursors)
    assert len(set(cursors)) == len(cursors)
    assert (
        client.delete(
            f"/catalog/products/{product_id}/attributes/{attribute_id}"
        ).status_code
        == 204
    )
    client.delete(f"/products/{product_id}")
    client.delete(f"/categories/{category_id}")
    client.delete(f"/catalog/attribute-definitions/{attribute_id}")


def test_bulk_is_atomic_and_admin_is_registered(client: httpx.Client) -> None:
    suffix = _suffix()
    category = client.post(
        "/categories",
        json={"name": f"Bulk {suffix}", "code": f"bulk_{suffix}"},
    ).json()
    product = client.post(
        "/products",
        json={
            "category_id": category["id"],
            "name": f"Bulk Product {suffix}",
            "code": f"bulk_product_{suffix}",
        },
    ).json()
    definitions = []
    for index in range(2):
        response = client.post(
            "/catalog/attribute-definitions",
            json={
                "name": f"Bulk Attribute {index} {suffix}",
                "slug": f"bulk_attribute_{index}_{suffix}",
                "scope": "GLOBAL",
                "data_type": "INTEGER",
                "minimum_value": 0,
                "maximum_value": 10,
            },
        )
        assert response.status_code == 201
        definitions.append(response.json())
    failed = client.post(
        f"/catalog/products/{product['id']}/attributes/bulk",
        json={
            "items": [
                {"attribute_id": definitions[0]["id"], "raw_value": 5},
                {"attribute_id": definitions[1]["id"], "raw_value": 99},
            ]
        },
    )
    assert failed.status_code == 422
    definition_ids = {item["id"] for item in definitions}
    values = _resolved_rows_by_id(
        client,
        f"/catalog/products/{product['id']}/attributes",
        definition_ids,
        scope="GLOBAL",
    )
    stored = {definition_id: row["value"] for definition_id, row in values.items()}
    assert stored == {
        definitions[0]["id"]: None,
        definitions[1]["id"]: None,
    }
    succeeded = client.post(
        f"/catalog/products/{product['id']}/attributes/bulk",
        json={
            "items": [
                {"attribute_id": definitions[0]["id"], "raw_value": 5},
                {"attribute_id": definitions[1]["id"], "raw_value": 9},
            ]
        },
    )
    assert succeeded.status_code == 200, succeeded.text
    assert [item["canonical_value"] for item in succeeded.json()] == [5, 9]
    admin = client.get("/catalog/attribute-admin")
    assert admin.status_code == 200
    assert "Product Attribute Administration" in admin.text
    client.delete(f"/products/{product['id']}")
    client.delete(f"/categories/{category['id']}")
    for definition in definitions:
        client.delete(f"/catalog/attribute-definitions/{definition['id']}")


def test_options_aliases_filters_compatibility_and_rules(
    client: httpx.Client,
) -> None:
    suffix = _suffix()
    category = client.post(
        "/categories",
        json={"name": f"Enum {suffix}", "code": f"enum_{suffix}"},
    ).json()
    product = client.post(
        "/products",
        json={
            "category_id": category["id"],
            "name": f"Enum Product {suffix}",
            "code": f"enum_product_{suffix}",
        },
    ).json()
    definition_response = client.post(
        "/catalog/attribute-definitions",
        json={
            "name": f"Form Factor {suffix}",
            "slug": f"form_factor_{suffix}",
            "scope": "CATEGORY",
            "data_type": "ENUM",
            "is_filter": True,
            "filter_type": "CHECKBOX",
            "is_compatibility_attribute": True,
            "compatibility_type": "MOTHERBOARD_FORM_FACTOR",
            "compatibility_priority": 10,
        },
    )
    assert definition_response.status_code == 201, definition_response.text
    definition = definition_response.json()
    assignment = client.post(
        f"/catalog/categories/{category['id']}/attributes",
        json={"attribute_definition_id": definition["id"], "sort_order": 3},
    )
    assert assignment.status_code == 201
    option = client.post(
        f"/catalog/attribute-definitions/{definition['id']}/options",
        json={
            "canonical_value": "Micro-ATX",
            "display_value": "Micro-ATX",
            "aliases": ["micro atx", "mATX"],
        },
    )
    assert option.status_code == 201, option.text
    duplicate_alias = client.post(
        f"/catalog/attribute-options/{option.json()['id']}/aliases",
        json={"alias": "MICRO ATX"},
    )
    assert duplicate_alias.status_code == 409
    value = client.put(
        f"/catalog/products/{product['id']}/attributes/{definition['id']}",
        json={"raw_value": "Micro ATX"},
    )
    assert value.status_code == 200, value.text
    assert value.json()["canonical_value"] == "Micro-ATX"
    filters = client.get(f"/catalog/categories/{category['id']}/filters")
    assert filters.status_code == 200
    assert filters.json()[0]["options"][0]["canonical_value"] == "Micro-ATX"
    compatibility = client.get(f"/catalog/categories/{category['id']}/compatibility")
    assert compatibility.status_code == 200
    assert compatibility.json()[0]["compatibility_type"] == ("MOTHERBOARD_FORM_FACTOR")
    invalid_rule = client.post(
        f"/catalog/attribute-definitions/{definition['id']}/normalization-rules",
        json={"rule_type": "REGEX", "pattern": "["},
    )
    assert invalid_rule.status_code == 422
    rule = client.post(
        f"/catalog/attribute-definitions/{definition['id']}/normalization-rules",
        json={
            "rule_type": "CASE_INSENSITIVE_EXACT",
            "pattern": "microatx",
            "replacement": "Micro ATX",
            "priority": 1,
        },
    )
    assert rule.status_code == 201
    assert (
        client.patch(
            f"/catalog/normalization-rules/{rule.json()['id']}",
            json={"is_active": False},
        ).status_code
        == 200
    )
    client.delete(f"/catalog/products/{product['id']}/attributes/{definition['id']}")
    client.delete(f"/products/{product['id']}")
    client.delete(f"/categories/{category['id']}")
    client.delete(f"/catalog/attribute-definitions/{definition['id']}")


def test_global_seed_registry_is_complete_and_idempotent(
    client: httpx.Client,
) -> None:
    first = client.post("/catalog/attribute-seed")
    second = client.post("/catalog/attribute-seed")
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == {"groups_created": 0, "definitions_created": 0}
    expected = {
        "product_name",
        "manufacturer",
        "mpn",
        "sku",
        "ean",
        "product_code",
        "category",
        "subcategory_level_1",
        "subcategory_level_2",
        "warranty",
        "device_dimensions",
        "device_weight",
        "intended_use",
        "power_consumption",
        "recommended_for",
        "color",
        "packaged_weight",
        "package_dimensions",
        "series",
        "package_contents",
        "material",
        "mini_text",
        "landing_page",
        "youtube_video",
        "manufacturer_url",
    }
    definitions = {slug: _definition_by_slug(client, slug) for slug in expected}
    assert definitions.keys() == expected
    assert definitions["product_name"]["source_path"] == "Product.name"
    assert definitions["ean"]["storage_kind"] == "CORE_FIELD"
    assert definitions["category"]["storage_kind"] == "CATEGORY_PATH"
    assert definitions["mini_text"]["storage_kind"] == "CONTENT_FIELD"


def test_catalog_attribute_system_has_no_inventory_import() -> None:
    violations = {}
    for path in CATALOG_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        forbidden = {
            item for item in imports if item.startswith("app.modules.inventory")
        }
        if forbidden:
            violations[str(path)] = forbidden
    assert violations == {}
