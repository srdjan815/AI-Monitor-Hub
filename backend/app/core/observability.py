from __future__ import annotations

import json
import logging
import math
import threading
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.core.errors import STATUS_CODES, current_request_id
from app.core.security import Principal


def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _identifier(value: str | None, fallback: str) -> str:
    if value is None:
        return fallback
    cleaned = "".join(
        character for character in value.strip() if character.isprintable()
    )
    return cleaned[:128] or fallback


class MetricsRegistry:
    """Low-cardinality, process-local Prometheus metrics."""

    duration_buckets = (
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[tuple[str, str, int], int] = defaultdict(int)
        self._duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self._duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._duration_buckets: dict[tuple[str, str], list[int]] = {}
        self._rate_limit_rejections: dict[str, int] = defaultdict(int)
        self._rate_limit_backend_failures: dict[tuple[str, str, str], int] = (
            defaultdict(int)
        )

    def observe_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        request_key = (method, route, status_code)
        duration_key = (method, route)
        with self._lock:
            self._requests[request_key] += 1
            self._duration_count[duration_key] += 1
            self._duration_sum[duration_key] += duration_seconds
            buckets = self._duration_buckets.setdefault(
                duration_key, [0] * len(self.duration_buckets)
            )
            for index, boundary in enumerate(self.duration_buckets):
                if duration_seconds <= boundary:
                    buckets[index] += 1

    def observe_rate_limit_rejection(self, policy: str) -> None:
        with self._lock:
            self._rate_limit_rejections[policy] += 1

    def observe_rate_limit_backend_failure(
        self,
        *,
        backend: str,
        policy: str,
        decision: str,
    ) -> None:
        with self._lock:
            self._rate_limit_backend_failures[(backend, policy, decision)] += 1

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()
            self._duration_count.clear()
            self._duration_sum.clear()
            self._duration_buckets.clear()
            self._rate_limit_rejections.clear()
            self._rate_limit_backend_failures.clear()

    def render(self) -> str:
        with self._lock:
            requests = sorted(self._requests.items())
            counts = dict(self._duration_count)
            sums = dict(self._duration_sum)
            buckets = {
                key: list(value) for key, value in self._duration_buckets.items()
            }
            rejections = sorted(self._rate_limit_rejections.items())
            backend_failures = sorted(self._rate_limit_backend_failures.items())
        lines = [
            "# HELP amh_http_requests_total HTTP requests handled by this process.",
            "# TYPE amh_http_requests_total counter",
        ]
        for (method, route, status_code), value in requests:
            labels = (
                f'method="{_label(method)}",route="{_label(route)}",'
                f'status="{status_code}"'
            )
            lines.append(f"amh_http_requests_total{{{labels}}} {value}")
        lines.extend(
            [
                "# HELP amh_http_request_duration_seconds Request duration.",
                "# TYPE amh_http_request_duration_seconds histogram",
            ]
        )
        for (method, route), count in sorted(counts.items()):
            base_labels = f'method="{_label(method)}",route="{_label(route)}"'
            for boundary, value in zip(
                self.duration_buckets, buckets[(method, route)], strict=True
            ):
                lines.append(
                    "amh_http_request_duration_seconds_bucket"
                    f'{{{base_labels},le="{boundary:g}"}} {value}'
                )
            lines.append(
                "amh_http_request_duration_seconds_bucket"
                f'{{{base_labels},le="+Inf"}} {count}'
            )
            lines.append(
                f"amh_http_request_duration_seconds_count{{{base_labels}}} {count}"
            )
            lines.append(
                f"amh_http_request_duration_seconds_sum{{{base_labels}}} "
                f"{sums[(method, route)]:.9f}"
            )
        lines.extend(
            [
                "# HELP amh_rate_limit_rejections_total Requests rejected by policy.",
                "# TYPE amh_rate_limit_rejections_total counter",
            ]
        )
        for policy, value in rejections:
            lines.append(
                f'amh_rate_limit_rejections_total{{policy="{_label(policy)}"}} {value}'
            )
        lines.extend(
            [
                "# HELP amh_rate_limit_backend_failures_total "
                "Limiter backend failures and capacity rejections.",
                "# TYPE amh_rate_limit_backend_failures_total counter",
            ]
        )
        for (backend, policy, decision), value in backend_failures:
            labels = (
                f'backend="{_label(backend)}",policy="{_label(policy)}",'
                f'decision="{_label(decision)}"'
            )
            lines.append(f"amh_rate_limit_backend_failures_total{{{labels}}} {value}")
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()
request_logger = logging.getLogger("app.http")


class RequestObservabilityMiddleware:
    def __init__(
        self,
        app: Any,
        *,
        metrics_enabled: bool = True,
        structured_logging: bool = True,
    ) -> None:
        self.app = app
        self.metrics_enabled = metrics_enabled
        self.structured_logging = structured_logging

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started_at = time.perf_counter()
        status_code = 500
        response_started = False
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        correlation_id = _identifier(
            headers.get(b"x-correlation-id", b"").decode(errors="replace"),
            current_request_id() or "unavailable",
        )

        async def observed_send(message: dict[str, Any]) -> None:
            nonlocal response_started, status_code
            if message["type"] == "http.response.start":
                response_started = True
                status_code = int(message["status"])
                message.setdefault("headers", []).append(
                    (b"x-correlation-id", correlation_id.encode())
                )
            await send(message)

        try:
            await self.app(scope, receive, observed_send)
        finally:
            duration = max(0.0, time.perf_counter() - started_at)
            route_object = scope.get("route")
            limiter_policy = scope.get("rate_limit_policy")
            fallback_route = (
                f"rate-limit:{limiter_policy}"
                if isinstance(limiter_policy, str)
                else "unmatched"
            )
            route = _identifier(
                getattr(route_object, "path", None),
                fallback_route,
            )
            method = _identifier(scope.get("method"), "UNKNOWN").upper()
            if self.metrics_enabled:
                metrics.observe_request(
                    method=method,
                    route=route,
                    status_code=status_code,
                    duration_seconds=duration,
                )
            if self.structured_logging:
                state = scope.get("state", {})
                principal = state.get("principal") if isinstance(state, dict) else None
                actor_id = (
                    principal.subject if isinstance(principal, Principal) else None
                )
                event = {
                    "actor_id": actor_id,
                    "correlation_id": correlation_id,
                    "duration_ms": round(duration * 1000, 3),
                    "error_code": (
                        STATUS_CODES.get(status_code) if status_code >= 400 else None
                    ),
                    "event": "http.request.completed",
                    "method": method,
                    "request_id": current_request_id(),
                    "response_started": response_started,
                    "route": route,
                    "status": status_code,
                }
                request_logger.info(
                    "http.request.completed",
                    extra={"event_data": event},
                )


class JsonFormatter(logging.Formatter):
    """Single-line JSON formatter that never serializes request payloads."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        event_data = getattr(record, "event_data", None)
        if isinstance(event_data, dict):
            payload.update(event_data)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(
            payload,
            default=str,
            separators=(",", ":"),
            sort_keys=True,
        )


def retry_after_seconds(reset_at: float, now: float) -> int:
    return max(1, math.ceil(reset_at - now))
