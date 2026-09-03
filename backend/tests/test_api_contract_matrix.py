from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.routing import APIRoute

from app.main import app


PUBLIC_PATHS = {
    "/",
    "/health",
    "/api/v1/health/",
    "/docs",
    "/redoc",
    "/api/v1/openapi.json",
    "/api/v1/auth/session",
}
UUID_VALUE = "00000000-0000-0000-0000-000000000000"
INTEGER_PARAMETERS = {
    "attempt",
    "cursor",
    "position",
    "revision",
    "sort_order",
    "version",
}


def _concrete_path(path: str) -> str:
    def replacement(match: re.Match[str]) -> str:
        name = match.group(0).strip("{}").split(":", 1)[0]
        if name in INTEGER_PARAMETERS or name.endswith(("_number", "_index")):
            return "1"
        if name == "content_key" or name.endswith(("_id", "_key")):
            return UUID_VALUE
        return "test"

    return re.sub(r"\{[^}]+\}", replacement, path)


def _effective_api_routes() -> Iterator[Any]:
    """Expand FastAPI 0.139 lazy included routers without private type imports."""
    for route in app.routes:
        effective_route_contexts = getattr(
            route,
            "effective_route_contexts",
            None,
        )
        if callable(effective_route_contexts):
            yield from effective_route_contexts()
        elif isinstance(route, APIRoute):
            yield route


def _protected_operations() -> list[tuple[str, str, str]]:
    operations: list[tuple[str, str, str]] = []
    for route in _effective_api_routes():
        if route.path in PUBLIC_PATHS:
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            operations.append(
                (
                    route.operation_id or route.name,
                    method,
                    _concrete_path(route.path),
                )
            )
    return operations


def test_openapi_operation_ids_security_and_error_contracts() -> None:
    specification = app.openapi()
    operation_ids: list[str] = []
    operation_count = 0
    for path, path_item in specification["paths"].items():
        for method, operation in path_item.items():
            if method not in {
                "delete",
                "get",
                "head",
                "options",
                "patch",
                "post",
                "put",
                "trace",
            }:
                continue
            operation_count += 1
            operation_id = operation.get("operationId")
            assert operation_id, f"{method.upper()} {path} lacks operationId"
            operation_ids.append(operation_id)
            if path not in PUBLIC_PATHS:
                assert operation.get("security"), (
                    f"{method.upper()} {path} lacks security"
                )
                responses = operation.get("responses", {})
                for code in ("401", "403", "422", "500"):
                    assert code in responses, (
                        f"{method.upper()} {path} lacks documented {code}"
                    )
    visible_operation_count = sum(
        len(route.methods - {"HEAD", "OPTIONS"})
        for route in _effective_api_routes()
        if route.include_in_schema
    )
    assert operation_count == visible_operation_count
    assert len(operation_ids) == len(set(operation_ids))


@pytest.mark.asyncio
async def test_every_protected_operation_rejects_missing_and_invalid_auth() -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://contract.test",
        timeout=30.0,
    ) as client:
        for operation_id, method, path in _protected_operations():
            missing = await client.request(method, path, json={})
            assert missing.status_code == 401, (
                operation_id,
                method,
                path,
                missing.status_code,
                missing.text,
            )
            invalid = await client.request(
                method,
                path,
                json={},
                headers={"Authorization": "Bearer invalid"},
            )
            assert invalid.status_code == 401, (
                operation_id,
                method,
                path,
                invalid.status_code,
                invalid.text,
            )
