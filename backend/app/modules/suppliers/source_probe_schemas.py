from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceCredentialWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    placement: str = Field(pattern="^(HEADER|QUERY)$")
    username: str | None = Field(default=None, min_length=1, max_length=500)
    password: str | None = Field(default=None, min_length=1, max_length=2000)
    token: str | None = Field(default=None, min_length=1, max_length=4000)
    api_key: str | None = Field(default=None, min_length=1, max_length=4000)
    username_parameter: str = Field(default="username", min_length=1, max_length=128)
    password_parameter: str = Field(default="password", min_length=1, max_length=128)
    token_parameter: str = Field(default="Authorization", min_length=1, max_length=128)
    api_key_parameter: str = Field(default="X-API-Key", min_length=1, max_length=128)

    @model_validator(mode="after")
    def at_least_one_secret(self) -> SourceCredentialWrite:
        if not any((self.password, self.token, self.api_key)):
            raise ValueError("Unesite lozinku, token ili API ključ")
        return self


class SourceCredentialState(BaseModel):
    configured: bool


class SourceProbeStep(BaseModel):
    label: str
    successful: bool


class SourceProbeResult(BaseModel):
    successful: bool
    tested_at: datetime
    duration_ms: int
    detected_format: str | None
    size_bytes: int
    approximate_record_count: int | None
    message: str
    steps: list[SourceProbeStep]
    preview: list[dict[str, object]]
    http_status: int | None = None
    content_type: str | None = None
    checksum: str | None = None


__all__ = [
    "SourceCredentialState",
    "SourceCredentialWrite",
    "SourceProbeResult",
    "SourceProbeStep",
]
