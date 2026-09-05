from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.invoice import Invoice
from app.repositories.base import BaseRepository


class InvoiceRepository(BaseRepository[Invoice]):
    def __init__(self, session):
        super().__init__(Invoice, session)

    async def get_by_merchant_and_number(
        self, merchant_id: UUID | str, invoice_number: str
    ) -> Invoice | None:
        stmt = (
            select(Invoice)
            .where(Invoice.merchant_id == merchant_id, Invoice.invoice_number == invoice_number)
            .options(selectinload(Invoice.customer), selectinload(Invoice.lines))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
