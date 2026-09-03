# Observability

## Structured request logs

`RequestContextMiddleware` establishes a request ID.
`RequestObservabilityMiddleware` emits one JSON log after each HTTP request with:

- UTC timestamp and severity;
- request and correlation IDs;
- authenticated actor ID when available;
- route template and method;
- status and duration;
- stable status error code.

Route templates are used instead of concrete URLs to avoid identifiers in logs
and metric labels. Authorization headers, tokens, query strings, request bodies
and response bodies are never logged. `X-Correlation-ID` is bounded and echoed
to clients; absent values fall back to the request ID.

## Metrics

An authenticated system administrator can scrape
`GET /api/v1/metrics` in Prometheus text format. It exposes:

- `amh_http_requests_total`;
- `amh_http_request_duration_seconds` histogram;
- `amh_rate_limit_rejections_total`;
- `amh_rate_limit_backend_failures_total`.

Labels are intentionally limited to method, route template, status, policy,
backend, and fail decision. Requests rejected before route resolution use a
finite rate-limit policy label rather than their concrete URL.

The registry is process-local even when Redis shares rate-limit decisions. A
multi-API deployment must scrape every replica as a separate Prometheus target.
Keep the target-provided `instance` label so a missing or restarting replica is
visible; do not inject a process-global instance value into application
metrics. Values reset on process restart and never participate in correctness.

Example service-level aggregations:

```promql
sum by (policy) (
  rate(amh_rate_limit_rejections_total[5m])
)

sum by (backend, policy, decision) (
  rate(amh_rate_limit_backend_failures_total[5m])
)

sum by (route, status) (
  rate(amh_http_requests_total[5m])
)

histogram_quantile(
  0.95,
  sum by (le, route) (
    rate(amh_http_request_duration_seconds_bucket[5m])
  )
)
```

Use `sum without (instance)` only for service-wide panels. Preserve `instance`
for target-health panels and incident drill-down. Counters from two replicas
must be summed as counters or rates, never averaged and never assumed to be one
in-process global.

## Operational guidance

Alerts should cover sustained 5xx responses, authentication/authorization
spikes, 429 spikes, limiter `fail_closed`/`fail_open` decisions,
`identity_capacity` rejections, latency budget violations, and missing scrape
targets. During a Redis restart, correlate backend-failure rates across
instances and expect the recovered non-canonical budget to start fresh.

Application logs and metrics are collector-neutral; deployment infrastructure
should attach service and `instance` labels and retention. Database-pool,
worker, lease, cache and domain-conflict metrics require domain-specific hooks
and are not inferred from request logs.
