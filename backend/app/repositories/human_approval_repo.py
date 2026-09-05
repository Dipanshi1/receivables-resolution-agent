from uuid import UUID

from sqlalchemy import select

from app.domain.recovery import HumanApproval
from app.repositories.base import BaseRepository


class HumanApprovalRepository(BaseRepository[HumanApproval]):
    def __init__(self, session):
        super().__init__(HumanApproval, session)

    async def get_pending_for_action(self, action_id: UUID | str) -> HumanApproval | None:
        stmt = select(HumanApproval).where(
            HumanApproval.action_id == action_id, HumanApproval.decision == "PENDING"
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
