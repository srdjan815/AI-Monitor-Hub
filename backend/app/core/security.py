from __future__ import annotations

import binascii
import contextvars
import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any, Final, NoReturn, Protocol

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.base64url import decode_base64url, encode_base64url
from app.core.config import Settings, settings


CATALOG_READ = "catalog.read"
CATALOG_WRITE = "catalog.write"
CATALOG_SEED = "catalog.seed"
ATTRIBUTES_READ = "attributes.read"
ATTRIBUTES_WRITE = "attributes.write"
ATTRIBUTES_APPROVE = "attributes.approve"
CONTENT_READ = "content.read"
CONTENT_WRITE = "content.write"
CONTENT_APPROVE = "content.approve"
CONTENT_RAW_PREVIEW = "content.raw_preview"
CONTENT_PROMPT_MANAGE = "content.prompt_manage"
CONTENT_SCORING_MANAGE = "content.scoring_manage"
INVENTORY_READ = "inventory.read"
INVENTORY_WRITE = "inventory.write"
INVENTORY_ADJUST = "inventory.adjust"
EXECUTION_READ = "execution.read"
EXECUTION_SUBMIT = "execution.submit"
EXECUTION_MANAGE = "execution.manage"
SUPPLIERS_READ = "suppliers.read"
SUPPLIERS_WRITE = "suppliers.write"
SUPPLIER_SOURCES_READ = "supplier_sources.read"
SUPPLIER_SOURCES_WRITE = "supplier_sources.write"
SUPPLIER_SOURCES_VALIDATE = "supplier_sources.validate"
SCHEMA_PROFILES_READ = "schema_profiles.read"
SCHEMA_PROFILES_WRITE = "schema_profiles.write"
SCHEMA_PROFILES_ACTIVATE = "schema_profiles.activate"
MAPPING_PROFILES_READ = "mapping_profiles.read"
MAPPING_PROFILES_WRITE = "mapping_profiles.write"
MAPPING_PROFILES_ACTIVATE = "mapping_profiles.activate"
ACQUISITIONS_READ = "acquisitions.read"
ACQUISITIONS_EXECUTE = "acquisitions.execute"
ACQUISITIONS_UPLOAD = "acquisitions.upload"
ACQUISITIONS_CANCEL = "acquisitions.cancel"
SNAPSHOTS_READ = "snapshots.read"
SNAPSHOTS_CREATE = "snapshots.create"
SNAPSHOTS_VERIFY = "snapshots.verify"
SNAPSHOTS_ARCHIVE = "snapshots.archive"
SNAPSHOTS_OFFLOAD = "snapshots.offload"
SNAPSHOTS_RESTORE = "snapshots.restore"
DELTAS_READ = "deltas.read"
DELTAS_CALCULATE = "deltas.calculate"
DELTAS_CANCEL = "deltas.cancel"
INCIDENTS_READ = "incidents.read"
INCIDENTS_CREATE = "incidents.create"
INCIDENTS_ACKNOWLEDGE = "incidents.acknowledge"
INCIDENTS_ASSIGN = "incidents.assign"
INCIDENTS_MANAGE = "incidents.manage"
INCIDENTS_RESOLVE = "incidents.resolve"
INCIDENTS_DISMISS = "incidents.dismiss"
INCIDENTS_SUPPRESS = "incidents.suppress"
INCIDENTS_COMMENT = "incidents.comment"
INCIDENT_RULES_READ = "incident_rules.read"
INCIDENT_RULES_MANAGE = "incident_rules.manage"
SUPPLIER_PLATFORM_OVERVIEW = "supplier_platform.overview"
SUPPLIER_PLATFORM_SEARCH = "supplier_platform.search"
ARTICLE_REVIEWS_READ = "article_reviews.read"
ARTICLE_REVIEWS_DECIDE = "article_reviews.decide"
ADMIN_ACCESS = "admin.access"

ALL_PERMISSIONS: Final[frozenset[str]] = frozenset(
    {
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
        ADMIN_ACCESS,
    }
)

ROLE_PERMISSIONS: Final[dict[str, frozenset[str]]] = {
    "system_admin": ALL_PERMISSIONS,
    "catalog_admin": frozenset(
        {
            CATALOG_READ,
            CATALOG_WRITE,
            CATALOG_SEED,
            ATTRIBUTES_READ,
            ATTRIBUTES_WRITE,
            ATTRIBUTES_APPROVE,
        }
    ),
    "content_editor": frozenset(
        {
            CATALOG_READ,
            ATTRIBUTES_READ,
            CONTENT_READ,
            CONTENT_WRITE,
        }
    ),
    "content_approver": frozenset(
        {CATALOG_READ, ATTRIBUTES_READ, CONTENT_READ, CONTENT_WRITE, CONTENT_APPROVE}
    ),
    "inventory_operator": frozenset(
        {CATALOG_READ, INVENTORY_READ, INVENTORY_WRITE, INVENTORY_ADJUST}
    ),
    "execution_operator": frozenset(
        {EXECUTION_READ, EXECUTION_SUBMIT, EXECUTION_MANAGE}
    ),
    "supplier_admin": frozenset(
        {
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
        }
    ),
    "supplier_source_validator": frozenset(
        {SUPPLIER_SOURCES_READ, SUPPLIER_SOURCES_VALIDATE}
    ),
    "schema_profile_editor": frozenset(
        {SUPPLIER_SOURCES_READ, SCHEMA_PROFILES_READ, SCHEMA_PROFILES_WRITE}
    ),
    "schema_profile_activator": frozenset(
        {SUPPLIER_SOURCES_READ, SCHEMA_PROFILES_READ, SCHEMA_PROFILES_ACTIVATE}
    ),
    "mapping_profile_editor": frozenset(
        {
            SUPPLIER_SOURCES_READ,
            SCHEMA_PROFILES_READ,
            MAPPING_PROFILES_READ,
            MAPPING_PROFILES_WRITE,
        }
    ),
    "mapping_profile_activator": frozenset(
        {
            SUPPLIER_SOURCES_READ,
            SCHEMA_PROFILES_READ,
            MAPPING_PROFILES_READ,
            MAPPING_PROFILES_ACTIVATE,
        }
    ),
    "acquisition_operator": frozenset(
        {
            SUPPLIERS_READ,
            SUPPLIER_SOURCES_READ,
            SCHEMA_PROFILES_READ,
            MAPPING_PROFILES_READ,
            ACQUISITIONS_READ,
            ACQUISITIONS_EXECUTE,
            ACQUISITIONS_UPLOAD,
            ACQUISITIONS_CANCEL,
        }
    ),
    "snapshot_operator": frozenset(
        {
            SUPPLIERS_READ,
            SUPPLIER_SOURCES_READ,
            ACQUISITIONS_READ,
            SNAPSHOTS_READ,
            SNAPSHOTS_CREATE,
            SNAPSHOTS_VERIFY,
            SNAPSHOTS_ARCHIVE,
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
            SUPPLIER_PLATFORM_OVERVIEW,
            SUPPLIER_PLATFORM_SEARCH,
            ARTICLE_REVIEWS_READ,
            ARTICLE_REVIEWS_DECIDE,
        }
    ),
    "read_only": frozenset(
        {
            CATALOG_READ,
            ATTRIBUTES_READ,
            CONTENT_READ,
            INVENTORY_READ,
            EXECUTION_READ,
            SUPPLIERS_READ,
            SUPPLIER_SOURCES_READ,
            SCHEMA_PROFILES_READ,
            MAPPING_PROFILES_READ,
            ACQUISITIONS_READ,
            SNAPSHOTS_READ,
            DELTAS_READ,
            INCIDENTS_READ,
            INCIDENT_RULES_READ,
            SUPPLIER_PLATFORM_OVERVIEW,
            SUPPLIER_PLATFORM_SEARCH,
            ARTICLE_REVIEWS_READ,
        }
    ),
    "internal_service": ALL_PERMISSIONS,
}


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


def _b64encode(value: bytes) -> str:
    return encode_base64url(value)


def _b64decode(value: str) -> bytes:
    return decode_base64url(value)


class AuthenticationAdapter(Protocol):
    """Replaceable token boundary for a future OIDC-backed implementation."""

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
    ) -> str: ...

    def authenticate(self, token: str) -> Principal: ...


class LocalHMACAuthenticationAdapter:
    """Strict local token adapter with additive legacy-token verification."""

    algorithm: Final[str] = "HS256"
    token_type: Final[str] = "JWT"
    maximum_token_length: Final[int] = 16_384

    def __init__(self, config: Settings) -> None:
        self.config = config

    @property
    def verification_keys(self) -> dict[str, str]:
        return {
            **self.config.auth_previous_keys,
            self.config.auth_key_id: self.config.auth_secret,
        }

    @staticmethod
    def _json_segment(value: str) -> dict[str, Any]:
        decoded = json.loads(_b64decode(value))
        if not isinstance(decoded, dict):
            raise ValueError("token segment is not an object")
        return decoded

    @staticmethod
    def _invalid() -> NoReturn:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Invalid or expired bearer token",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

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
        now = int(time.time())
        lifetime = (
            self.config.auth_token_ttl_seconds if expires_in is None else expires_in
        )
        header = {
            "alg": self.algorithm,
            "kid": self.config.auth_key_id,
            "typ": self.token_type,
        }
        payload: dict[str, Any] = {
            "aud": self.config.auth_audience,
            "exp": now + lifetime,
            "iat": now,
            "iss": self.config.auth_issuer,
            "roles": list(roles),
            "sub": subject,
            "type": actor_type,
            "ver": self.config.auth_token_version,
        }
        if not_before_in is not None:
            payload["nbf"] = now + not_before_in
        if include_token_id:
            payload["jti"] = (
                token_id
                or hashlib.sha256(
                    f"{subject}:{now}:{time.time_ns()}".encode()
                ).hexdigest()[:32]
            )
        encoded_header = _b64encode(
            json.dumps(header, separators=(",", ":"), sort_keys=True).encode()
        )
        encoded_payload = _b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )
        signing_input = f"{encoded_header}.{encoded_payload}"
        signature = hmac.new(
            self.config.auth_secret.encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
        return f"{signing_input}.{_b64encode(signature)}"

    def _verify_current(self, parts: list[str]) -> tuple[dict[str, Any], str]:
        encoded_header, encoded_payload, supplied_signature = parts
        header = self._json_segment(encoded_header)
        if header.get("alg") != self.algorithm or header.get("typ") != self.token_type:
            raise ValueError("unsupported token header")
        key_id = header.get("kid")
        if not isinstance(key_id, str) or key_id not in self.verification_keys:
            raise ValueError("unknown signing key")
        signing_input = f"{encoded_header}.{encoded_payload}"
        expected = hmac.new(
            self.verification_keys[key_id].encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(supplied_signature)):
            raise ValueError("invalid signature")
        return self._json_segment(encoded_payload), key_id

    def _verify_legacy(self, parts: list[str]) -> tuple[dict[str, Any], str]:
        if not self.config.auth_allow_legacy_tokens:
            raise ValueError("legacy tokens are disabled")
        encoded_payload, supplied_signature = parts
        decoded_signature = _b64decode(supplied_signature)
        verified_key_id: str | None = None
        for key_id, secret in self.verification_keys.items():
            expected = hmac.new(
                secret.encode(), encoded_payload.encode(), hashlib.sha256
            ).digest()
            if hmac.compare_digest(expected, decoded_signature):
                verified_key_id = key_id
        if verified_key_id is None:
            raise ValueError("invalid signature")
        return self._json_segment(encoded_payload), verified_key_id

    @staticmethod
    def _integer_claim(payload: dict[str, Any], name: str) -> int:
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"invalid {name}")
        return value

    def _validate_time_and_protocol(
        self,
        payload: dict[str, Any],
        *,
        legacy: bool,
    ) -> int:
        now = int(time.time())
        skew = self.config.auth_clock_skew_seconds
        issued_at = self._integer_claim(payload, "iat")
        expires_at = self._integer_claim(payload, "exp")
        not_before = payload.get("nbf", issued_at)
        if isinstance(not_before, bool) or not isinstance(not_before, int):
            raise ValueError("invalid nbf")
        if issued_at > now + skew or not_before > now + skew:
            raise ValueError("token is not active")
        if now >= expires_at + skew or expires_at <= issued_at:
            raise ValueError("expired")
        if not legacy:
            if payload.get("iss") != self.config.auth_issuer:
                raise ValueError("invalid issuer")
            if payload.get("aud") != self.config.auth_audience:
                raise ValueError("invalid audience")
            version = self._integer_claim(payload, "ver")
            if version != self.config.auth_token_version:
                raise ValueError("unsupported token version")
        else:
            version = 0
        return version

    @staticmethod
    def _identity_claims(
        payload: dict[str, Any],
    ) -> tuple[str, tuple[str, ...], str, str | None]:
        subject_value = payload.get("sub")
        roles_value = payload.get("roles")
        actor_type_value = payload.get("type", "user")
        if (
            not isinstance(subject_value, str)
            or not subject_value.strip()
            or len(subject_value) > 255
            or not isinstance(roles_value, list)
            or not roles_value
            or len(roles_value) > 32
            or not all(isinstance(role, str) for role in roles_value)
            or len(set(roles_value)) != len(roles_value)
            or any(role not in ROLE_PERMISSIONS for role in roles_value)
            or not isinstance(actor_type_value, str)
            or not actor_type_value
            or len(actor_type_value) > 64
        ):
            raise ValueError("invalid principal")
        token_id_value = payload.get("jti")
        if token_id_value is not None and (
            not isinstance(token_id_value, str)
            or not token_id_value
            or len(token_id_value) > 128
        ):
            raise ValueError("invalid token identifier")
        return (
            subject_value.strip(),
            tuple(str(role) for role in roles_value),
            actor_type_value,
            token_id_value,
        )

    def _principal(
        self,
        payload: dict[str, Any],
        key_id: str,
        *,
        legacy: bool,
    ) -> Principal:
        version = self._validate_time_and_protocol(payload, legacy=legacy)
        subject, roles, actor_type, token_id = self._identity_claims(payload)
        permissions: set[str] = set()
        for role in roles:
            permissions.update(ROLE_PERMISSIONS[role])
        return Principal(
            subject=subject,
            roles=roles,
            permissions=frozenset(permissions),
            actor_type=actor_type,
            token_id=token_id,
            token_version=version,
            key_id=key_id,
        )

    def authenticate(self, token: str) -> Principal:
        try:
            if not token or len(token) > self.maximum_token_length:
                raise ValueError("invalid token length")
            parts = token.split(".")
            if len(parts) == 3 and all(parts):
                payload, key_id = self._verify_current(parts)
                return self._principal(payload, key_id, legacy=False)
            if len(parts) == 2 and all(parts):
                payload, key_id = self._verify_legacy(parts)
                return self._principal(payload, key_id, legacy=True)
            raise ValueError("invalid token shape")
        except (
            binascii.Error,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
            json.JSONDecodeError,
        ):
            self._invalid()


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
