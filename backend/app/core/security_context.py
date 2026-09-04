from __future__ import annotations

import contextvars
from dataclasses import dataclass

from fastapi import HTTPException, status
from fastapi.security import HTTPBearer


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    roles: tuple[str, ...]
    permissions: frozenset[str]
    actor_type: str = "user"
    token_id: str | None = None
    token_version: int = 0
    key_id: str | None = None


_principal: contextvars.ContextVar[Principal | None] = contextvars.ContextVar(
    "authenticated_principal", default=None
)
bearer = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def current_principal() -> Principal | None:
    return _principal.get()


def current_actor_id() -> str | None:
    principal = current_principal()
    return principal.subject if principal else None


def require_current_permission(permission: str) -> Principal:
    principal = current_principal()
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Bearer token required",
            },
        )
    if permission not in principal.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PERMISSION_DENIED",
                "message": f"Permission required: {permission}",
            },
        )
    return principal


__all__ = [
    "Principal",
    "_principal",
    "bearer",
    "current_actor_id",
    "current_principal",
    "require_current_permission",
]
