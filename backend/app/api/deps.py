from uuid import UUID

from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_db


async def get_db_session() -> AsyncSession:
    async for session in get_db():
        yield session


async def get_merchant_id(x_merchant_id: str = Header(...)) -> UUID:
    return UUID(x_merchant_id)
