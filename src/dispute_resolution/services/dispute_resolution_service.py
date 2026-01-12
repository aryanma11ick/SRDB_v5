from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta

from dispute_resolution.models import Email, Dispute
from dispute_resolution.services.intent_service import classify_intent
from dispute_resolution.services.fact_extraction_service import extract_facts
from dispute_resolution.services.clarification_service import build_clarification_email
from dispute_resolution.services.embedding_service import embed_email
from dispute_resolution.services.vector_search_service import find_candidate_disputes
from dispute_resolution.services.decision_service import decide_dispute
from dispute_resolution.services.summary_service import (
    generate_dispute_summary,
    resummarize_dispute,
)
from dispute_resolution.services.thread_service import get_thread_context
from dispute_resolution.services.reply_service import send_reply, build_reply_subject


AMBIGUOUS_TTL_HOURS = 24


def clarification_expired(sent_at: datetime | None) -> bool:
    if not sent_at:
        return False
    return datetime.now(timezone.utc) > (
        sent_at + timedelta(hours=AMBIGUOUS_TTL_HOURS)
    )


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
    # 0. THREAD SHORT-CIRCUIT (already linked dispute)
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
    # 2. FACT EXTRACTION
    # =================================================
    extraction = extract_facts(
        subject=email.subject,
        body=email.body,
    )

    email.extracted_facts = extraction["facts"]
    email.fact_confidence = extraction["confidence"]
    email.missing_fields = extraction["missing_fields"]
    await db.flush()

    # =================================================
    # 3. NOT A DISPUTE
    # =================================================
    if intent["intent"] == "NOT_DISPUTE":
        await db.commit()
        return None

    # =================================================
    # 4. AMBIGUOUS → SEND CLARIFICATION (TTL-SAFE)
    # =================================================
    if intent["intent"] == "AMBIGUOUS":

        if email.thread_id:
            existing = await db.execute(
                select(Email)
                .where(
                    Email.thread_id == email.thread_id,
                    Email.clarification_sent.is_(True),
                )
                .order_by(Email.received_at.desc())
                .limit(1)
            )
            prev = existing.scalar_one_or_none()

            if prev and not clarification_expired(prev.clarification_sent_at):
                await db.commit()
                return {
                    "action": "WAITING",
                    "reason": "Awaiting clarification (within TTL)",
                }

        clarification_text = build_clarification_email(
            known_facts=extraction["facts"],
            missing_fields=extraction["missing_fields"][:2],
        )

        send_reply(
            service=gmail_service,
            to=sender,
            subject=build_reply_subject(email.subject),
            body=clarification_text,
            in_reply_to=email.gmail_message_id,
            thread_id=email.thread_id,
        )

        email.clarification_sent = True
        email.clarification_sent_at = datetime.now(timezone.utc)

        await db.commit()
        return {
            "action": "CLARIFICATION_SENT",
            "reason": "Awaiting clarification from supplier",
        }

    # =================================================
    # 5. DISPUTE PATH (STRONG SIGNAL ONLY)
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

    if candidates:
        decision = decide_dispute(
            subject=email.subject,
            body=email.body,
            extracted_facts=extraction["facts"],
            candidate_disputes=candidates,
        )
    else:
        decision = {
            "action": "NEW",
            "dispute_id": None,
            "reason": "No candidate disputes found",
        }

    # =================================================
    # 5a. MATCH
    # =================================================
    if decision["action"] == "MATCH":
        dispute_id = decision["dispute_id"]

        email.dispute_id = dispute_id
        await db.flush()

        dispute = await db.get(Dispute, dispute_id)
        if dispute:
            await resummarize_dispute(db=db, dispute=dispute)

        await db.commit()
        return decision

    # =================================================
    # 5b. NEW DISPUTE
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
