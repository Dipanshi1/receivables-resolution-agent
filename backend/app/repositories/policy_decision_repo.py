from uuid import UUID

from sqlalchemy import select

from app.domain.recovery import PolicyDecision
from app.repositories.base import BaseRepository


class PolicyDecisionRepository(BaseRepository[PolicyDecision]):
    def __init__(self, session):
        super().__init__(PolicyDecision, session)

    async def get_latest_by_case(self, case_id: UUID | str) -> PolicyDecision | None:
        stmt = (
            select(PolicyDecision)
            .where(PolicyDecision.case_id == case_id)
            .order_by(PolicyDecision.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
