# app/core/config.py
from typing import Optional
from pydantic import AnyUrl
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me"  # override in .env / secrets

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # MongoDB
    MONGODB_URI: Optional[str] = "mongodb://localhost:27017/ats_resume"

    # S3 / R2
    S3_PROVIDER: str = "cloudflare"
    S3_BUCKET: Optional[str] = None
    S3_ENDPOINT: Optional[AnyUrl] = None
    S3_REGION: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None

    # MinIO dev fallback
    MINIO_ENDPOINT: Optional[str] = None
    MINIO_ACCESS_KEY: Optional[str] = None
    MINIO_SECRET_KEY: Optional[str] = None

    # LLM
    LLM_API_KEY: Optional[str] = None

    # other
    DETERMINISTIC_SEED: int = 42
    ALLOWED_HOSTS: str = "*"

    # Pydantic v2 settings: read from .env file
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

# single shared settings instance
settings = Settings()
