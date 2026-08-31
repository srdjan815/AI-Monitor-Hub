from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.security import create_access_token
from app.main import app


def bearer(subject: str, role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject, (role,))}"}


@pytest.mark.asyncio
async def test_public_and_protected_route_classes() -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as client:
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/api/v1/health")).status_code == 200

        unauthenticated = await client.post("/api/v1/catalog/attribute-seed")
        assert unauthenticated.status_code == 401
        assert unauthenticated.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"
        assert unauthenticated.json()["request_id"]
        assert (
            unauthenticated.headers["x-request-id"]
            == unauthenticated.json()["request_id"]
        )

        unauthorized = await client.post(
            "/api/v1/catalog/attribute-seed",
            headers=bearer("reader", "read_only"),
        )
        assert unauthorized.status_code == 403
        assert unauthorized.json()["detail"]["code"] == "PERMISSION_DENIED"

        authorized_read = await client.get(
            "/api/v1/products",
            headers=bearer("reader", "read_only"),
        )
        assert authorized_read.status_code == 200


@pytest.mark.asyncio
async def test_authenticated_identity_is_backend_authoritative() -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthenticated = await client.get("/api/v1/auth/me")
        assert unauthenticated.status_code == 401

        response = await client.get(
            "/api/v1/auth/me",
            headers=bearer("supplier-user", "supplier_admin"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["subject"] == "supplier-user"
    assert payload["roles"] == ["supplier_admin"]
    assert "suppliers.write" in payload["permissions"]
    assert "supplier_sources.validate" in payload["permissions"]
    assert "token" not in payload


@pytest.mark.asyncio
async def test_raw_preview_requires_permission_and_server_setting() -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    url = (
        "/api/v1/content/products/00000000-0000-0000-0000-000000000000/"
        "templates/00000000-0000-0000-0000-000000000000/preview"
    )
    payload = {
        "language_id": "00000000-0000-0000-0000-000000000000",
        "trusted_raw": True,
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        forbidden = await client.post(
            url,
            json=payload,
            headers=bearer("editor", "content_editor"),
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["code"] == "PERMISSION_DENIED"

        disabled = await client.post(
            url,
            json=payload,
            headers=bearer("admin", "system_admin"),
        )
        assert disabled.status_code == 403
        assert disabled.json()["detail"] == "Trusted raw preview is disabled"


@pytest.mark.asyncio
async def test_transport_request_limit_returns_413() -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    oversized = b"x" * (settings.max_request_body_bytes + 1)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/products",
            content=oversized,
            headers={
                **bearer("admin", "system_admin"),
                "content-type": "application/json",
            },
        )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "PAYLOAD_TOO_LARGE"
    assert response.headers["x-request-id"] == response.json()["request_id"]


def test_production_configuration_rejects_insecure_defaults() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://postgres:password@db/app",
        )

    valid = Settings(
        app_env="production",
        database_url="postgresql+asyncpg://app:nondefault@db/app",
        backend_cors_origins=["https://admin.example.test/"],
        backend_allowed_hosts=["api.example.test"],
        cors_allow_credentials=True,
        auth_secret="x" * 48,
        rate_limit_enabled=True,
        rate_limit_backend="redis",
        rate_limit_shared_required=True,
        docs_enabled=False,
    )
    assert valid.backend_cors_origins == ["https://admin.example.test"]

    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://app:nondefault@db/app",
            backend_cors_origins=["https://admin.example.test"],
            backend_allowed_hosts=["api.example.test"],
            auth_secret="x" * 48,
            rate_limit_enabled=True,
            rate_limit_backend="redis",
            rate_limit_shared_required=True,
            rate_limit_fail_open_mutations=True,
            docs_enabled=False,
        )


def test_settings_ignore_compose_only_environment_values() -> None:
    configured = Settings(
        database_url="postgresql+asyncpg://test:test@db/test",
        postgres_db="compose_database",
        postgres_user="compose_user",
        postgres_password="compose_password",
    )

    assert configured.database_url.endswith("/test")


def test_shared_rate_limit_configuration_requires_redis_and_valid_networks() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="test",
            database_url="postgresql+asyncpg://test:test@db/test",
            rate_limit_shared_required=True,
            rate_limit_backend="memory",
        )

    with pytest.raises(ValidationError):
        Settings(
            app_env="test",
            database_url="postgresql+asyncpg://test:test@db/test",
            rate_limit_backend="redis",
            rate_limit_trusted_proxy_cidrs=["not-a-network"],
        )

    shared = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://test:test@db/test",
        rate_limit_enabled=True,
        rate_limit_backend="redis",
        rate_limit_shared_required=True,
        rate_limit_trusted_proxy_cidrs=["10.0.0.0/8"],
    )
    assert shared.rate_limit_backend == "redis"
    assert shared.rate_limit_shared_required


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", "/api/v1/products", {}),
        ("POST", "/api/v1/catalog/attribute-seed", None),
        (
            "POST",
            "/api/v1/catalog/products/00000000-0000-0000-0000-000000000000/"
            "attributes/00000000-0000-0000-0000-000000000000/approve",
            {},
        ),
        ("POST", "/api/v1/inventory/movements", {}),
        (
            "POST",
            "/api/v1/content/types/00000000-0000-0000-0000-000000000000/prompts",
            {},
        ),
        ("POST", "/api/v1/content/scoring-policies", {}),
        ("POST", "/api/v1/jobs", {}),
    ],
)
async def test_privileged_route_matrix(
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthenticated = await client.request(method, path, json=payload)
        assert unauthenticated.status_code == 401

        unauthorized = await client.request(
            method,
            path,
            json=payload,
            headers=bearer("reader", "read_only"),
        )
        assert unauthorized.status_code == 403

        authorized = await client.request(
            method,
            path,
            json=payload,
            headers=bearer("admin", "system_admin"),
        )
        assert authorized.status_code not in {401, 403, 500}


@pytest.mark.asyncio
async def test_invalid_and_expired_tokens_return_401() -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        invalid = await client.get(
            "/api/v1/products",
            headers={"Authorization": "Bearer invalid"},
        )
        expired = await client.get(
            "/api/v1/products",
            headers={
                "Authorization": (
                    f"Bearer {create_access_token('expired', expires_in=-1)}"
                )
            },
        )
    assert invalid.status_code == 401
    assert expired.status_code == 401
