from __future__ import annotations

import uuid

import httpx
import pytest
from app.core.security import create_access_token

from app.modules.catalog.formula_engine import FormulaEngine, FormulaError

API_ROOT = "http://localhost:8000/api/v1"


@pytest.fixture
def client() -> httpx.Client:
    with httpx.Client(
        base_url=API_ROOT,
        timeout=20.0,
        headers={"Authorization": f"Bearer {create_access_token('pytest')}"},
    ) as api_client:
        yield api_client


def suffix() -> str:
    return uuid.uuid4().hex[:10]


def create_definition(
    client: httpx.Client,
    token: str,
    name: str,
    *,
    data_type: str = "INTEGER",
) -> dict:
    response = client.post(
        "/catalog/attribute-definitions",
        json={
            "name": f"{name} {token}",
            "slug": f"{name.lower().replace(' ', '_')}_{token}",
            "scope": "GLOBAL",
            "storage_kind": "ATTRIBUTE_VALUE",
            "data_type": data_type,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_product(client: httpx.Client, token: str) -> tuple[dict, dict]:
    category_response = client.post(
        "/categories",
        json={"name": f"Platform {token}", "code": f"platform_{token}"},
    )
    assert category_response.status_code == 201
    category = category_response.json()
    product_response = client.post(
        "/products",
        json={
            "category_id": category["id"],
            "name": f"Platform Product {token}",
            "code": f"platform_product_{token}",
        },
    )
    assert product_response.status_code == 201
    return category, product_response.json()


def test_formula_engine_is_safe_and_detects_cycles() -> None:
    engine = FormulaEngine()
    assert engine.evaluate("modules * capacity", {"modules": 2, "capacity": 16}) == 32
    assert engine.evaluate("max(usb2 + usb3, 1)", {"usb2": 2, "usb3": 3}) == 5
    with pytest.raises(FormulaError):
        engine.evaluate("__import__('os').system('id')", {})
    with pytest.raises(FormulaError):
        engine.validate_graph({"a": {"b"}, "b": {"c"}, "c": {"a"}})


def test_family_template_assignment_clone_export_and_usage(
    client: httpx.Client,
) -> None:
    token = suffix()
    category, _ = create_product(client, token)
    definition = create_definition(client, token, "Capacity")
    family_response = client.post(
        "/catalog/attribute-families",
        json={
            "name": f"Storage {token}",
            "slug": f"storage_{token}",
            "description": "Storage family",
            "sort_order": 10,
        },
    )
    assert family_response.status_code == 201, family_response.text
    family = family_response.json()
    assert (
        client.post(
            f"/catalog/attribute-families/{family['id']}/items",
            json={"attribute_definition_id": definition["id"], "sort_order": 1},
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/catalog/attribute-families/{family['id']}/categories/{category['id']}"
        ).status_code
        == 201
    )
    usage = client.get(f"/catalog/attribute-families/{family['id']}/usage")
    assert usage.status_code == 200
    assert usage.json()["attributes"] == 1
    assert usage.json()["categories"] == 1

    template_response = client.post(
        "/catalog/attribute-templates",
        json={"name": f"Gaming Laptop {token}", "slug": f"gaming_{token}"},
    )
    assert template_response.status_code == 201
    template = template_response.json()
    assert (
        client.post(
            f"/catalog/attribute-templates/{template['id']}/items",
            json={
                "attribute_definition_id": definition["id"],
                "family_id": family["id"],
                "sort_order": 5,
                "is_required_override": True,
            },
        ).status_code
        == 201
    )
    exported = client.get(f"/catalog/attribute-templates/{template['id']}/export")
    assert exported.status_code == 200
    assert exported.json()["items"][0]["attribute_definition_id"] == definition["id"]
    clone = client.post(
        f"/catalog/attribute-templates/{template['id']}/clone",
        params={"name": f"Clone {token}", "slug": f"clone_{token}"},
    )
    assert clone.status_code == 200, clone.text
    assigned = client.post(
        f"/catalog/attribute-templates/{template['id']}/assign/{category['id']}"
    )
    assert assigned.status_code == 200
    resolved = client.get(
        f"/catalog/categories/{category['id']}/attributes/resolved",
        params={"template_id": template["id"], "limit": 500},
    )
    assert resolved.status_code == 200, resolved.text
    assert definition["id"] in {item["definition"]["id"] for item in resolved.json()}
    assert (
        client.delete(
            f"/catalog/attribute-templates/{template['id']}/assign/{category['id']}"
        ).status_code
        == 204
    )


def test_formula_derived_auto_recalculation_and_cycle_detection(
    client: httpx.Client,
) -> None:
    token = suffix()
    _, product = create_product(client, token)
    modules = create_definition(client, token, "Modules")
    capacity = create_definition(client, token, "Capacity")
    total = create_definition(client, token, "Total Memory")
    doubled = create_definition(client, token, "Doubled Memory")
    formula = client.post(
        "/catalog/attribute-formulas",
        json={
            "target_attribute_id": total["id"],
            "formula_kind": "FORMULA",
            "expression": f"{modules['api_name']} * {capacity['api_name']}",
        },
    )
    assert formula.status_code == 201, formula.text
    derived = client.post(
        "/catalog/attribute-formulas",
        json={
            "target_attribute_id": doubled["id"],
            "formula_kind": "DERIVED",
            "expression": f"{total['api_name']} * 2",
        },
    )
    assert derived.status_code == 201, derived.text
    preview = client.post(
        f"/catalog/attribute-formulas/{formula.json()['id']}/preview",
        json={
            "values": {
                modules["api_name"]: 2,
                capacity["api_name"]: 16,
            }
        },
    )
    assert preview.status_code == 200
    assert preview.json()["result"] == "32"
    assert (
        client.put(
            f"/catalog/products/{product['id']}/attributes/{modules['id']}",
            json={"raw_value": 2},
        ).status_code
        == 200
    )
    written = client.put(
        f"/catalog/products/{product['id']}/attributes/{capacity['id']}",
        json={"raw_value": 16},
    )
    assert written.status_code == 200, written.text
    layout = client.get(
        f"/catalog/products/{product['id']}/attributes/resolved",
        params={"include_unset": False, "limit": 500},
    )
    assert layout.status_code == 200, layout.text
    values = {
        item["definition"]["id"]: item["value"] for item in layout.json()["items"]
    }
    assert values[total["id"]] == 32
    assert values[doubled["id"]] == 64

    cycle = client.patch(
        f"/catalog/attribute-formulas/{formula.json()['id']}",
        json={"expression": f"{doubled['api_name']} + 1"},
    )
    assert cycle.status_code == 422
    recalculated = client.post(
        f"/catalog/products/{product['id']}/attributes/recalculate"
    )
    assert recalculated.status_code == 200
    assert recalculated.json()["values_recalculated"] >= 2


def test_lock_dependencies_atomic_bulk_prompt_history_and_usage(
    client: httpx.Client,
) -> None:
    token = suffix()
    _, first_product = create_product(client, token)
    _, second_product = create_product(client, f"{token}b")
    source = create_definition(client, token, "Source", data_type="TEXT")
    target = create_definition(client, token, "Target", data_type="TEXT")
    assert (
        client.put(
            f"/catalog/products/{first_product['id']}/attributes/{source['id']}",
            json={"raw_value": "DDR5"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/catalog/products/{first_product['id']}/attributes/{target['id']}",
            json={"raw_value": "Invalid"},
        ).status_code
        == 200
    )
    dependency = client.post(
        "/catalog/attribute-dependencies",
        json={
            "source_attribute_id": source["id"],
            "target_attribute_id": target["id"],
            "dependency_type": "ALLOWED_VALUES",
            "rule_config": {
                "when_source_in": ["DDR5"],
                "allowed_values": ["DDR5-compatible"],
            },
        },
    )
    assert dependency.status_code == 201, dependency.text
    validation = client.get(
        f"/catalog/products/{first_product['id']}/attributes/dependencies/validate"
    )
    assert validation.status_code == 200
    assert validation.json()["valid"] is False

    locked = client.post(
        f"/catalog/products/{first_product['id']}/attributes/{target['id']}/lock",
        json={"actor": "admin", "reason": "Approved specification"},
    )
    assert locked.status_code == 200
    assert locked.json()["is_locked"] is True
    blocked = client.patch(
        f"/catalog/products/{first_product['id']}/attributes/{target['id']}",
        json={"raw_value": "DDR5-compatible", "source_type": "AI"},
    )
    assert blocked.status_code == 409
    assert (
        client.post(
            f"/catalog/products/{first_product['id']}/attributes/{target['id']}/unlock",
            json={"actor": "admin"},
        ).status_code
        == 200
    )

    failed_bulk = client.post(
        "/catalog/attribute-bulk/commit",
        json={
            "items": [
                {
                    "product_id": first_product["id"],
                    "attribute_id": target["id"],
                    "raw_value": "DDR5-compatible",
                },
                {
                    "product_id": second_product["id"],
                    "attribute_id": str(uuid.uuid4()),
                    "raw_value": "broken",
                },
            ]
        },
    )
    assert failed_bulk.status_code == 404
    current = client.get(
        f"/catalog/products/{first_product['id']}/attributes/{target['id']}"
    ).json()
    assert current[0]["canonical_value"] == "Invalid"
    preview = client.post(
        "/catalog/attribute-bulk/preview",
        json={
            "items": [
                {
                    "product_id": first_product["id"],
                    "attribute_id": target["id"],
                    "raw_value": "DDR5-compatible",
                }
            ]
        },
    )
    assert preview.status_code == 200

    prompt_one = client.post(
        f"/catalog/attribute-definitions/{target['id']}/prompt-versions",
        json={"extraction_prompt": "Extract v1", "activate": True},
    )
    prompt_two = client.post(
        f"/catalog/attribute-definitions/{target['id']}/prompt-versions",
        json={
            "extraction_prompt": "Extract v2",
            "negative_examples": ["wrong"],
            "normalization_examples": [{"raw": "x", "canonical": "X"}],
            "activate": True,
        },
    )
    assert prompt_one.status_code == 201
    assert prompt_two.status_code == 201
    history = client.get(
        f"/catalog/attribute-definitions/{target['id']}/prompt-versions"
    )
    assert [item["version_number"] for item in history.json()][:2] == [2, 1]
    diff = client.get(
        f"/catalog/attribute-prompt-versions/{prompt_one.json()['id']}/diff/"
        f"{prompt_two.json()['id']}"
    )
    assert diff.status_code == 200
    assert "Extract v2" in diff.json()["extraction_prompt"]
    assert (
        client.post(
            f"/catalog/attribute-prompt-versions/{prompt_one.json()['id']}/activate"
        ).status_code
        == 200
    )
    usage = client.get(f"/catalog/attribute-definitions/{target['id']}/usage")
    assert usage.status_code == 200
    assert usage.json()["values"] == 1
    assert usage.json()["missing_values"] >= 0


def test_all_platform_admin_pages_load(client: httpx.Client) -> None:
    for page in (
        "families",
        "templates",
        "formulas",
        "derived",
        "dependencies",
        "prompts",
        "usage",
        "bulk",
        "locked",
    ):
        response = client.get(f"/catalog/attribute-admin/{page}")
        assert response.status_code == 200
        assert "Administration" in response.text
