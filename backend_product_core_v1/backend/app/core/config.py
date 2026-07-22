from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # API Configuration
    api_prefix: str = "/api/v1"
    backend_cors_origins: List[str] = ["*"]

    # Environment
    app_env: str = "development"

    # Service information
    app_name: str = "ai-cenovnici-api"
    app_version: str = "0.1.0"

    # Database configuration
    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_echo: bool = False

    # Redis configuration
    redis_url: str = "redis://redis:6379"
    redis_db: int = 0

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
    )


settings = Settings()