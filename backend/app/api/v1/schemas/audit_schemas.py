from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    id: UUID
    case_id: UUID
    event_type: str
    actor_type: str
    actor_id: str | None
    state_before: str | None
    state_after: str | None
    payload_json: dict | None
    created_at: datetime


class PaginatedAuditResponse(BaseModel):
    data: list[AuditEventResponse]
    total: int
    page: int
    page_size: int
