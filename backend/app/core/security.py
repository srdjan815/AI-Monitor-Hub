"""Stable security façade for authentication, authorization and RBAC."""

import time as time  # Public compatibility hook for deterministic token tests.

from app.core.security_authentication import (
    AuthenticationAdapter,
    LocalHMACAuthenticationAdapter,
)
from app.core.security_authorization import authorize_request, required_permission
from app.core.security_context import (
    Principal,
    bearer,
    current_actor_id,
    current_principal,
    require_current_permission,
)
from app.core.security_permissions import *  # noqa: F403
from app.core.security_runtime import (
    StaticAdminAuthenticationAdapter,
    authenticate_token,
    authentication_adapter,
    create_access_token,
)

__all__ = [
    "AuthenticationAdapter",
    "LocalHMACAuthenticationAdapter",
    "Principal",
    "StaticAdminAuthenticationAdapter",
    "authenticate_token",
    "authentication_adapter",
    "authorize_request",
    "bearer",
    "create_access_token",
    "current_actor_id",
    "current_principal",
    "require_current_permission",
    "required_permission",
]
