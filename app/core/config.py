# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, field_validator
from typing import Optional

class Settings(BaseSettings):
    APP_ENV: str = "development"
    SECRET_KEY: str = "dev-secret-key"
    DETERMINISTIC_SEED: int = 42
    ALLOWED_HOSTS: str = "*"

    # DB / Redis
    DATABASE_URL: str = "sqlite:///test.db"
    REDIS_URL: str = "redis://localhost:6379"

    # S3 / R2 / Minio
    S3_PROVIDER: str = "cloudflare"
    S3_BUCKET: str = ""
    S3_ENDPOINT: Optional[str] = None
    S3_REGION: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None

    # MinIO fallback (local dev)
    MINIO_ENDPOINT: Optional[str] = None
    MINIO_ACCESS_KEY: Optional[str] = None
    MINIO_SECRET_KEY: Optional[str] = None

    # LLM
    LLM_API_KEY: Optional[str] = None

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

settings = Settings()
