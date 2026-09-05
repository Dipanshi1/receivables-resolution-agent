from fastapi import APIRouter

from .endpoints import approvals, health, invoices, recovery_cases, webhooks

api_v1_router = APIRouter(prefix="/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_v1_router.include_router(
    recovery_cases.router, prefix="/recovery-cases", tags=["recovery_cases"]
)
api_v1_router.include_router(
    approvals.router, prefix="/recovery-cases/{case_id}/approvals", tags=["approvals"]
)
api_v1_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
