from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from dispute_resolution.models import Email, Dispute


async def find_dispute_by_thread(
    db: AsyncSession,
    supplier_id,
    thread_id: str,
) -> Dispute | None:
    result = await db.execute(
        select(Dispute)
        .join(Email)
        .where(
            Email.thread_id == thread_id,
            Email.supplier_id == supplier_id,
            Email.dispute_id.isnot(None),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()

async def get_thread_context(
    *,
    db: AsyncSession,
    supplier_id,
    thread_id: str,
):
    result = await db.execute(
        select(Email)
        .where(
            Email.thread_id == thread_id,
            Email.supplier_id == supplier_id,
        )
        .order_by(Email.received_at)
    )
    emails = result.scalars().all()

    dispute = next((e.dispute for e in emails if e.dispute_id), None)

    return {
        "emails": emails,
        "dispute": dispute,
        "last_intent": emails[-1].intent_status if emails else None,
    }

async def clarification_sent_for_thread(
    *,
    db: AsyncSession,
    thread_id: str,
) -> bool:
    """
    Returns True if a clarification email was already sent
    for this Gmail thread.
    """
    stmt = (
        select(Email.id)
        .where(
            Email.thread_id == thread_id,
            Email.clarification_sent.is_(True),
        )
        .limit(1)
    )

    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None