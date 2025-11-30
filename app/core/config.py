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
    # optional db name env var (some deployments use MONGODB_DB)
    MONGODB_DB: Optional[str] = "ats_resume"

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
    # Adapter selection: 'mock' or 'http'
    LLM_ADAPTER: str = "mock"
    # HTTP adapter settings
    LLM_HTTP_URL: Optional[AnyUrl] = None
    LLM_TIMEOUT_SEC: int = 20
    LLM_RETRIES: int = 2
    LLM_BACKOFF_FACTOR: float = 0.5
    # allow fallback to mock adapter when HTTP adapter fails
    LLM_ALLOW_FALLBACK: bool = True

    # other
    DETERMINISTIC_SEED: int = 42
    ALLOWED_HOSTS: str = "*"
    # Access token expiry (minutes) - environment values are often strings,
    # pydantic will coerce to int. Add this explicit field so env vars such as
    # ACCESS_TOKEN_EXPIRE_MINUTES or access_token_expire_minutes are accepted
    # instead of being treated as unexpected extras.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Pydantic v2 settings: read from .env file
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

# single shared settings instance
settings = Settings()
