from sqlalchemy.ext.asyncio import AsyncSession

from dispute_resolution.services.decision_service import decide_dispute
from dispute_resolution.services.summary_service import generate_dispute_summary
from dispute_resolution.services.embedding_service import embed_email
from dispute_resolution.models import Dispute, Email


async def resolve_email(
    *,
    db: AsyncSession,
    email: Email,
    candidate_disputes: list[dict],
):
    # ✅ USE INSTANCE ATTRIBUTES
    decision = decide_dispute(
        subject=email.subject,
        body=email.body,
        candidate_disputes=candidate_disputes,
    )

    # ---- CASE 1: MATCH ----
    if decision["action"] == "MATCH":
        email.dispute_id = decision["dispute_id"]
        await db.commit()
        return decision

    # ---- CASE 2: NEW DISPUTE ----
    summary = generate_dispute_summary(
        subject=email.subject,
        body=email.body,
    )

    summary_embedding = embed_email(
        subject="Dispute summary",
        body=summary,
    )

    dispute = Dispute(
        supplier_id=email.supplier_id,
        summary=summary,
        summary_embedding=summary_embedding,
    )

    db.add(dispute)
    await db.flush()  # populate dispute.id

    email.dispute_id = dispute.id
    await db.commit()

    return {
        "action": "NEW",
        "dispute_id": str(dispute.id),
        "reason": "New dispute created",
    }
