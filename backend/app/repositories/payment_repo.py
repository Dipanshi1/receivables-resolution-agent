from sqlalchemy import select

from app.domain.recovery import Payment
from app.repositories.base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self, session):
        super().__init__(Payment, session)

    async def get_by_razorpay_link_id(self, link_id: str) -> Payment | None:
        stmt = select(Payment).where(Payment.razorpay_payment_link_id == link_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()
