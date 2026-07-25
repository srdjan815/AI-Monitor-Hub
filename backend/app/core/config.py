import ipaddress
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # API Configuration
    api_prefix: str = "/api/v1"
    backend_cors_origins: list[str] = ["*"]
    backend_allowed_hosts: list[str] = ["*"]
    cors_allow_credentials: bool = False
    max_request_body_bytes: int = 2_097_152
    acquisition_artifact_root: str = "/tmp/ai-monitor-hub-acquisitions"
    acquisition_max_artifact_bytes: int = Field(
        default=50 * 1024 * 1024,
        ge=65_536,
        le=1024 * 1024 * 1024,
    )
    acquisition_max_records: int = Field(default=100_000, ge=1, le=1_000_000)
    snapshot_archive_root: str = "/tmp/ai-monitor-hub-snapshot-archives"
    snapshot_archive_max_bytes: int = Field(
        default=2 * 1024 * 1024 * 1024,
        ge=1_048_576,
        le=10 * 1024 * 1024 * 1024,
    )
    snapshot_batch_size: int = Field(default=1000, ge=10, le=10_000)
    snapshot_archive_candidate_limit: int = Field(default=500, ge=1, le=5000)
    snapshot_image_url_max_length: int = Field(default=4096, ge=256, le=16_384)
    delta_batch_size: int = Field(default=1000, ge=10, le=10_000)
    delta_max_comparison_items: int = Field(default=250_000, ge=100, le=2_000_000)
    delta_max_changed_fields_per_item: int = Field(default=2000, ge=10, le=10_000)
    delta_ratio_signal_minimum_items: int = Field(default=10, ge=1, le=100_000)
    delta_high_removal_ratio: float = Field(default=0.5, ge=0, le=1)
    delta_high_addition_ratio: float = Field(default=0.5, ge=0, le=1)
    delta_unusual_modified_ratio: float = Field(default=0.8, ge=0, le=1)
    incident_max_synchronized_per_source: int = Field(default=100, ge=1, le=1000)
    incident_due_hours_p1: int = Field(default=4, ge=1, le=720)
    incident_due_hours_p2: int = Field(default=24, ge=1, le=720)
    incident_due_hours_p3: int = Field(default=72, ge=1, le=2160)
    incident_due_hours_p4: int = Field(default=168, ge=1, le=4320)

    # Environment
    app_env: Literal["development", "test", "production"] = "development"

    # Service information
    app_name: str = "ai-cenovnici-api"
    app_version: str = "0.1.0"
    product_content_trusted_raw_preview: bool = False
    auth_secret: str = "development-only-change-me"
    auth_key_id: str = Field(default="local-development", min_length=1, max_length=64)
    auth_previous_keys: dict[str, str] = Field(default_factory=dict)
    auth_issuer: str = Field(default="ai-monitor-hub", min_length=1, max_length=255)
    auth_audience: str = Field(
        default="ai-monitor-hub-api", min_length=1, max_length=255
    )
    auth_token_version: int = Field(default=1, ge=1)
    auth_token_ttl_seconds: int = 3600
    auth_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    auth_allow_legacy_tokens: bool = True
    docs_enabled: bool = True

    # Request protection and observability.
    rate_limit_enabled: bool = False
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    rate_limit_shared_required: bool = False
    rate_limit_requests: int = Field(default=30, ge=1, le=100_000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=86_400)
    rate_limit_max_clients: int = Field(default=10_000, ge=100, le=1_000_000)
    rate_limit_namespace: str = Field(
        default="amh:rate-limit:v1",
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9:_-]+$",
    )
    rate_limit_backend_timeout_seconds: float = Field(
        default=0.5,
        ge=0.05,
        le=10.0,
    )
    rate_limit_redis_max_connections: int = Field(default=20, ge=1, le=100)
    rate_limit_fail_open_reads: bool = True
    rate_limit_fail_open_mutations: bool = False
    rate_limit_trusted_proxy_cidrs: list[str] = Field(default_factory=list)
    metrics_enabled: bool = True
    structured_logging: bool = True

    # Database configuration
    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_echo: bool = False

    # Redis configuration
    redis_url: str = "redis://redis:6379"
    redis_db: int = Field(default=0, ge=0, le=15)

    def _validate_rate_limit_configuration(self) -> None:
        if self.rate_limit_shared_required:
            if not self.rate_limit_enabled:
                raise ValueError(
                    "RATE_LIMIT_SHARED_REQUIRED requires RATE_LIMIT_ENABLED=true"
                )
            if self.rate_limit_backend != "redis":
                raise ValueError(
                    "RATE_LIMIT_SHARED_REQUIRED requires RATE_LIMIT_BACKEND=redis"
                )
        if self.rate_limit_backend == "redis" and not self.redis_url.startswith(
            ("redis://", "rediss://")
        ):
            raise ValueError("Redis rate limiting requires a redis:// or rediss:// URL")
        for cidr in self.rate_limit_trusted_proxy_cidrs:
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid RATE_LIMIT_TRUSTED_PROXY_CIDRS entry: {cidr}"
                ) from exc

    def _validate_production_network(self) -> None:
        if not self.backend_cors_origins or "*" in self.backend_cors_origins:
            raise ValueError("Production requires explicit CORS origins")
        if not self.backend_allowed_hosts or "*" in self.backend_allowed_hosts:
            raise ValueError("Production requires explicit allowed hosts")

    def _validate_production_authentication(self) -> None:
        if len(self.auth_secret) < 32 or self.auth_secret == (
            "development-only-change-me"
        ):
            raise ValueError("Production requires a strong AUTH_SECRET")
        if any(len(secret) < 32 for secret in self.auth_previous_keys.values()):
            raise ValueError(
                "Production previous signing keys must be at least 32 characters"
            )

    def _validate_production_runtime(self) -> None:
        if not self.rate_limit_enabled:
            raise ValueError("Production requires RATE_LIMIT_ENABLED=true")
        if not self.rate_limit_shared_required or self.rate_limit_backend != "redis":
            raise ValueError("Production requires shared Redis rate limiting")
        if self.rate_limit_fail_open_mutations:
            raise ValueError("Production mutation rate limiting must fail closed")
        lowered_database_url = self.database_url.lower()
        if (
            ":password@" in lowered_database_url
            or "postgres:postgres@" in lowered_database_url
        ):
            raise ValueError("Production database credentials use a known default")
        if self.product_content_trusted_raw_preview:
            raise ValueError("Trusted raw preview cannot be enabled in production")
        if self.docs_enabled:
            raise ValueError(
                "Interactive API documentation must be disabled in production"
            )

    @model_validator(mode="after")
    def validate_security_profile(self) -> "Settings":
        self.backend_cors_origins = sorted(
            {origin.rstrip("/") for origin in self.backend_cors_origins}
        )
        if self.max_request_body_bytes < 65_536:
            raise ValueError("MAX_REQUEST_BODY_BYTES must be at least 65536")
        if self.auth_key_id in self.auth_previous_keys:
            raise ValueError("AUTH_KEY_ID must not also appear in AUTH_PREVIOUS_KEYS")
        self._validate_rate_limit_configuration()
        if self.app_env != "production":
            return self
        self._validate_production_network()
        self._validate_production_authentication()
        self._validate_production_runtime()
        return self

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings.model_validate({})
