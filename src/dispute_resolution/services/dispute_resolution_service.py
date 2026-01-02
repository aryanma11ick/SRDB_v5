from sqlalchemy.ext.asyncio import AsyncSession

from dispute_resolution.models import Email, Dispute
from dispute_resolution.services.intent_service import classify_intent
from dispute_resolution.services.clarification_service import generate_clarification_email
from dispute_resolution.services.embedding_service import embed_email
from dispute_resolution.services.vector_search_service import find_candidate_disputes
from dispute_resolution.services.decision_service import decide_dispute
from dispute_resolution.services.summary_service import generate_dispute_summary
from dispute_resolution.services.thread_service import find_dispute_by_thread


async def resolve_email(
    *,
    db: AsyncSession,
    email: Email,
) -> dict | None:
    """
    Orchestrates full dispute resolution for a single email.

    Returns:
    - dict → when a dispute is MATCHED or CREATED
    - None → for NON_DISPUTE or AMBIGUOUS cases
    """


    # ---- 0. THREAD-AWARE FAST PATH (NEW) ----
    if email.thread_id:
        dispute = await find_dispute_by_thread(
            db=db,
            supplier_id=email.supplier_id,
            thread_id=email.thread_id,
        )

        if dispute:
            email.dispute_id = dispute.id
            email.intent_status = "DISPUTE"
            email.intent_reason = "Matched via Gmail thread"
            email.intent_confidence = 1.0

            await db.commit()

            return {
                "action": "MATCH_THREAD",
                "dispute_id": str(dispute.id),
                "reason": "Matched via Gmail thread",
            }


    # ---- 1. Intent classification ----
    intent = classify_intent(
        subject=email.subject,
        body=email.body,
    )

    email.intent_status = intent["intent"]
    email.intent_reason = intent["reason"]
    email.intent_confidence = intent["confidence_score"]
    await db.flush()

    # ---- 2. NOT-DISPUTE ----
    if intent["intent"] == "NOT_DISPUTE":
        await db.commit()
        return None

    # ---- 3. AMBIGUOUS → clarification ----
    if intent["intent"] == "AMBIGUOUS":
        clarification = generate_clarification_email(
            subject=email.subject,
            body=email.body,
        )
        await db.commit()
        return {
            "action": "CLARIFICATION_SENT",
            "dispute_id": None,
            "reason": "Low confidence dispute – clarification requested",
        }

    # ---- 4. DISPUTE path ----
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
    if not candidates:
        decision = {
            "action": "NEW",
            "dispute_id": None,
            "reason": "No similar disputes found",
        }
    else:
        decision = decide_dispute(
            subject=email.subject,
            body=email.body,
            candidate_disputes=candidates,
        )
        
    # ---- 4a. MATCH ----
    if decision["action"] == "MATCH":
        email.dispute_id = decision["dispute_id"]
        await db.commit()
        return decision

    # ---- 4b. NEW DISPUTE ----
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
    await db.flush()

    email.dispute_id = dispute.id
    await db.commit()

    return {
        "action": "NEW",
        "dispute_id": str(dispute.id),
        "reason": "New dispute created",
    }
