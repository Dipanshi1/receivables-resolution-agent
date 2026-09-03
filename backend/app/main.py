"""FastAPI application entry point."""

from fastapi import FastAPI

from .api.v1.router import api_v1_router
from .core.config import get_settings


def create_app() -> FastAPI:
    """Application factory for FastAPI app."""
    settings = get_settings()

    application = FastAPI(
        title="Receivables Resolution Agent API",
        version="0.1.0",
        description="AI-assisted B2B receivables resolution platform",
        docs_url="/docs" if settings.app_env.value != "production" else None,
        redoc_url="/redoc" if settings.app_env.value != "production" else None,
    )

    # Mount v1 API router
    application.include_router(api_v1_router)

    return application


app = create_app()
