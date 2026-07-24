from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import math
import threading
import time
from collections import OrderedDict
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast
from urllib.parse import parse_qsl

from fastapi import HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.errors import current_request_id
from app.core.observability import metrics, retry_after_seconds
from app.core.security import Principal, authenticate_token


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int
    capacity_rejected: bool = False


class RateLimitBackendUnavailable(RuntimeError):
    """The optional limiter backend could not produce an atomic decision."""


class RateLimitBackend(Protocol):
    name: str

    async def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        now: float | None = None,
    ) -> RateLimitDecision: ...

    async def close(self) -> None: ...


@dataclass(slots=True)
class _Window:
    count: int
    reset_at: float


class InMemoryRateLimitBackend:
    """Thread-safe fixed-window backend scoped to one API process."""

    name = "memory"

    def __init__(self, max_clients: int) -> None:
        self.max_clients = max_clients
        self._lock = threading.Lock()
        self._windows: OrderedDict[str, _Window] = OrderedDict()

    async def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        now: float | None = None,
    ) -> RateLimitDecision:
        checked_at = time.monotonic() if now is None else now
        with self._lock:
            self._prune_expired(checked_at)
            current = self._windows.get(key)
            if current is None:
                if len(self._windows) >= self.max_clients:
                    earliest = min(window.reset_at for window in self._windows.values())
                    return RateLimitDecision(
                        allowed=False,
                        retry_after=retry_after_seconds(earliest, checked_at),
                        capacity_rejected=True,
                    )
                self._windows[key] = _Window(
                    count=1,
                    reset_at=checked_at + window_seconds,
                )
                return RateLimitDecision(True, window_seconds)
            if current.count >= limit:
                return RateLimitDecision(
                    False,
                    retry_after_seconds(current.reset_at, checked_at),
                )
            current.count += 1
            return RateLimitDecision(
                True,
                retry_after_seconds(current.reset_at, checked_at),
            )

    def _prune_expired(self, checked_at: float) -> None:
        for key, window in tuple(self._windows.items()):
            if window.reset_at <= checked_at:
                del self._windows[key]

    def clear(self) -> None:
        with self._lock:
            self._windows.clear()

    async def close(self) -> None:
        self.clear()


class RedisRateLimitBackend:
    """Redis-backed fixed window shared by all API replicas.

    Redis stores only bounded hashes, counts, and expiry timestamps. It never
    stores the actor, credential, client address, or canonical domain state.
    """

    name = "redis"
    _CHECK_SCRIPT = """
local clock = redis.call("TIME")
local now_ms = (tonumber(clock[1]) * 1000)
  + math.floor(tonumber(clock[2]) / 1000)
local window_ms = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local max_clients = tonumber(ARGV[3])
local member = ARGV[4]

redis.call("ZREMRANGEBYSCORE", KEYS[2], "-inf", now_ms)
local exists = redis.call("EXISTS", KEYS[1])
local member_score = redis.call("ZSCORE", KEYS[2], member)
if exists == 0 then
  local active_clients = redis.call("ZCARD", KEYS[2])
  if not member_score and active_clients >= max_clients then
    local earliest = redis.call("ZRANGE", KEYS[2], 0, 0, "WITHSCORES")
    local retry_ms = window_ms
    if earliest[2] then
      retry_ms = math.max(1, tonumber(earliest[2]) - now_ms)
    end
    redis.call("PEXPIRE", KEYS[2], window_ms)
    return {-1, retry_ms}
  end
  redis.call("ZADD", KEYS[2], now_ms + window_ms, member)
elseif not member_score then
  local existing_ttl = redis.call("PTTL", KEYS[1])
  if existing_ttl < 1 then
    existing_ttl = window_ms
  end
  redis.call("ZADD", KEYS[2], now_ms + existing_ttl, member)
end
redis.call("PEXPIRE", KEYS[2], window_ms)

local count = redis.call("INCR", KEYS[1])
if count == 1 then
  redis.call("PEXPIRE", KEYS[1], window_ms)
end
local ttl_ms = redis.call("PTTL", KEYS[1])
if ttl_ms < 1 then
  redis.call("PEXPIRE", KEYS[1], window_ms)
  ttl_ms = window_ms
end
return {count, ttl_ms, limit}
"""

    def __init__(
        self,
        *,
        redis_url: str,
        redis_db: int,
        namespace: str,
        max_clients: int,
        timeout_seconds: float,
        max_connections: int = 20,
    ) -> None:
        self.max_clients = max_clients
        self._prefix = f"{{{namespace}}}"
        self._registry_key = f"{self._prefix}:clients"
        self._client: Redis = Redis.from_url(
            redis_url,
            db=redis_db,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
            health_check_interval=30,
            max_connections=max_connections,
            decode_responses=False,
        )

    async def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        now: float | None = None,
    ) -> RateLimitDecision:
        del now  # Redis server time is canonical across replicas.
        opaque_key = hashlib.sha256(key.encode()).hexdigest()
        counter_key = f"{self._prefix}:window:{opaque_key}"
        try:
            raw = await cast(
                Awaitable[Any],
                self._client.eval(
                    self._CHECK_SCRIPT,
                    2,
                    counter_key,
                    self._registry_key,
                    str(window_seconds * 1000),
                    str(limit),
                    str(self.max_clients),
                    opaque_key,
                ),
            )
        except (RedisError, OSError, TimeoutError) as exc:
            raise RateLimitBackendUnavailable(
                "Redis rate-limit backend is unavailable"
            ) from exc
        values = cast(list[int | bytes], raw)
        if len(values) < 2:
            raise RateLimitBackendUnavailable(
                "Redis rate-limit backend returned an invalid decision"
            )
        count = int(values[0])
        retry_after = max(1, math.ceil(int(values[1]) / 1000))
        if count == -1:
            return RateLimitDecision(
                allowed=False,
                retry_after=retry_after,
                capacity_rejected=True,
            )
        return RateLimitDecision(
            allowed=count <= limit,
            retry_after=retry_after,
        )

    async def close(self) -> None:
        await self._client.aclose()


def create_rate_limit_backend(
    backend: Literal["memory", "redis"],
    *,
    max_clients: int,
    redis_url: str,
    redis_db: int,
    namespace: str,
    timeout_seconds: float,
    max_connections: int = 20,
) -> RateLimitBackend:
    if backend == "redis":
        return RedisRateLimitBackend(
            redis_url=redis_url,
            redis_db=redis_db,
            namespace=namespace,
            max_clients=max_clients,
            timeout_seconds=timeout_seconds,
            max_connections=max_connections,
        )
    return InMemoryRateLimitBackend(max_clients)


_BULK_PATH_TOKENS = (
    "attribute-bulk",
    "/bulk",
    "/recalculate",
    "/validate",
    "/import",
    "/reorder",
    "/expire",
)


def _is_search_request(path: str, query_string: bytes) -> bool:
    try:
        query_names = {
            name.casefold()
            for name, _ in parse_qsl(
                query_string.decode("utf-8", errors="replace"),
                keep_blank_values=True,
                max_num_fields=100,
            )
        }
    except ValueError:
        return True
    return path.endswith("/search") or "search" in query_names


def high_risk_policy(
    path: str,
    method: str,
    query_string: bytes = b"",
) -> str | None:
    method = method.upper()
    mutation = method not in {"GET", "HEAD", "OPTIONS"}
    lowered = path.lower()
    if mutation and lowered.endswith(("/attribute-seed", "/content/seed")):
        return "seed"
    if mutation and lowered.endswith("/preview"):
        return "preview"
    if mutation and any(token in lowered for token in _BULK_PATH_TOKENS):
        return "bulk"
    if method == "GET" and lowered.endswith("/attributes/dependencies/validate"):
        return "validation"
    if mutation and "/jobs" in lowered:
        if lowered.endswith("/cancel"):
            return "execution-control"
        return "execution"
    if method == "GET" and (
        lowered.endswith("/export") or "/resolved-export" in lowered
    ):
        return "export"
    if method == "GET" and _is_search_request(lowered, query_string):
        return "search"
    return None


class RateLimitMiddleware:
    def __init__(
        self,
        app: Any,
        *,
        enabled: bool,
        requests: int,
        window_seconds: int,
        max_clients: int,
        backend: RateLimitBackend | None = None,
        fail_open_reads: bool = True,
        fail_open_mutations: bool = False,
        trusted_proxy_cidrs: tuple[str, ...] = (),
        identity_secret: str = "development-only-change-me",
    ) -> None:
        self.app = app
        self.enabled = enabled
        self.requests = requests
        self.window_seconds = window_seconds
        self.backend = backend or InMemoryRateLimitBackend(max_clients)
        self.fail_open_reads = fail_open_reads
        self.fail_open_mutations = fail_open_mutations
        self._identity_secret = identity_secret.encode()
        self._trusted_proxies = tuple(
            ipaddress.ip_network(cidr, strict=False) for cidr in trusted_proxy_cidrs
        )

    def _client_host(self, scope: dict[str, Any]) -> str:
        client = scope.get("client")
        direct_host = str(client[0]) if client else "unknown"
        try:
            direct_address = ipaddress.ip_address(direct_host)
        except ValueError:
            return direct_host[:255]
        if not any(direct_address in network for network in self._trusted_proxies):
            return direct_host[:255]
        forwarded_values = [
            value
            for name, value in scope.get("headers", ())
            if name.lower() == b"x-forwarded-for"
        ]
        if len(forwarded_values) != 1:
            return direct_host[:255]
        forwarded = forwarded_values[0].decode(errors="replace")
        raw_hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if not raw_hops:
            return direct_host[:255]
        try:
            hops = [ipaddress.ip_address(hop) for hop in raw_hops]
        except ValueError:
            return direct_host[:255]
        for address in reversed([*hops, direct_address]):
            if not any(address in network for network in self._trusted_proxies):
                return str(address)
        return str(hops[0])

    def _client_key(self, scope: dict[str, Any], policy: str) -> str:
        state = scope.get("state")
        principal = state.get("principal") if isinstance(state, dict) else None
        if not isinstance(principal, Principal):
            authorization_values = [
                value
                for name, value in scope.get("headers", ())
                if name.lower() == b"authorization"
            ]
            authorization = (
                authorization_values[0] if len(authorization_values) == 1 else b""
            )
            if authorization.lower().startswith(b"bearer "):
                try:
                    token = authorization[7:].decode("ascii")
                    principal = authenticate_token(token)
                except (HTTPException, UnicodeDecodeError):
                    principal = None
        identity = (
            f"actor:{principal.subject[:255]}"
            if isinstance(principal, Principal)
            else f"peer:{self._client_host(scope)}"
        )
        return hmac.new(
            self._identity_secret,
            f"{policy}:{identity}".encode(),
            hashlib.sha256,
        ).hexdigest()

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return
        method = str(scope.get("method", "")).upper()
        policy = high_risk_policy(
            str(scope.get("path", "")),
            method,
            cast(bytes, scope.get("query_string", b"")),
        )
        if policy is None:
            await self.app(scope, receive, send)
            return
        scope["rate_limit_policy"] = policy
        try:
            decision = await self.backend.check(
                self._client_key(scope, policy),
                limit=self.requests,
                window_seconds=self.window_seconds,
            )
        except RateLimitBackendUnavailable:
            fail_open = (
                self.fail_open_reads
                if method in {"GET", "HEAD", "OPTIONS"}
                else self.fail_open_mutations
            )
            metrics.observe_rate_limit_backend_failure(
                backend=self.backend.name,
                policy=policy,
                decision="fail_open" if fail_open else "fail_closed",
            )
            if fail_open:
                await self.app(scope, receive, send)
                return
            await self._send_error(
                send,
                status_code=503,
                code="RATE_LIMIT_BACKEND_UNAVAILABLE",
                message="Request protection is temporarily unavailable",
                retry_after=1,
            )
            return
        if decision.allowed:
            await self.app(scope, receive, send)
            return
        if decision.capacity_rejected:
            metrics.observe_rate_limit_backend_failure(
                backend=self.backend.name,
                policy=policy,
                decision="identity_capacity",
            )
        metrics.observe_rate_limit_rejection(policy)
        await self._send_error(
            send,
            status_code=429,
            code="RATE_LIMITED",
            message="Request rate limit exceeded",
            retry_after=decision.retry_after,
        )

    @staticmethod
    async def _send_error(
        send: Any,
        *,
        status_code: int,
        code: str,
        message: str,
        retry_after: int,
    ) -> None:
        body = json.dumps(
            {
                "detail": {"code": code, "message": message},
                "code": code,
                "request_id": current_request_id() or "unavailable",
            },
            separators=(",", ":"),
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    (b"cache-control", b"no-store"),
                    (b"content-length", str(len(body)).encode()),
                    (b"content-type", b"application/json"),
                    (b"retry-after", str(retry_after).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
