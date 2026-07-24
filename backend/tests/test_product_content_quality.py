from __future__ import annotations

import ast
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from app.core.security import create_access_token

from app.modules.product_content.completion import ContentCompletionService
from app.modules.product_content.security import (
    compare_values,
    interpolate_variables,
    sanitize_preview,
)

API = "http://localhost:8000/api/v1"
MODULE_ROOT = (
    Path(__file__).resolve().parents[1] / "app" / "modules" / "product_content"
)


@pytest.fixture
def client() -> httpx.Client:
    with httpx.Client(
        base_url=API,
        timeout=20,
        headers={"Authorization": f"Bearer {create_access_token('pytest')}"},
    ) as value:
        yield value


def token() -> str:
    return uuid.uuid4().hex[:10]


def product(client: httpx.Client) -> dict:
    suffix = token()
    category = client.post(
        "/categories",
        json={"name": f"Quality {suffix}", "code": f"quality_{suffix}"},
    ).json()
    response = client.post(
        "/products",
        json={
            "category_id": category["id"],
            "name": f"<Admin> Product {suffix}",
            "code": f"quality_product_{suffix}",
            "manufacturer": "Quality",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def language(client: httpx.Client) -> dict:
    assert client.post("/content/seed").status_code == 200
    return next(
        row for row in client.get("/content/languages").json() if row["code"] == "sr"
    )


def test_condition_engine_and_or_not_and_missing_values() -> None:
    values = {"CPU": "Zen", "Warranty": 48}
    conditions = [
        SimpleNamespace(
            source="CPU",
            comparator="EQ",
            expected_value="Zen",
            boolean_operator="AND",
        ),
        SimpleNamespace(
            source="Warranty",
            comparator="GT",
            expected_value="36",
            boolean_operator="AND",
        ),
    ]
    assert ContentCompletionService._conditions(conditions, values) is True
    conditions[1].boolean_operator = "OR"
    conditions[0].expected_value = "Other"
    assert ContentCompletionService._conditions(conditions, values) is True
    conditions[1].boolean_operator = "NOT"
    conditions[0].expected_value = "Zen"
    conditions[1].expected_value = "100"
    assert ContentCompletionService._conditions(conditions, values) is True
    assert compare_values("EXISTS", values.get("Missing"), None) is False


def test_invalid_condition_is_rejected_by_schema(client: httpx.Client) -> None:
    item_id = uuid.uuid4()
    response = client.post(
        f"/content/template-items/{item_id}/conditions",
        json={
            "source": "CPU",
            "comparator": "__import__",
            "boolean_operator": "EXEC",
        },
    )
    assert response.status_code == 422


def test_condition_model_cannot_form_cycles() -> None:
    source = (MODULE_ROOT / "models.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    condition = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ContentTemplateCondition"
    )
    assigned = {
        target.id
        for node in condition.body
        if isinstance(node, ast.AnnAssign)
        and isinstance((target := node.target), ast.Name)
    }
    assert "parent_condition_id" not in assigned
    assert "child_condition_id" not in assigned


def test_variable_interpolation_reports_unknown_malformed_and_escapes() -> None:
    rendered, unknown, malformed = interpolate_variables(
        "{{ProductName}} {{Unknown}} {{__class__}} {{Bad.Name}}",
        {"ProductName": "<img src=x onerror=alert(1)>"},
    )
    assert "&lt;img" in rendered
    assert unknown == ["Unknown"]
    assert "{{__class__}}" in malformed
    assert "{{Bad.Name}}" in malformed
    assert "__class__" not in unknown


def test_preview_sanitizer_removes_active_content() -> None:
    source = (
        '<script>alert(1)</script><a href="javascript:alert(2)" '
        'onclick="alert(3)">safe</a><iframe src="https://evil.test/x"></iframe>'
    )
    sanitized = sanitize_preview(source)
    assert "<script" not in sanitized
    assert "javascript:" not in sanitized
    assert "onclick" not in sanitized
    assert "evil.test" not in sanitized
    assert "safe" in sanitized


@pytest.mark.parametrize(
    "payload,forbidden",
    [
        ("<svg><script>alert(1)</script></svg>", ("<svg", "<script")),
        ("<math><mi href='javascript:x'>x</mi></math>", ("<math", "javascript:")),
        ("<a href='JaVaScRiPt:alert(1)'>x</a>", ("javascript:",)),
        ("<a href='&#x6a;avascript:alert(1)'>x</a>", ("javascript:",)),
        ("<img src=x OnErRoR=alert(1)>", ("<img", "onerror")),
        ("<iframe srcdoc='<script>x</script>'></iframe>", ("iframe", "srcdoc")),
        ("<a href='data:text/html,x'>x</a>", ("data:text/html",)),
        ("<div style='width:expression(alert(1))'>x</div>", ("style=", "expression")),
        ("<div><p><b>nested", ("<script",)),
    ],
)
def test_security_edge_payloads_are_sanitized(
    payload: str,
    forbidden: tuple[str, ...],
) -> None:
    sanitized = sanitize_preview(payload).lower()
    assert all(value not in sanitized for value in forbidden)


def test_excessive_conditions_fail_closed() -> None:
    conditions = [
        SimpleNamespace(
            source="CPU",
            comparator="EXISTS",
            expected_value=None,
            boolean_operator="AND",
        )
        for _ in range(65)
    ]
    assert ContentCompletionService._conditions(conditions, {"CPU": "x"}) is False


def test_product_field_and_attribute_variable_resolution(
    client: httpx.Client,
) -> None:
    row = product(client)
    suffix = token()
    definition = client.post(
        "/catalog/attribute-definitions",
        json={
            "name": f"Quality Attribute {suffix}",
            "slug": f"quality_attribute_{suffix}",
            "api_name": f"QualityAttribute{suffix}",
            "scope": "GLOBAL",
            "storage_kind": "ATTRIBUTE_VALUE",
            "data_type": "TEXT",
        },
    )
    assert definition.status_code == 201, definition.text
    stored = client.put(
        f"/catalog/products/{row['id']}/attributes/{definition.json()['id']}",
        json={"raw_value": "Resolved", "source_type": "MANUAL"},
    )
    assert stored.status_code == 200, stored.text
    variables = client.get(f"/content/products/{row['id']}/variables").json()[
        "variables"
    ]
    assert variables["ProductName"] == row["name"]
    assert variables["Manufacturer"] == "Quality"
    assert variables[definition.json()["api_name"]] == "Resolved"


def test_preview_is_sanitized_and_raw_requires_explicit_trust(
    client: httpx.Client,
) -> None:
    lang = language(client)
    row = product(client)
    suffix = token()
    library = client.post(
        "/content/library",
        json={
            "name": f"Unsafe {suffix}",
            "slug": f"unsafe-{suffix}",
            "item_kind": "BLOCK",
            "language_id": lang["id"],
            "content": "<script>x()</script><b>{{ProductName}}</b>",
        },
    ).json()
    template = client.post(
        "/content/templates",
        json={"name": f"Unsafe Template {suffix}"},
    ).json()
    item = client.post(
        f"/content/templates/{template['id']}/items",
        json={"library_item_id": library["id"]},
    )
    assert item.status_code == 201
    safe = client.post(
        f"/content/products/{row['id']}/templates/{template['id']}/preview",
        json={"language_id": lang["id"], "viewport": "RAW"},
    ).json()
    assert "<script" not in safe["rendered_html"]
    assert "&lt;Admin&gt;" in safe["rendered_html"]
    trusted = client.post(
        f"/content/products/{row['id']}/templates/{template['id']}/preview",
        json={
            "language_id": lang["id"],
            "viewport": "RAW",
            "trusted_raw": True,
        },
    )
    assert trusted.status_code == 403
    assert trusted.json()["detail"] == "Trusted raw preview is disabled"


def test_seo_revision_history_rollback_and_duplicate_slug(
    client: httpx.Client,
) -> None:
    lang = language(client)
    row = product(client)
    suffix = token()
    payload = {
        "language_id": lang["id"],
        "seo_title": "Original quality SEO title",
        "seo_description": "Original quality SEO description",
        "slug": f"quality-seo-{suffix}",
    }
    created = client.post(f"/content/products/{row['id']}/seo", json=payload)
    assert created.status_code == 201
    duplicate = client.post(
        f"/content/products/{product(client)['id']}/seo", json=payload
    )
    assert duplicate.status_code == 409
    payload["seo_title"] = "Revised quality SEO title"
    revised = client.patch(f"/content/seo/{created.json()['id']}", json=payload)
    assert revised.status_code == 201, revised.text
    key = revised.json()["seo_key"]
    history = client.get(f"/content/seo/{key}/history").json()
    assert [item["revision"] for item in history] == [2, 1]
    rolled = client.post(f"/content/seo/{key}/rollback", json={"revision": 1})
    assert rolled.status_code == 201, rolled.text
    assert rolled.json()["revision"] == 3
    assert rolled.json()["seo_title"] == "Original quality SEO title"


def test_landing_revision_rollback_and_schedule_validation(
    client: httpx.Client,
) -> None:
    lang = language(client)
    row = product(client)
    suffix = token()
    invalid = client.post(
        f"/content/products/{row['id']}/landing-pages",
        json={
            "language_id": lang["id"],
            "title": "Invalid",
            "slug": f"invalid-{suffix}",
            "body": "Body",
            "publish_at": "2030-02-01T00:00:00Z",
            "expire_at": "2030-01-01T00:00:00Z",
        },
    )
    assert invalid.status_code == 422
    payload = {
        "language_id": lang["id"],
        "title": "Original",
        "slug": f"landing-{suffix}",
        "body": "Original body",
    }
    created = client.post(
        f"/content/products/{row['id']}/landing-pages", json=payload
    ).json()
    payload["body"] = "Revised body"
    revised = client.patch(
        f"/content/landing-pages/{created['id']}", json=payload
    ).json()
    history = client.get(
        f"/content/landing-pages/{revised['landing_key']}/history"
    ).json()
    assert [item["revision"] for item in history] == [2, 1]
    rollback = client.post(
        f"/content/landing-pages/{revised['landing_key']}/rollback",
        json={"revision": 1},
    )
    assert rollback.status_code == 201
    assert rollback.json()["body"] == "Original body"


def test_video_crud_link_metadata_and_soft_delete(client: httpx.Client) -> None:
    lang = language(client)
    row = product(client)
    payload = {
        "language_id": lang["id"],
        "title": "Quality Video",
        "url": "https://youtube.com/watch?v=quality",
        "reference_type": "YOUTUBE",
        "sort_order": 2,
    }
    created = client.post(f"/content/products/{row['id']}/videos", json=payload).json()
    payload["title"] = "Updated Quality Video"
    updated = client.patch(f"/content/videos/{created['id']}", json=payload)
    assert updated.json()["title"] == payload["title"]
    checked = client.patch(
        f"/content/videos/{created['id']}/link",
        json={"status": "OK"},
    )
    assert checked.json()["link_status"] == "OK"
    deleted = client.delete(f"/content/videos/{created['id']}")
    assert deleted.json()["is_active"] is False
    assert any(
        item["id"] == created["id"]
        for item in client.get(
            "/content/videos",
            params={"product_id": row["id"], "active_only": False},
        ).json()
    )


def test_template_ordering_reference_protection_and_transaction_rollback(
    client: httpx.Client,
) -> None:
    lang = language(client)
    suffix = token()
    library = client.post(
        "/content/library",
        json={
            "name": f"Referenced {suffix}",
            "item_kind": "SNIPPET",
            "language_id": lang["id"],
            "content": "Referenced",
        },
    ).json()
    template_payload = {
        "name": f"Ordering {suffix}",
        "slug": f"ordering-{suffix}",
    }
    template = client.post("/content/templates", json=template_payload).json()
    item = client.post(
        f"/content/templates/{template['id']}/items",
        json={"library_item_id": library["id"], "sort_order": 20},
    )
    assert item.status_code == 201
    detail = client.get(f"/content/templates/{template['id']}").json()
    assert detail["items"][0]["sort_order"] == 20
    assert client.delete(f"/content/library/{library['id']}").status_code == 200
    assert client.get(f"/content/templates/{template['id']}").status_code == 200
    duplicate = client.post("/content/templates", json=template_payload)
    assert duplicate.status_code == 409
    assert client.get("/content/templates").status_code == 200


def test_prompt_version_activation_and_score_history(
    client: httpx.Client,
) -> None:
    lang = language(client)
    content_type = next(
        row
        for row in client.get("/content/types").json()
        if row["slug"] == "short_description"
    )
    first = client.post(
        f"/content/types/{content_type['id']}/prompts",
        json={"prompt": "First {{ProductName}}"},
    )
    second = client.post(
        f"/content/types/{content_type['id']}/prompts",
        json={"prompt": "Second {{ProductName}}"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert (
        client.post(f"/content/prompts/{first.json()['id']}/activate").status_code
        == 200
    )
    prompts = client.get(f"/content/types/{content_type['id']}/prompts").json()
    active = [row for row in prompts if row["is_active"]]
    assert [row["id"] for row in active] == [first.json()["id"]]

    row = product(client)
    content = client.post(
        f"/content/products/{row['id']}/entries",
        json={
            "language_id": lang["id"],
            "content_type_id": content_type["id"],
            "content": "Quality score content",
        },
    )
    assert content.status_code == 201
    policy = client.post(
        "/content/scoring-policies",
        json={
            "name": f"Quality Policy {token()}",
            "short_description_weight": 100,
            "long_description_weight": 0,
            "seo_weight": 0,
            "landing_weight": 0,
            "document_weight": 0,
            "video_weight": 0,
            "translation_weight": 0,
            "mandatory_sections": ["short_description"],
        },
    )
    assert policy.status_code == 201
    score = client.post(f"/content/products/{row['id']}/score/{policy.json()['id']}")
    assert score.status_code == 200
    assert score.json()["score"] == 100
    history = client.get(
        f"/content/products/{row['id']}/score-history",
        params={"score_type": "CONTENT"},
    ).json()
    assert history[0]["score"] == 100


def test_content_schedule_and_seo_scoring_validation(
    client: httpx.Client,
) -> None:
    lang = language(client)
    row = product(client)
    content_type = next(
        item
        for item in client.get("/content/types").json()
        if item["slug"] == "long_description"
    )
    invalid = client.post(
        f"/content/products/{row['id']}/entries",
        json={
            "language_id": lang["id"],
            "content_type_id": content_type["id"],
            "content": "Invalid schedule",
            "publish_at": "2030-02-01T00:00:00Z",
            "expire_at": "2030-01-01T00:00:00Z",
        },
    )
    assert invalid.status_code == 422
    seo_token = token()
    seo = client.post(
        f"/content/products/{row['id']}/seo",
        json={
            "language_id": lang["id"],
            "seo_title": f"Valid quality SEO {seo_token}",
            "seo_description": (
                "A sufficiently detailed quality SEO description that has "
                "the expected length for deterministic scoring validation "
                f"{seo_token}."
            ),
            "seo_keywords": "quality,pytest",
            "canonical_url": "https://example.test/quality",
            "slug": f"quality-score-{seo_token}",
            "open_graph": {"title": "Quality"},
            "twitter_card": {"card": "summary"},
            "schema_org": {"@type": "Product"},
        },
    )
    assert seo.status_code == 201
    score = client.post(f"/content/products/{row['id']}/seo/{seo.json()['id']}/score")
    assert score.status_code == 200
    assert score.json()["checks"]["unique"] is True
    assert score.json()["score"] >= 80


def test_naive_schedule_is_rejected_and_offsets_are_preserved(
    client: httpx.Client,
) -> None:
    lang = language(client)
    row = product(client)
    content_type = next(
        item
        for item in client.get("/content/types").json()
        if item["slug"] == "long_description"
    )
    naive = client.post(
        f"/content/products/{row['id']}/entries",
        json={
            "language_id": lang["id"],
            "content_type_id": content_type["id"],
            "content": "Naive",
            "publish_at": "2030-03-31T01:30:00",
        },
    )
    assert naive.status_code == 422
    aware = client.post(
        f"/content/products/{row['id']}/entries",
        json={
            "language_id": lang["id"],
            "content_type_id": content_type["id"],
            "content": "Offset aware",
            "publish_at": "2030-03-31T01:30:00+01:00",
            "expire_at": "2030-03-31T04:30:00+02:00",
        },
    )
    assert aware.status_code == 201, aware.text
    assert aware.json()["publish_at"].endswith("Z")


def test_export_labels_raw_source_and_excludes_deactivated_references(
    client: httpx.Client,
) -> None:
    lang = language(client)
    row = product(client)
    document = client.post(
        f"/content/products/{row['id']}/documents",
        json={
            "language_id": lang["id"],
            "title": "Inactive export",
            "url": f"https://example.test/{token()}.pdf",
            "reference_type": "MANUAL",
        },
    ).json()
    assert client.delete(f"/content/documents/{document['id']}").status_code == 200
    exported = client.get(f"/content/products/{row['id']}/export")
    assert exported.status_code == 200
    contract = exported.json()["content_contract"]
    assert contract == {
        "representation": "stored_source",
        "sanitized": False,
        "publishable": False,
    }
    assert all(item["id"] != document["id"] for item in exported.json()["documents"])


def test_search_pagination_and_architecture_boundaries(
    client: httpx.Client,
) -> None:
    response = client.get(
        "/content/search",
        params={"query": "Quality", "offset": 0, "limit": 1},
    )
    assert response.status_code == 200
    assert all(len(rows) <= 1 for rows in response.json().values())

    forbidden = {"supplier", "pricing", "inventory", "import_engine"}
    for path in MODULE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        assert not any(
            part in imported.lower() for imported in imports for part in forbidden
        )
    model_source = (MODULE_ROOT / "models.py").read_text(encoding="utf-8")
    classes = [
        node.name
        for node in ast.parse(model_source).body
        if isinstance(node, ast.ClassDef)
    ]
    assert "Product" not in classes

    for path in (MODULE_ROOT / "routers").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "select"
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"commit", "rollback", "flush"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "session"
            for node in ast.walk(tree)
        )
