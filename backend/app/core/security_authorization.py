from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.security_context import Principal, _principal, bearer
from app.core.security_permissions import (
    CATALOG_READ,
    CATALOG_WRITE,
    CATALOG_SEED,
    ATTRIBUTES_READ,
    ATTRIBUTES_WRITE,
    ATTRIBUTES_APPROVE,
    CONTENT_READ,
    CONTENT_WRITE,
    CONTENT_APPROVE,
    CONTENT_RAW_PREVIEW,
    CONTENT_PROMPT_MANAGE,
    CONTENT_SCORING_MANAGE,
    INVENTORY_READ,
    INVENTORY_WRITE,
    INVENTORY_ADJUST,
    EXECUTION_READ,
    EXECUTION_SUBMIT,
    EXECUTION_MANAGE,
    SUPPLIERS_READ,
    SUPPLIERS_WRITE,
    SUPPLIER_SOURCES_READ,
    SUPPLIER_SOURCES_WRITE,
    SUPPLIER_SOURCES_VALIDATE,
    SCHEMA_PROFILES_READ,
    SCHEMA_PROFILES_WRITE,
    SCHEMA_PROFILES_ACTIVATE,
    MAPPING_PROFILES_READ,
    MAPPING_PROFILES_WRITE,
    MAPPING_PROFILES_ACTIVATE,
    ACQUISITIONS_READ,
    ACQUISITIONS_EXECUTE,
    ACQUISITIONS_UPLOAD,
    ACQUISITIONS_CANCEL,
    SNAPSHOTS_READ,
    SNAPSHOTS_CREATE,
    SNAPSHOTS_VERIFY,
    SNAPSHOTS_ARCHIVE,
    SNAPSHOTS_OFFLOAD,
    SNAPSHOTS_RESTORE,
    DELTAS_READ,
    DELTAS_CALCULATE,
    DELTAS_CANCEL,
    INCIDENTS_READ,
    INCIDENTS_CREATE,
    INCIDENTS_ACKNOWLEDGE,
    INCIDENTS_ASSIGN,
    INCIDENTS_MANAGE,
    INCIDENTS_RESOLVE,
    INCIDENTS_DISMISS,
    INCIDENTS_SUPPRESS,
    INCIDENTS_COMMENT,
    INCIDENT_RULES_READ,
    INCIDENT_RULES_MANAGE,
    SUPPLIER_PLATFORM_OVERVIEW,
    SUPPLIER_PLATFORM_SEARCH,
    ARTICLE_REVIEWS_READ,
    ARTICLE_REVIEWS_DECIDE,
)
from app.core.security_runtime import authenticate_token


def _content_permission(path: str, method: str, trusted_raw: bool) -> str:
    write = method not in {"GET", "HEAD", "OPTIONS"}
    if path.endswith("/preview") and write:
        return CONTENT_RAW_PREVIEW if trusted_raw else CONTENT_WRITE
    if "/prompts" in path and write:
        return CONTENT_PROMPT_MANAGE
    if "/scoring-policies" in path and write:
        return CONTENT_SCORING_MANAGE
    if any(part in path for part in ("/approve", "/workflow")) and write:
        return CONTENT_APPROVE
    return CONTENT_WRITE if write else CONTENT_READ


def _attribute_permission(path: str, method: str) -> str:
    write = method not in {"GET", "HEAD", "OPTIONS"}
    if "/attribute-seed" in path:
        return CATALOG_SEED
    if any(part in path for part in ("/approve", "/reject", "/lock")) and write:
        return ATTRIBUTES_APPROVE
    return ATTRIBUTES_WRITE if write else ATTRIBUTES_READ


def required_permission(request: Request) -> str | None:
    path = request.url.path
    method = request.method.upper()
    write = method not in {"GET", "HEAD", "OPTIONS"}
    if path.endswith("/auth/me") and method in {"GET", "HEAD", "OPTIONS"}:
        # Svaki uspešno autentifikovan principal sme da pročita sopstveni
        # identitet i efektivne dozvole.
        return None
    if "/suppliers/platform/overview" in path:
        return SUPPLIER_PLATFORM_OVERVIEW
    if "/suppliers/platform/search" in path:
        return SUPPLIER_PLATFORM_SEARCH
    if "/suppliers/platform/article-reviews" in path:
        return ARTICLE_REVIEWS_DECIDE if write else ARTICLE_REVIEWS_READ
    if "/suppliers/platform/source-schedules" in path:
        return SUPPLIER_SOURCES_WRITE if write else SUPPLIER_SOURCES_READ
    if "/suppliers/platform/bulk/incidents/assign" in path:
        return INCIDENTS_ASSIGN
    if "/suppliers/platform/bulk/incidents/priority" in path:
        return INCIDENTS_MANAGE
    if "/suppliers/platform/incidents" in path:
        return INCIDENTS_READ
    if "/supplier-incident-rules" in path:
        return (
            INCIDENT_RULES_READ
            if method in {"GET", "HEAD", "OPTIONS"}
            else INCIDENT_RULES_MANAGE
        )
    if "/supplier-incidents" in path:
        if method in {"GET", "HEAD", "OPTIONS"}:
            return INCIDENTS_READ
        if path.endswith("/acknowledge"):
            return INCIDENTS_ACKNOWLEDGE
        if path.endswith(("/assign", "/unassign")):
            return INCIDENTS_ASSIGN
        if path.endswith("/resolve"):
            return INCIDENTS_RESOLVE
        if path.endswith("/dismiss"):
            return INCIDENTS_DISMISS
        if path.endswith(("/suppress", "/reopen")):
            return INCIDENTS_SUPPRESS
        if path.endswith("/comments"):
            return INCIDENTS_COMMENT
        if path.endswith(("/priority", "/due-date", "/start", "/links")):
            return INCIDENTS_MANAGE
        return INCIDENTS_CREATE
    if "/jobs" in path:
        if method == "POST" and path.endswith(("/cancel", "/retry")):
            return EXECUTION_MANAGE
        return EXECUTION_SUBMIT if method == "POST" else EXECUTION_READ
    if "/acquisitions" in path:
        if method == "POST" and path.endswith("/upload"):
            return ACQUISITIONS_UPLOAD
        if method == "POST" and path.endswith("/cancel"):
            return ACQUISITIONS_CANCEL
        if method == "POST":
            return ACQUISITIONS_EXECUTE
        return ACQUISITIONS_READ
    if "/snapshots" in path:
        if method == "POST" and path.endswith("/verify"):
            return SNAPSHOTS_VERIFY
        if method == "POST" and path.endswith(("/archive", "/archive-bulk")):
            return SNAPSHOTS_ARCHIVE
        if method == "POST" and path.endswith("/offload"):
            return SNAPSHOTS_OFFLOAD
        if method == "POST" and path.endswith("/restore"):
            return SNAPSHOTS_RESTORE
        if method == "POST":
            return SNAPSHOTS_CREATE
        return SNAPSHOTS_READ
    if "/deltas" in path:
        if method == "POST" and path.endswith("/cancel"):
            return DELTAS_CANCEL
        if method == "POST":
            return DELTAS_CALCULATE
        return DELTAS_READ
    if "/mapping-profiles" in path:
        if method == "POST" and path.endswith(("/activate", "/archive")):
            return MAPPING_PROFILES_ACTIVATE
        return MAPPING_PROFILES_WRITE if write else MAPPING_PROFILES_READ
    if "/schema-profiles" in path:
        if method == "POST" and path.endswith(("/activate", "/archive")):
            return SCHEMA_PROFILES_ACTIVATE
        return SCHEMA_PROFILES_WRITE if write else SCHEMA_PROFILES_READ
    if "/suppliers" in path and "/sources" in path:
        if method == "POST" and path.endswith("/validate"):
            return SUPPLIER_SOURCES_VALIDATE
        return SUPPLIER_SOURCES_WRITE if write else SUPPLIER_SOURCES_READ
    if "/suppliers" in path:
        return SUPPLIERS_WRITE if write else SUPPLIERS_READ
    if "/inventory" in path or "/warehouses" in path:
        if any(part in path for part in ("/movements", "/reservations")) and write:
            return INVENTORY_ADJUST
        return INVENTORY_WRITE if write else INVENTORY_READ
    if "/content" in path:
        return _content_permission(
            path,
            method,
            request.query_params.get("trusted_raw") == "true",
        )
    if "/attribute" in path or "/catalog/" in path:
        return _attribute_permission(path, method)
    return CATALOG_WRITE if write else CATALOG_READ


async def authorize_request(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AsyncIterator[Principal]:
    authorization_headers = [
        value
        for name, value in request.scope.get("headers", ())
        if name.lower() == b"authorization"
    ]
    cookie_token = request.cookies.get(settings.auth_session_cookie_name)
    header_valid = (
        len(authorization_headers) == 1
        and credentials is not None
        and credentials.scheme.lower() == "bearer"
    )
    if len(authorization_headers) > 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Bearer token required",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    if header_valid and cookie_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "AMBIGUOUS_AUTHENTICATION",
                "message": "Koristite jedan način autentikacije",
            },
        )
    supplied_token = (
        credentials.credentials if header_valid and credentials else cookie_token
    )
    if not supplied_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Bearer token required",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    if cookie_token and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin", "").rstrip("/")
        same_origin = str(request.base_url).rstrip("/")
        allowed_origins = set(settings.auth_session_trusted_origins)
        if not origin or (origin != same_origin and origin not in allowed_origins):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "CSRF_ORIGIN_REJECTED",
                    "message": "Poreklo zahteva nije dozvoljeno",
                },
            )
    principal = authenticate_token(supplied_token)
    permission = required_permission(request)
    if permission is not None and permission not in principal.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PERMISSION_DENIED",
                "message": f"Permission required: {permission}",
            },
        )
    token = _principal.set(principal)
    request.state.principal = principal
    try:
        yield principal
    finally:
        _principal.reset(token)


__all__ = ["authorize_request", "required_permission"]
