from uuid import UUID

from sqlalchemy import select

from app.domain.recovery import AuditEvent
from app.repositories.base import BaseRepository


class AuditEventRepository(BaseRepository[AuditEvent]):
    def __init__(self, session):
        super().__init__(AuditEvent, session)

    async def list_by_case(
        self, case_id: UUID | str, page: int = 1, page_size: int = 20
    ) -> tuple[list[AuditEvent], int]:
        stmt = select(AuditEvent).where(AuditEvent.case_id == case_id)

        total_result = await self.session.execute(
            select(AuditEvent).where(AuditEvent.case_id == case_id)
        )
        total = len(total_result.scalars().all())

        stmt = (
            stmt.order_by(AuditEvent.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
