from __future__ import annotations

import json
import logging

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import (
    RequestContextMiddleware,
    stale_data_error_handler,
)
from app.core.observability import RequestObservabilityMiddleware, metrics
from app.core.rate_limit import InMemoryRateLimitBackend, RateLimitMiddleware
from app.core.security import create_access_token
from app.main import app


def _bearer(role: str = "system_admin") -> dict[str, str]:
    token = create_access_token("observability-test", (role,))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_rate_limit_is_stable_and_only_applies_to_high_risk_routes() -> None:
    test_app = FastAPI()

    @test_app.post("/jobs", status_code=202)
    async def submit_job() -> dict[str, bool]:
        return {"accepted": True}

    @test_app.get("/safe")
    async def safe() -> dict[str, bool]:
        return {"ok": True}

    backend = InMemoryRateLimitBackend(max_clients=100)
    test_app.add_middleware(
        RateLimitMiddleware,
        enabled=True,
        requests=2,
        window_seconds=60,
        max_clients=100,
        backend=backend,
    )
    test_app.add_middleware(RequestContextMiddleware)
    transport = httpx.ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/jobs")).status_code == 202
        assert (await client.post("/jobs")).status_code == 202
        rejected = await client.post("/jobs")
        for _ in range(5):
            assert (await client.get("/safe")).status_code == 200

    assert rejected.status_code == 429
    assert rejected.headers["retry-after"] == "60"
    assert rejected.headers["cache-control"] == "no-store"
    payload = rejected.json()
    assert payload["code"] == "RATE_LIMITED"
    assert payload["detail"]["code"] == "RATE_LIMITED"
    assert rejected.headers["x-request-id"] == payload["request_id"]


@pytest.mark.asyncio
async def test_request_metrics_and_structured_log_exclude_credentials(
    caplog: pytest.LogCaptureFixture,
) -> None:
    metrics.reset()
    test_app = FastAPI()

    @test_app.get("/objects/{object_id}")
    async def object_detail(object_id: str) -> dict[str, str]:
        return {"id": object_id}

    test_app.add_middleware(
        RequestObservabilityMiddleware,
        metrics_enabled=True,
        structured_logging=True,
    )
    test_app.add_middleware(RequestContextMiddleware)
    caplog.set_level(logging.INFO, logger="app.http")
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/objects/secret-object-id",
            headers={
                "Authorization": "Bearer must-never-be-logged",
                "X-Correlation-ID": "correlation-test",
                "X-Request-ID": "request-test",
            },
        )

    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "correlation-test"
    rendered = metrics.render()
    assert (
        'amh_http_requests_total{method="GET",'
        'route="/objects/{object_id}",status="200"} 1'
    ) in rendered
    assert "amh_http_request_duration_seconds_bucket" in rendered
    records = [record for record in caplog.records if record.name == "app.http"]
    assert records
    event = records[-1].event_data
    assert event["request_id"] == "request-test"
    assert event["correlation_id"] == "correlation-test"
    assert event["route"] == "/objects/{object_id}"
    assert event["status"] == 200
    assert "must-never-be-logged" not in json.dumps(event)
    assert "secret-object-id" not in json.dumps(event)


@pytest.mark.asyncio
async def test_metrics_endpoint_requires_admin_and_is_prometheus_compatible() -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/v1/metrics")).status_code == 401
        assert (
            await client.get(
                "/api/v1/metrics",
                headers=_bearer("read_only"),
            )
        ).status_code == 403
        response = await client.get(
            "/api/v1/metrics",
            headers=_bearer(),
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert "# TYPE amh_http_requests_total counter" in response.text
    assert "# TYPE amh_http_request_duration_seconds histogram" in response.text


@pytest.mark.asyncio
async def test_duplicate_authorization_headers_are_rejected() -> None:
    token = create_access_token("duplicate-header", ("system_admin",))
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/metrics",
            headers=[
                ("Authorization", f"Bearer {token}"),
                ("Authorization", "Bearer rotating-junk"),
            ],
        )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"


def test_openapi_documents_rate_limit_and_backend_unavailable_responses() -> None:
    responses = app.openapi()["paths"]["/api/v1/jobs"]["post"]["responses"]
    assert "429" in responses
    assert "503" in responses


@pytest.mark.asyncio
async def test_early_rate_limit_metrics_use_a_bounded_policy_label() -> None:
    metrics.reset()
    test_app = FastAPI()

    @test_app.post("/jobs/{job_id}")
    async def submit(job_id: str) -> dict[str, str]:
        return {"id": job_id}

    test_app.add_middleware(
        RateLimitMiddleware,
        enabled=True,
        requests=1,
        window_seconds=60,
        max_clients=100,
    )
    test_app.add_middleware(
        RequestObservabilityMiddleware,
        metrics_enabled=True,
        structured_logging=False,
    )
    test_app.add_middleware(RequestContextMiddleware)
    transport = httpx.ASGITransport(app=test_app)
    first_id = "00000000-0000-0000-0000-000000000001"
    rejected_id = "00000000-0000-0000-0000-000000000002"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post(f"/jobs/{first_id}")).status_code == 200
        rejected = await client.post(f"/jobs/{rejected_id}")

    assert rejected.status_code == 429
    rendered = metrics.render()
    assert 'route="rate-limit:execution",status="429"' in rendered
    assert rejected_id not in rendered


@pytest.mark.asyncio
async def test_stale_data_error_has_stable_concurrency_contract() -> None:
    test_app = FastAPI()
    test_app.add_exception_handler(StaleDataError, stale_data_error_handler)
    test_app.add_middleware(RequestContextMiddleware)

    @test_app.post("/stale")
    async def stale() -> None:
        raise StaleDataError("database row count did not match")

    transport = httpx.ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/stale", headers={"X-Request-ID": "stale-request"}
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "CONCURRENT_MODIFICATION",
            "message": "The resource changed during this operation",
        },
        "code": "CONCURRENT_MODIFICATION",
        "request_id": "stale-request",
    }
    assert response.headers["x-request-id"] == "stale-request"
