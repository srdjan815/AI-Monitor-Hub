from __future__ import annotations

import hmac
from typing import Final

from app.core.config import Settings, settings
from app.core.security_authentication import (
    AuthenticationAdapter,
    LocalHMACAuthenticationAdapter,
)
from app.core.security_context import Principal
from app.core.security_permissions import ALL_PERMISSIONS


class StaticAdminAuthenticationAdapter:
    """Timing-safe local administrator authentication without token issuance."""

    maximum_token_length: Final[int] = 16_384

    def __init__(self, config: Settings) -> None:
        self.config = config

    def issue_token(
        self,
        subject: str,
        roles: tuple[str, ...] = ("system_admin",),
        *,
        expires_in: int | None = None,
        actor_type: str = "user",
        not_before_in: int | None = None,
        token_id: str | None = None,
        include_token_id: bool = True,
    ) -> str:
        del (
            subject,
            roles,
            expires_in,
            actor_type,
            not_before_in,
            token_id,
            include_token_id,
        )
        raise RuntimeError(
            "Statički administratorski token se ne generiše; "
            "podesite AI_MONITOR_ADMIN_TOKEN"
        )

    def authenticate(self, token: str) -> Principal:
        configured = (
            self.config.ai_monitor_admin_token.get_secret_value()
            if self.config.ai_monitor_admin_token is not None
            else ""
        )
        if (
            not token
            or len(token) > self.maximum_token_length
            or len(configured) < 32
            or not hmac.compare_digest(
                token.encode("utf-8"),
                configured.encode("utf-8"),
            )
        ):
            LocalHMACAuthenticationAdapter._invalid()
        return Principal(
            subject="local-administrator",
            roles=("system_admin",),
            permissions=ALL_PERMISSIONS,
            actor_type="user",
            key_id="static-local-admin",
        )


authentication_adapter: AuthenticationAdapter = (
    StaticAdminAuthenticationAdapter(settings)
    if settings.auth_mode == "static"
    else LocalHMACAuthenticationAdapter(settings)
)


def create_access_token(
    subject: str,
    roles: tuple[str, ...] = ("system_admin",),
    *,
    expires_in: int | None = None,
    actor_type: str = "user",
    not_before_in: int | None = None,
    token_id: str | None = None,
    include_token_id: bool = True,
) -> str:
    return authentication_adapter.issue_token(
        subject,
        roles,
        expires_in=expires_in,
        actor_type=actor_type,
        not_before_in=not_before_in,
        token_id=token_id,
        include_token_id=include_token_id,
    )


def authenticate_token(token: str) -> Principal:
    return authentication_adapter.authenticate(token)


__all__ = [
    "StaticAdminAuthenticationAdapter",
    "authenticate_token",
    "authentication_adapter",
    "create_access_token",
]
