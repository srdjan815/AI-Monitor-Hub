from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm.exc import StaleDataError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import (
    DEFAULT_ERROR_RESPONSES,
    RequestContextMiddleware,
    http_error_handler,
    stale_data_error_handler,
    validation_error_handler,
)
from app.core.logging import setup_logging
from app.core.middleware import RequestSizeLimitMiddleware
from app.core.observability import RequestObservabilityMiddleware, metrics
from app.core.rate_limit import RateLimitMiddleware, create_rate_limit_backend
from app.core.security import (
    ADMIN_ACCESS,
    authorize_request,
    require_current_permission,
)

# Setup logging
setup_logging()

rate_limit_backend = create_rate_limit_backend(
    settings.rate_limit_backend,
    max_clients=settings.rate_limit_max_clients,
    redis_url=settings.redis_url,
    redis_db=settings.redis_db,
    namespace=settings.rate_limit_namespace,
    timeout_seconds=settings.rate_limit_backend_timeout_seconds,
    max_connections=settings.rate_limit_redis_max_connections,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    try:
        yield
    finally:
        await rate_limit_backend.close()


# Create FastAPI application
app = FastAPI(
    title="AI Cenovnici API",
    version="0.1.0",
    description="API for AI Cenovnici application",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    lifespan=lifespan,
    responses=DEFAULT_ERROR_RESPONSES,
)
app.add_exception_handler(HTTPException, http_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StaleDataError, stale_data_error_handler)

app.add_middleware(
    RequestSizeLimitMiddleware,
    max_body_bytes=settings.max_request_body_bytes,
)
app.add_middleware(
    RateLimitMiddleware,
    enabled=settings.rate_limit_enabled,
    requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
    max_clients=settings.rate_limit_max_clients,
    backend=rate_limit_backend,
    fail_open_reads=settings.rate_limit_fail_open_reads,
    fail_open_mutations=settings.rate_limit_fail_open_mutations,
    trusted_proxy_cidrs=tuple(settings.rate_limit_trusted_proxy_cidrs),
    identity_secret=settings.auth_secret,
)
app.add_middleware(
    RequestObservabilityMiddleware,
    metrics_enabled=settings.metrics_enabled,
    structured_logging=settings.structured_logging,
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.backend_allowed_hosts,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs_url": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get(
    f"{settings.api_prefix}/metrics",
    tags=["Observability"],
    response_class=PlainTextResponse,
    dependencies=[Depends(authorize_request)],
)
async def prometheus_metrics() -> PlainTextResponse:
    require_current_permission(ADMIN_ACCESS)
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Metrics are disabled")
    return PlainTextResponse(
        metrics.render(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
