from __future__ import annotations

import uuid

import httpx
import pytest

from app.core.security import create_access_token
from app.main import app


def bearer(subject: str, role: str) -> dict[str, str]:
    token = create_access_token(subject, (role,))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_job_management_routes_require_manage_permission() -> None:
    job_id = uuid.uuid4()
    url = f"/api/v1/jobs/{job_id}/cancel"
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthenticated = await client.post(url)
        reader = await client.post(
            url,
            headers=bearer("execution-reader", "read_only"),
        )
        operator = await client.post(
            url,
            headers=bearer("execution-operator", "execution_operator"),
        )

    assert unauthenticated.status_code == 401
    assert reader.status_code == 403
    assert operator.status_code == 404


@pytest.mark.asyncio
async def test_pending_job_can_be_cancelled_idempotently_via_api() -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    headers = bearer("execution-operator", "execution_operator")
    unique = uuid.uuid4().hex
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={
                "job_type": "forensic.noop",
                "queue": f"api-cancel-{unique}",
                "idempotency_key": f"api-cancel-{unique}",
            },
        )
        assert created.status_code == 202
        job_id = created.json()["id"]

        mismatched_idempotency = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={
                "job_type": "forensic.different",
                "queue": f"api-cancel-{unique}",
                "idempotency_key": f"api-cancel-{unique}",
            },
        )
        cancelled = await client.post(
            f"/api/v1/jobs/{job_id}/cancel",
            headers=headers,
        )
        cancelled_again = await client.post(
            f"/api/v1/jobs/{job_id}/cancel",
            headers=headers,
        )
        invalid_retry = await client.post(
            f"/api/v1/jobs/{job_id}/retry",
            headers=headers,
        )

    assert cancelled.status_code == 200
    assert mismatched_idempotency.status_code == 409
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled_again.status_code == 200
    assert cancelled_again.json()["version"] == cancelled.json()["version"]
    assert invalid_retry.status_code == 409


def test_openapi_documents_job_management_routes() -> None:
    schema = app.openapi()

    assert "/api/v1/jobs/{job_id}/cancel" in schema["paths"]
    assert "/api/v1/jobs/{job_id}/retry" in schema["paths"]
