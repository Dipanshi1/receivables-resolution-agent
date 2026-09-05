from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.merchant import Merchant
from app.repositories.base import BaseRepository


class MerchantRepository(BaseRepository[Merchant]):
    def __init__(self, session):
        super().__init__(Merchant, session)

    async def get_with_policy(self, merchant_id: UUID | str) -> Merchant | None:
        stmt = (
            select(Merchant)
            .options(selectinload(Merchant.policies))
            .where(Merchant.id == merchant_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
