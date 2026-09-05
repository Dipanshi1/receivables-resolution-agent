from uuid import UUID

from sqlalchemy import select

from app.domain.recovery import RecoveryCase
from app.repositories.base import BaseRepository


class RecoveryCaseRepository(BaseRepository[RecoveryCase]):
    def __init__(self, session):
        super().__init__(RecoveryCase, session)

    async def get_by_invoice_id(self, invoice_id: UUID | str) -> list[RecoveryCase]:
        stmt = select(RecoveryCase).where(RecoveryCase.invoice_id == invoice_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_merchant(
        self, merchant_id: UUID | str, status: str | None = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[RecoveryCase], int]:
        stmt = select(RecoveryCase).where(RecoveryCase.merchant_id == merchant_id)
        if status:
            stmt = stmt.where(RecoveryCase.status == status)

        # simplified total count for MVP
        total_result = await self.session.execute(
            select(RecoveryCase).where(RecoveryCase.merchant_id == merchant_id)
        )
        total = len(total_result.scalars().all())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
