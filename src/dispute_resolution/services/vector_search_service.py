from sqlalchemy import select
from dispute_resolution.models import Dispute


async def find_candidate_disputes(
    *,
    db,
    supplier_id,
    email_embedding,
    k: int = 3,
):
    stmt = (
        select(Dispute.id, Dispute.summary)
        .where(
            Dispute.supplier_id == supplier_id,
            Dispute.summary_embedding.is_not(None),
        )
        .order_by(Dispute.summary_embedding.cosine_distance(email_embedding))
        .limit(k)
    )

    result = await db.execute(stmt)
    return [
        {"id": row.id, "summary": row.summary}
        for row in result.fetchall()
    ]
