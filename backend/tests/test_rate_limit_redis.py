from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.core.config import settings
from app.core.errors import RequestContextMiddleware
from app.core.observability import metrics
from app.core.rate_limit import (
    InMemoryRateLimitBackend,
    RateLimitBackend,
    RateLimitBackendUnavailable,
    RateLimitDecision,
    RateLimitMiddleware,
    RedisRateLimitBackend,
    high_risk_policy,
)
from app.core.security import create_access_token


@asynccontextmanager
async def redis_backends(
    count: int,
    *,
    max_clients: int = 100,
) -> AsyncIterator[tuple[str, list[RedisRateLimitBackend], Redis]]:
    namespace = f"amh:test:rate-limit:{uuid4().hex}"
    backends = [
        RedisRateLimitBackend(
            redis_url=settings.redis_url,
            redis_db=settings.redis_db,
            namespace=namespace,
            max_clients=max_clients,
            timeout_seconds=1.0,
        )
        for _ in range(count)
    ]
    client: Redis = Redis.from_url(
        settings.redis_url,
        db=settings.redis_db,
        decode_responses=False,
    )
    try:
        await client.ping()
        yield namespace, backends, client
    finally:
        keys = [key async for key in client.scan_iter(match=f"{{{namespace}}}:*")]
        if keys:
            await client.delete(*keys)
        for backend in backends:
            await backend.close()
        await client.aclose()


@pytest.mark.asyncio
async def test_in_memory_capacity_never_resets_an_active_window() -> None:
    backend = InMemoryRateLimitBackend(max_clients=2)
    assert (await backend.check("first", limit=1, window_seconds=60, now=10)).allowed
    assert (await backend.check("second", limit=1, window_seconds=60, now=10)).allowed

    capacity = await backend.check("third", limit=1, window_seconds=60, now=10)
    existing = await backend.check("first", limit=1, window_seconds=60, now=10)

    assert not capacity.allowed
    assert capacity.capacity_rejected
    assert capacity.retry_after == 60
    assert not existing.allowed
    assert not existing.capacity_rejected

    renewed = await backend.check("third", limit=1, window_seconds=60, now=71)
    assert renewed.allowed


@pytest.mark.asyncio
async def test_two_redis_backends_share_atomic_limit_and_bounded_keys() -> None:
    async with redis_backends(2) as (namespace, backends, client):
        decisions = await asyncio.gather(
            *[
                backends[index % 2].check(
                    "opaque-client-key",
                    limit=5,
                    window_seconds=30,
                )
                for index in range(20)
            ]
        )

        assert sum(decision.allowed for decision in decisions) == 5
        assert all(decision.retry_after >= 1 for decision in decisions)
        keys = [
            key.decode() async for key in client.scan_iter(match=f"{{{namespace}}}:*")
        ]
        assert len(keys) == 2
        assert all("opaque-client-key" not in key for key in keys)
        counter_key = next(key for key in keys if ":window:" in key)
        ttl_ms = await client.pttl(counter_key)
        assert 0 < ttl_ms <= 30_000
        members = await client.zrange(f"{{{namespace}}}:clients", 0, -1)
        assert all(b"opaque-client-key" not in member for member in members)


@pytest.mark.asyncio
async def test_redis_window_rollover_registry_recovery_and_reconnect() -> None:
    async with redis_backends(1, max_clients=1) as (
        namespace,
        backends,
        client,
    ):
        backend = backends[0]
        first = await backend.check("first-client", limit=1, window_seconds=1)
        rejected = await backend.check("first-client", limit=1, window_seconds=1)
        assert first.allowed
        assert not rejected.allowed

        counter_keys = [
            key async for key in client.scan_iter(match=f"{{{namespace}}}:window:*")
        ]
        assert len(counter_keys) == 1
        await client.delete(counter_keys[0])
        recovered = await backend.check(
            "first-client",
            limit=1,
            window_seconds=1,
        )
        capacity = await backend.check(
            "second-client",
            limit=1,
            window_seconds=1,
        )
        assert recovered.allowed
        assert capacity.capacity_rejected

        await backend._client.connection_pool.disconnect()
        after_reconnect = await backend.check(
            "first-client",
            limit=2,
            window_seconds=1,
        )
        assert after_reconnect.allowed

        await asyncio.sleep(1.1)
        rolled_over = await backend.check(
            "second-client",
            limit=1,
            window_seconds=1,
        )
        assert rolled_over.allowed
        registry_ttl = await client.pttl(f"{{{namespace}}}:clients")
        assert 0 < registry_ttl <= 1_000


def _limited_app(
    backend: RateLimitBackend,
    *,
    requests: int = 2,
) -> FastAPI:
    app = FastAPI()

    @app.post("/jobs", status_code=202)
    async def create_job() -> dict[str, bool]:
        return {"accepted": True}

    app.add_middleware(
        RateLimitMiddleware,
        enabled=True,
        requests=requests,
        window_seconds=60,
        max_clients=100,
        backend=backend,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://client.test"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


@pytest.mark.asyncio
async def test_valid_tokens_share_actor_budget_and_invalid_tokens_share_peer() -> None:
    backend = InMemoryRateLimitBackend(max_clients=100)
    app = _limited_app(backend, requests=1)
    transport = httpx.ASGITransport(app=app)
    first_token = create_access_token("same-actor", token_id="first")
    second_token = create_access_token("same-actor", token_id="second")

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/jobs",
            headers={
                "Authorization": f"Bearer {first_token}",
                "Origin": "https://client.test",
            },
        )
        same_actor = await client.post(
            "/jobs",
            headers={
                "Authorization": f"Bearer {second_token}",
                "Origin": "https://client.test",
            },
        )
        backend.clear()
        invalid_first = await client.post(
            "/jobs",
            headers={"Authorization": "Bearer rotating-invalid-one"},
        )
        invalid_second = await client.post(
            "/jobs",
            headers={"Authorization": "Bearer rotating-invalid-two"},
        )

    assert first.status_code == 202
    assert same_actor.status_code == 429
    assert same_actor.headers["access-control-allow-origin"] == "https://client.test"
    assert invalid_first.status_code == 202
    assert invalid_second.status_code == 429


@pytest.mark.asyncio
async def test_two_api_replicas_share_one_redis_budget() -> None:
    async with redis_backends(2) as (_, backends, _):
        clients = [
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=_limited_app(backend)),
                base_url="http://replica.test",
            )
            for backend in backends
        ]
        try:
            first = await clients[0].post("/jobs")
            second = await clients[1].post("/jobs")
            rejected = await clients[0].post("/jobs")
        finally:
            for client in clients:
                await client.aclose()

        assert first.status_code == 202
        assert second.status_code == 202
        assert rejected.status_code == 429
        assert rejected.headers["retry-after"] == "60"
        assert rejected.json()["code"] == "RATE_LIMITED"


class _UnavailableBackend:
    name = "unavailable-test"

    async def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        now: float | None = None,
    ) -> RateLimitDecision:
        del key, limit, window_seconds, now
        raise RateLimitBackendUnavailable("injected")

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_backend_unavailable_fails_closed_for_mutation_and_open_for_read() -> (
    None
):
    metrics.reset()
    app = FastAPI()

    @app.post("/jobs")
    async def submit() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/search")
    async def search() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(
        RateLimitMiddleware,
        enabled=True,
        requests=1,
        window_seconds=60,
        max_clients=100,
        backend=_UnavailableBackend(),
        fail_open_reads=True,
        fail_open_mutations=False,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://client.test"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        closed = await client.post(
            "/jobs",
            headers={"Origin": "https://client.test"},
        )
        opened = await client.get(
            "/search",
            headers={"Origin": "https://client.test"},
        )

    assert closed.status_code == 503
    assert closed.headers["retry-after"] == "1"
    assert closed.headers["access-control-allow-origin"] == "https://client.test"
    assert closed.json()["code"] == "RATE_LIMIT_BACKEND_UNAVAILABLE"
    assert opened.status_code == 200
    rendered = metrics.render()
    assert 'decision="fail_closed"' in rendered
    assert 'decision="fail_open"' in rendered


def test_high_risk_policy_covers_amplification_routes_and_query_search() -> None:
    assert high_risk_policy("/catalog/attribute-bulk/commit", "POST") == "bulk"
    assert (
        high_risk_policy("/catalog/products/id/attributes/validate", "POST") == "bulk"
    )
    assert high_risk_policy("/catalog/attribute-templates/import", "POST") == "bulk"
    assert high_risk_policy("/catalog/attribute-groups/reorder", "PATCH") == "bulk"
    assert high_risk_policy("/products", "GET", b"search=term") == "search"
    assert high_risk_policy("/products", "GET", b"se%61rch=term") == "search"
    assert high_risk_policy("/jobs/id/cancel", "POST") == "execution-control"
    assert high_risk_policy("/content/seed", "POST") == "seed"
    assert high_risk_policy("/inventory/reservations/expire", "POST") == "bulk"
    assert (
        high_risk_policy(
            "/products/id/attributes/dependencies/validate",
            "GET",
        )
        == "validation"
    )
    assert high_risk_policy("/products/id/export", "OPTIONS") is None
    assert high_risk_policy("/safe", "GET") is None


def test_trusted_proxy_chain_is_validated_from_right_to_left() -> None:
    middleware = RateLimitMiddleware(
        app=object(),
        enabled=True,
        requests=1,
        window_seconds=60,
        max_clients=100,
        trusted_proxy_cidrs=("127.0.0.0/8", "10.0.0.0/8"),
    )
    base_scope = {
        "client": ("127.0.0.1", 12345),
        "headers": [
            (
                b"x-forwarded-for",
                b"203.0.113.9, 198.51.100.7, 10.0.0.8",
            )
        ],
    }
    assert middleware._client_host(base_scope) == "198.51.100.7"

    malformed = {
        **base_scope,
        "headers": [(b"x-forwarded-for", b"not-an-ip")],
    }
    duplicate = {
        **base_scope,
        "headers": [
            (b"x-forwarded-for", b"198.51.100.7"),
            (b"x-forwarded-for", b"203.0.113.9"),
        ],
    }
    assert middleware._client_host(malformed) == "127.0.0.1"
    assert middleware._client_host(duplicate) == "127.0.0.1"
