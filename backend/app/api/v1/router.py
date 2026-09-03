"""API v1 master router aggregating all resource sub-routers."""

from fastapi import APIRouter

from .endpoints.health import router as health_router

api_v1_router = APIRouter(prefix="/v1")

# Mount endpoints
api_v1_router.include_router(health_router)
