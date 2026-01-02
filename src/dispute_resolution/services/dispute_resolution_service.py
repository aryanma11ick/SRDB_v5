from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from dispute_resolution.models import Email, Dispute
from dispute_resolution.services.intent_service import classify_intent
from dispute_resolution.services.clarification_service import extract_facts_and_clarification
from dispute_resolution.services.embedding_service import embed_email
from dispute_resolution.services.vector_search_service import find_candidate_disputes
from dispute_resolution.services.decision_service import decide_dispute
from dispute_resolution.services.summary_service import generate_dispute_summary, resummarize_dispute
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
    - MATCH
    - NEW
    - CLARIFICATION_SENT
    - WAITING
    - None → NOT_DISPUTE
    """

    # =================================================
    # 0. THREAD SHORT-CIRCUIT (already a dispute)
    # =================================================
    if email.thread_id:
        ctx = await get_thread_context(
            db=db,
            supplier_id=email.supplier_id,
            thread_id=email.thread_id,
        )

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

    # =================================================
    # 1. INTENT CLASSIFICATION
    # =================================================
    intent = classify_intent(
        subject=email.subject,
        body=email.body,
    )

    email.intent_status = intent["intent"]
    email.intent_confidence = intent["confidence_score"]
    email.intent_reason = intent["reason"]
    await db.flush()

    # =================================================
    # 2. NOT A DISPUTE
    # =================================================
    if intent["intent"] == "NOT_DISPUTE":
        await db.commit()
        return None

    # =================================================
    # 3. AMBIGUOUS → ALWAYS CLARIFY
    # =================================================
    if intent["intent"] == "AMBIGUOUS":

        # ---- Thread-level guard ----
        if email.thread_id:
            existing = await db.execute(
                select(Email).where(
                    Email.thread_id == email.thread_id,
                    Email.clarification_sent.is_(True),
                )
            )
            if existing.scalars().first():
                await db.commit()
                return {
                    "action": "WAITING",
                    "reason": "Clarification already sent for this thread",
                }

        # ---- Extraction ONLY for wording ----
        extraction = extract_facts_and_clarification(
            subject=email.subject,
            body=email.body,
        )

        clarification_text = extraction.get("email_body")

        # Deterministic fallback (guaranteed)
        if not clarification_text:
            clarification_text = (
                "We’ve reviewed your message and would like to understand "
                "the issue in more detail. Please clarify what action you "
                "would like us to take so we can proceed."
            )

        send_reply(
            service=gmail_service,
            to=sender,
            subject=f"Re: {email.subject}",
            body=clarification_text,
            thread_id=email.thread_id,
            in_reply_to=email.gmail_message_id,
        )

        email.clarification_sent = True
        await db.commit()

        return {
            "action": "CLARIFICATION_SENT",
            "reason": "Intent ambiguous",
        }

    # =================================================
    # 4. DISPUTE PATH (ONLY FOR DISPUTE)
    # =================================================
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

    # =================================================
    # 4a. MATCH EXISTING DISPUTE
    # =================================================
    if decision["action"] == "MATCH":
        dispute_id = decision["dispute_id"]

        email.dispute_id = dispute_id
        await db.flush()

        dispute = await db.get(Dispute, dispute_id)
        if dispute:
            await resummarize_dispute(
                db=db,
                dispute=dispute,
            )

        await db.commit()
        return decision
    # =================================================
    # 4b. CREATE NEW DISPUTE
    # =================================================
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
