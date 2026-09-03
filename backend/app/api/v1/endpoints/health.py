"""Health check endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = "ok"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns service health status for observability and readiness probes.",
)
async def get_health() -> HealthResponse:
    """Return health status."""
    return HealthResponse(status="ok")
