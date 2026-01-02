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

async def get_thread_context(db, thread_id: str):
    emails = (
        await db.execute(
            select(Email)
            .where(Email.thread_id == thread_id)
            .order_by(Email.received_at)
        )
    ).scalars().all()

    dispute = next((e.dispute for e in emails if e.dispute_id), None)

    return {
        "emails": emails,
        "dispute": dispute,
        "last_intent": emails[-1].intent_status if emails else None,
    }
