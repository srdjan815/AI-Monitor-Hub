from __future__ import annotations

import uuid

import httpx
import pytest
from app.core.security import create_access_token

API = "http://localhost:8000/api/v1"


@pytest.fixture
def client() -> httpx.Client:
    with httpx.Client(
        base_url=API,
        timeout=20,
        headers={"Authorization": f"Bearer {create_access_token('pytest')}"},
    ) as value:
        yield value


def setup_product(client: httpx.Client) -> dict:
    token = uuid.uuid4().hex[:10]
    category = client.post(
        "/categories", json={"name": f"Content {token}", "code": f"content_{token}"}
    ).json()
    response = client.post(
        "/products",
        json={
            "category_id": category["id"],
            "name": f"Content Product {token}",
            "code": f"content_product_{token}",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_languages_types_content_workflow_history_and_rollback(
    client: httpx.Client,
) -> None:
    assert client.post("/content/seed").status_code == 200
    assert client.post("/content/seed").json() == {
        "languages_created": 0,
        "types_created": 0,
    }
    language = next(
        item for item in client.get("/content/languages").json() if item["code"] == "sr"
    )
    content_type = next(
        item
        for item in client.get("/content/types").json()
        if item["slug"] == "short_description"
    )
    product = setup_product(client)
    payload = {
        "language_id": language["id"],
        "content_type_id": content_type["id"],
        "title": "Naslov",
        "content": "Prva verzija sadržaja",
        "source_type": "MANUAL",
        "created_by": "pytest",
    }
    created = client.post(f"/content/products/{product['id']}/entries", json=payload)
    assert created.status_code == 201, created.text
    row = created.json()
    payload["content"] = "Druga verzija sadržaja"
    revised = client.patch(f"/content/entries/{row['id']}", json=payload)
    assert revised.status_code == 200
    assert revised.json()["revision"] == 2
    review = client.post(
        f"/content/entries/{revised.json()['id']}/workflow",
        json={"actor": "editor", "status": "WAITING_REVIEW"},
    )
    assert review.status_code == 200
    approved = client.post(
        f"/content/entries/{review.json()['id']}/workflow",
        json={"actor": "admin", "status": "APPROVED"},
    )
    assert approved.status_code == 200
    invalid = client.post(
        f"/content/entries/{approved.json()['id']}/workflow",
        json={"status": "REJECTED"},
    )
    assert invalid.status_code == 409
    history = client.get(f"/content/entries/{row['content_key']}/history")
    assert history.status_code == 200
    assert [item["revision"] for item in history.json()] == [4, 3, 2, 1]
    rollback = client.post(
        f"/content/entries/{row['content_key']}/rollback",
        json={"revision": 1, "actor": "admin"},
    )
    assert rollback.status_code == 200
    assert rollback.json()["content"] == "Prva verzija sadržaja"
    searched = client.get(
        "/content/entries", params={"product_id": product["id"], "status": "DRAFT"}
    )
    assert searched.status_code == 200
    assert searched.json()[0]["revision"] == 5


def test_seo_landing_documents_videos_score_export_and_delta(
    client: httpx.Client,
) -> None:
    client.post("/content/seed")
    language = next(
        item for item in client.get("/content/languages").json() if item["code"] == "sr"
    )
    product = setup_product(client)
    seo = client.post(
        f"/content/products/{product['id']}/seo",
        json={
            "language_id": language["id"],
            "seo_title": "Validan SEO naslov",
            "seo_description": "Dovoljno kratak SEO opis",
            "slug": f"seo-{uuid.uuid4().hex[:8]}",
        },
    )
    assert seo.status_code == 201
    landing = client.post(
        f"/content/products/{product['id']}/landing-pages",
        json={
            "language_id": language["id"],
            "title": "Kampanja",
            "slug": f"landing-{uuid.uuid4().hex[:8]}",
            "body": "Landing sadržaj",
        },
    )
    assert landing.status_code == 201
    document = client.post(
        f"/content/products/{product['id']}/documents",
        json={
            "language_id": language["id"],
            "title": "Datasheet",
            "url": "https://example.com/data.pdf",
            "reference_type": "DATASHEET",
        },
    )
    assert document.status_code == 201
    video = client.post(
        f"/content/products/{product['id']}/videos",
        json={
            "language_id": language["id"],
            "title": "Video",
            "url": "https://youtube.com/watch?v=test",
            "reference_type": "YOUTUBE",
        },
    )
    assert video.status_code == 201
    score = client.get(f"/content/products/{product['id']}/score")
    assert score.status_code == 200
    assert score.json()["score"] > 40
    exported = client.get(f"/content/products/{product['id']}/export")
    assert exported.status_code == 200
    assert len(exported.json()["seo"]) == 1
    assert len(exported.json()["landing_pages"]) == 1
    assert len(exported.json()["documents"]) == 1
    assert len(exported.json()["videos"]) == 1
    changes = client.get("/content/changes", params={"cursor": 0})
    assert changes.status_code == 200
    cursors = [item["cursor"] for item in changes.json()]
    assert cursors == sorted(cursors)
    assert len(cursors) == len(set(cursors))


def test_content_validation_duplicate_metadata_and_admin(client: httpx.Client) -> None:
    client.post("/content/seed")
    language = next(
        item for item in client.get("/content/languages").json() if item["code"] == "sr"
    )
    content_type = next(
        item
        for item in client.get("/content/types").json()
        if item["slug"] == "long_description"
    )
    first = setup_product(client)
    second = setup_product(client)
    payload = {
        "language_id": language["id"],
        "content_type_id": content_type["id"],
        "content": "Identičan sadržaj za detekciju",
        "source_type": "AI",
        "prompt": "Metadata only",
        "ai_model": "future-model",
        "confidence": 0.9,
    }
    one = client.post(f"/content/products/{first['id']}/entries", json=payload)
    two = client.post(f"/content/products/{second['id']}/entries", json=payload)
    assert one.status_code == 201
    assert two.status_code == 201
    assert one.json()["content_hash"] == two.json()["content_hash"]
    invalid_seo = client.post(
        f"/content/products/{first['id']}/seo",
        json={
            "language_id": language["id"],
            "seo_title": "x" * 71,
            "seo_description": "ok",
            "slug": "invalid",
        },
    )
    assert invalid_seo.status_code == 422
    admin = client.get("/content/admin")
    assert admin.status_code == 200
    assert "Product Content Administration" in admin.text
