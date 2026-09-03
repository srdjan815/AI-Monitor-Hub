"""Fail-closed production environment preflight without printing secrets."""

from __future__ import annotations

from app.core.config import settings


def main() -> None:
    if settings.app_env != "production":
        raise SystemExit("PREFLIGHT FAILED: APP_ENV mora biti production")
    settings.validate_runtime_secrets()
    checks = {
        "allowed_hosts": bool(settings.backend_allowed_hosts),
        "cors_origins": bool(settings.backend_cors_origins),
        "docs_disabled": not settings.docs_enabled,
        "encrypted_supplier_secrets": settings.supplier_secret_mode == "encrypted_file",
        "legacy_tokens_disabled": not settings.auth_allow_legacy_tokens,
        "rate_limit_shared": settings.rate_limit_enabled
        and settings.rate_limit_backend == "redis"
        and settings.rate_limit_shared_required,
        "session_origins_https": all(
            origin.startswith("https://")
            for origin in settings.auth_session_trusted_origins
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise SystemExit(f"PREFLIGHT FAILED: {', '.join(failed)}")
    print("PREFLIGHT OK: production security profile is valid")


if __name__ == "__main__":
    main()
