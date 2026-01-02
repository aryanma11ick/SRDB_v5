from sqlalchemy.ext.asyncio import AsyncSession

from dispute_resolution.models import Email, Dispute
from dispute_resolution.services.intent_service import classify_intent
from dispute_resolution.services.clarification_service import generate_clarification_email
from dispute_resolution.services.embedding_service import embed_email
from dispute_resolution.services.vector_search_service import find_candidate_disputes
from dispute_resolution.services.decision_service import decide_dispute
from dispute_resolution.services.summary_service import generate_dispute_summary
from dispute_resolution.services.thread_service import get_thread_context
from dispute_resolution.services.reply_service import send_reply


async def resolve_email(
    *,
    db: AsyncSession,
    email: Email,
    gmail_service,
    sender: str,
) -> dict | None:
    """
    Returns:
    - MATCH / NEW / CLARIFICATION_SENT
    - None → NOT_DISPUTE
    """

    # -------------------------------------------------
    # 0. THREAD SHORT-CIRCUIT (FAST PATH)
    # -------------------------------------------------
    if email.thread_id:
        ctx = await get_thread_context(db=db, thread_id=email.thread_id)
        if ctx and ctx.get("dispute"):
            dispute = ctx["dispute"]

            email.dispute_id = dispute.id
            email.intent_status = "DISPUTE"
            email.intent_confidence = 1.0
            email.intent_reason = "Thread already linked to dispute"

            await db.commit()
            return {
                "action": "MATCH",
                "dispute_id": str(dispute.id),
                "reason": "Thread already linked to dispute",
            }

    # -------------------------------------------------
    # 1. INTENT CLASSIFICATION
    # -------------------------------------------------
    intent = classify_intent(
        subject=email.subject,
        body=email.body,
    )

    email.intent_status = intent["intent"]
    email.intent_confidence = intent["confidence"]
    email.intent_reason = intent["reason"]
    await db.flush()

    # -------------------------------------------------
    # 2. NOT A DISPUTE
    # -------------------------------------------------
    if intent["intent"] == "NOT_DISPUTE":
        await db.commit()
        return None

    # -------------------------------------------------
    # 3. AMBIGUOUS → SEND CLARIFICATION (ONCE)
    # -------------------------------------------------
    if intent["intent"] == "AMBIGUOUS":
        if email.clarification_sent:
            await db.commit()
            return {
                "action": "WAITING",
                "reason": "Clarification already sent",
            }

        clarification = generate_clarification_email(
            subject=email.subject,
            body=email.body,
        )

        if email.thread_id:
            send_reply(
                service=gmail_service,
                to=sender,
                subject=email.subject,
                body=clarification,
                thread_id=email.thread_id,
                in_reply_to=email.gmail_message_id,
            )

        email.clarification_sent = True
        await db.commit()

        return {
            "action": "CLARIFICATION_SENT",
            "reason": "Awaiting supplier response",
        }

    # -------------------------------------------------
    # 4. DISPUTE PATH
    # -------------------------------------------------
    email.embedding = embed_email(
        subject=email.subject,
        body=email.body,
    )
    await db.flush()

    candidates = await find_candidate_disputes(
        db=db,
        supplier_id=email.supplier_id,
        email_embedding=email.embedding,
        k=3,
    )

    decision = (
        {"action": "NEW", "dispute_id": None}
        if not candidates
        else decide_dispute(
            subject=email.subject,
            body=email.body,
            candidate_disputes=candidates,
        )
    )

    # -------------------------------------------------
    # 4a. MATCH
    # -------------------------------------------------
    if decision["action"] == "MATCH":
        email.dispute_id = decision["dispute_id"]
        await db.commit()
        return decision

    # -------------------------------------------------
    # 4b. NEW DISPUTE
    # -------------------------------------------------
    summary = generate_dispute_summary(
        subject=email.subject,
        body=email.body,
    )

    dispute = Dispute(
        supplier_id=email.supplier_id,
        summary=summary,
        summary_embedding=embed_email("Dispute summary", summary),
    )

    db.add(dispute)
    await db.flush()

    email.dispute_id = dispute.id
    await db.commit()

    return {
        "action": "NEW",
        "dispute_id": str(dispute.id),
        "reason": "New dispute created",
    }
