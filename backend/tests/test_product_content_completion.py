from __future__ import annotations

import asyncio
import os
import uuid

import httpx
import pytest
from app.core.security import create_access_token
from app.core.config import settings
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.product_content.models import Language

API = "http://localhost:8000/api/v1"
DATABASE_URL = os.getenv(
    "PRODUCT_CONTENT_INTEGRATION_DATABASE_URL",
    settings.database_url,
)


@pytest.fixture
def client() -> httpx.Client:
    with httpx.Client(
        base_url=API,
        timeout=20,
        headers={"Authorization": f"Bearer {create_access_token('pytest')}"},
    ) as value:
        yield value


@pytest.fixture
def language_cleanup() -> list[uuid.UUID]:
    language_ids: list[uuid.UUID] = []
    yield language_ids

    async def purge() -> None:
        if not language_ids:
            return
        engine = create_async_engine(DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessions() as session:
                await session.execute(
                    delete(Language).where(Language.id.in_(language_ids))
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(purge())


def create_product(client: httpx.Client) -> dict:
    token = uuid.uuid4().hex[:10]
    category = client.post(
        "/categories",
        json={"name": f"CMS {token}", "code": f"cms_{token}"},
    ).json()
    response = client.post(
        "/products",
        json={
            "category_id": category["id"],
            "name": f"CMS Product {token}",
            "code": f"cms_product_{token}",
            "manufacturer": "Codex",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def seeded_language(client: httpx.Client) -> dict:
    assert client.post("/content/seed").status_code == 200
    return next(
        item for item in client.get("/content/languages").json() if item["code"] == "sr"
    )


def test_language_and_content_type_complete_crud(
    client: httpx.Client,
    language_cleanup: list[uuid.UUID],
) -> None:
    token = uuid.uuid4().hex[:8]
    language = client.post(
        "/content/languages",
        json={
            "code": f"x-{token}",
            "name": f"Language {token}",
            "native_name": f"Native {token}",
        },
    )
    assert language.status_code == 201, language.text
    language_id = language.json()["id"]
    language_cleanup.append(uuid.UUID(language_id))
    assert client.get(f"/content/languages/{language_id}").status_code == 200
    updated = client.patch(
        f"/content/languages/{language_id}",
        json={"name": f"Updated {token}"},
    )
    assert updated.json()["name"] == f"Updated {token}"
    assert (
        client.delete(f"/content/languages/{language_id}").json()["is_active"] is False
    )
    assert (
        client.post(f"/content/languages/{language_id}/activate").json()["is_active"]
        is True
    )
    duplicate = client.post(
        "/content/languages",
        json={
            "code": f"x-{token}",
            "name": f"Other {token}",
            "native_name": "Other",
        },
    )
    assert duplicate.status_code == 409

    content_type = client.post(
        "/content/types",
        json={"name": f"Type {token}", "slug": f"type-{token}"},
    )
    assert content_type.status_code == 201
    type_id = content_type.json()["id"]
    assert client.get(f"/content/types/{type_id}").status_code == 200
    assert (
        client.patch(f"/content/types/{type_id}", json={"sort_order": 42}).json()[
            "sort_order"
        ]
        == 42
    )
    assert client.delete(f"/content/types/{type_id}").status_code == 200
    assert client.post(f"/content/types/{type_id}/activate").status_code == 200


def test_library_template_variables_conditions_preview_and_usage(
    client: httpx.Client,
) -> None:
    language = seeded_language(client)
    product = create_product(client)
    token = uuid.uuid4().hex[:8]
    library_payload = {
        "name": f"Hero {token}",
        "slug": f"hero-{token}",
        "item_kind": "BLOCK",
        "category": "Hero",
        "tags": ["hero", "pytest"],
        "language_id": language["id"],
        "title": "Hero",
        "content": "<h1>{{ProductName}}</h1><p>{{Manufacturer}}</p>{{Unknown}}",
    }
    library = client.post("/content/library", json=library_payload)
    assert library.status_code == 201, library.text
    item_id = library.json()["id"]
    revision = client.post(
        f"/content/library/{item_id}/revisions",
        json={**library_payload, "content": "<h1>{{ProductName}}</h1>"},
    )
    assert revision.status_code == 201
    history = client.get(f"/content/library/{item_id}/history")
    assert [row["revision"] for row in history.json()] == [2, 1]

    template = client.post(
        "/content/templates",
        json={"name": f"Template {token}", "slug": f"template-{token}"},
    )
    assert template.status_code == 201, template.text
    template_id = template.json()["id"]
    item = client.post(
        f"/content/templates/{template_id}/items",
        json={
            "library_item_id": item_id,
            "sort_order": 10,
            "condition_source": "Manufacturer",
            "condition_comparator": "EQ",
            "condition_value": "Codex",
        },
    )
    assert item.status_code == 201, item.text
    assert (
        client.post(
            f"/content/products/{product['id']}/templates/{template_id}"
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/content/products/{product['id']}/library/{item_id}",
            params={"order": 10},
        ).status_code
        == 201
    )
    variables = client.get(f"/content/products/{product['id']}/variables").json()[
        "variables"
    ]
    assert variables["ProductName"] == product["name"]
    preview = client.post(
        f"/content/products/{product['id']}/templates/{template_id}/preview",
        json={"language_id": language["id"], "viewport": "MOBILE"},
    )
    assert preview.status_code == 200, preview.text
    assert product["name"] in preview.json()["rendered_html"]
    assert preview.json()["viewport"] == "MOBILE"
    assert client.get(f"/content/library/{item_id}/usage").json()["usage_count"] == 1
    assert (
        client.get(f"/content/templates/{template_id}/usage").json()["usage_count"] == 1
    )
    clone = client.post(
        f"/content/templates/{template_id}/clone",
        params={"name": f"Clone {token}"},
    )
    assert clone.status_code == 201, clone.text


def test_reference_crud_link_metadata_scoring_prompts_search_and_diff(
    client: httpx.Client,
) -> None:
    language = seeded_language(client)
    product = create_product(client)
    token = uuid.uuid4().hex[:8]
    reference = {
        "language_id": language["id"],
        "title": "Manual",
        "url": "https://example.com/manual.pdf",
        "reference_type": "MANUAL",
    }
    document = client.post(
        f"/content/products/{product['id']}/documents", json=reference
    )
    document_id = document.json()["id"]
    assert client.get(f"/content/documents/{document_id}").status_code == 200
    assert (
        client.patch(
            f"/content/documents/{document_id}", json={**reference, "title": "New"}
        ).json()["title"]
        == "New"
    )
    link = client.patch(
        f"/content/documents/{document_id}/link",
        json={"status": "BROKEN", "error": "pytest"},
    )
    assert link.json()["link_status"] == "BROKEN"

    content_type = next(
        row
        for row in client.get("/content/types").json()
        if row["slug"] == "short_description"
    )
    content = client.post(
        f"/content/products/{product['id']}/entries",
        json={
            "language_id": language["id"],
            "content_type_id": content_type["id"],
            "content": f"Original {token}",
        },
    ).json()
    revised = client.patch(
        f"/content/entries/{content['id']}",
        json={
            "language_id": language["id"],
            "content_type_id": content_type["id"],
            "content": f"Changed {token}",
        },
    )
    assert revised.status_code == 200
    diff = client.get(
        f"/content/entries/{content['content_key']}/diff",
        params={"from_revision": 1, "to_revision": 2},
    )
    assert diff.status_code == 200
    assert diff.json()["diff"]

    policy = client.post(
        "/content/scoring-policies",
        json={"name": f"Policy {token}", "mandatory_sections": ["short_description"]},
    )
    assert policy.status_code == 201, policy.text
    score = client.post(
        f"/content/products/{product['id']}/score/{policy.json()['id']}"
    )
    assert score.status_code == 200
    assert score.json()["checks"]["has_short_description"] is True
    assert client.get(f"/content/products/{product['id']}/score-history").json()

    prompt = client.post(
        f"/content/types/{content_type['id']}/prompts",
        json={
            "description": "Metadata only",
            "prompt": "Describe {{ProductName}}",
            "variables": ["ProductName"],
            "examples": ["Good"],
            "negative_examples": ["Bad"],
        },
    )
    assert prompt.status_code == 201, prompt.text
    assert (
        client.get(f"/content/types/{content_type['id']}/prompts").json()[0]["version"]
        >= 1
    )
    search = client.get("/content/search", params={"query": token})
    assert search.status_code == 200
    assert search.json()["content"]
    assert (
        client.delete(f"/content/documents/{document_id}").json()["is_active"] is False
    )
    assert (
        client.get(
            "/content/documents",
            params={"product_id": product["id"], "active_only": False},
        ).status_code
        == 200
    )
