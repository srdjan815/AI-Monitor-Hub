from pydantic_settings import SettingsConfigDict, BaseSettings
from typing import List

class Settings(BaseSettings):
    # API Configuration
    api_prefix: str = "/api/v1"
    backend_cors_origins: List[str] = ["*"]
    
    # Environment
    app_env: str = "development"
    
    # Service information
    app_name: str = "ai-cenovnici-api"
    app_version: str = "0.1.0"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Create settings instance
settings = Settings()
