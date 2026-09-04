"""Typed settings configuration using pydantic-settings."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    """Application deployment environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application Environment
    app_env: AppEnvironment = Field(
        default=AppEnvironment.DEVELOPMENT,
        alias="APP_ENV",
        description="Deployment environment (development, staging, production, test)",
    )
    api_host: str = Field(
        default="0.0.0.0",
        alias="API_HOST",
        description="Bind host for the API server",
    )
    api_port: int = Field(
        default=8000,
        alias="API_PORT",
        description="Bind port for the API server",
    )

    # Database Configuration
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/receivables_db",
        alias="DATABASE_URL",
        description="PostgreSQL connection URL",
    )

    # Razorpay Credentials (Test Mode)
    razorpay_key_id: str = Field(
        default="",
        alias="RAZORPAY_KEY_ID",
        description="Razorpay API Key ID",
    )
    razorpay_key_secret: str = Field(
        default="",
        alias="RAZORPAY_KEY_SECRET",
        description="Razorpay API Key Secret",
    )
    razorpay_webhook_secret: str = Field(
        default="",
        alias="RAZORPAY_WEBHOOK_SECRET",
        description="Razorpay Webhook verification secret",
    )

    # AI / LLM Configuration
    ai_provider: str = Field(
        default="gemini",
        alias="AI_PROVIDER",
        description="AI provider identifier",
    )
    llm_api_key: str = Field(
        default="",
        alias="LLM_API_KEY",
        description="API key for the AI provider",
    )
    llm_model: str = Field(
        default="gemini-1.5-pro",
        alias="LLM_MODEL",
        description="Model name for AI reasoning",
    )

    # CORS Configuration
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        alias="CORS_ORIGINS",
        description="Allowed CORS origins for web clients",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
