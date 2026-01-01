from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dispute_resolution.models import Supplier


async def get_supplier_by_domain(db: AsyncSession, domain: str):
    """
    Fetch supplier by email domain.
    Domain must already be normalized (lowercase).
    """
    result = await db.execute(select(Supplier).where(Supplier.domain == domain))
    return result.scalars().one_or_none()
