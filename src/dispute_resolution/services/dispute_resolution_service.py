from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

from dispute_resolution.models import Email, Dispute
from dispute_resolution.services.intent_service import classify_intent
from dispute_resolution.services.fact_extraction_service import extract_facts
from dispute_resolution.services.clarification_service import build_clarification_email
from dispute_resolution.services.embedding_service import embed_email
from dispute_resolution.services.vector_search_service import find_candidate_disputes
from dispute_resolution.services.decision_service import decide_dispute
from dispute_resolution.services.summary_service import (
    generate_dispute_summary_from_intake,
    generate_dispute_summary,
    resummarize_dispute,
)
from dispute_resolution.services.reply_service import send_reply, build_reply_subject

from dispute_resolution.services.intake_service import (
    get_or_create_dispute_intake,
    merge_facts_into_intake,
    intake_is_complete,
    mark_clarification_sent,
    mark_intake_dropped,
    promote_intake_to_dispute,
    extract_keys,
)
MAX_CLARIFICATIONS = 5

async def resolve_email(
    *,
    db: AsyncSession,
    email: Email,
    gmail_service,
    sender: str,
) -> dict | None:
    """
    Final resolution pipeline.

    Returns:
    - MATCH
    - NEW
    - CLARIFICATION_SENT
    - DROPPED
    - None → NOT_DISPUTE
    """

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

    if intent["intent"] == "NOT_DISPUTE":
        await db.commit()
        return None

    # =================================================
    # 2. FACT EXTRACTION
    # =================================================
    extraction = extract_facts(
        subject=email.subject,
        body=email.body,
    )

    email.extracted_facts = extraction["facts"]
    email.fact_confidence = extraction["confidence"]
    await db.flush()

    # =================================================
    # 3. GET OR CREATE INTAKE (SINGLE SOURCE OF TRUTH)
    # =================================================
    intake = await get_or_create_dispute_intake(
        db=db,
        supplier_id=email.supplier_id,
        thread_id=email.thread_id,
        root_gmail_message_id=email.root_gmail_message_id,
        extracted_facts=extraction["facts"],
    )

    # Merge again defensively (safe & idempotent)
    merge_facts_into_intake(
        intake=intake,
        extracted_facts=extraction["facts"],
    )

    # =================================================
    # 4. INTAKE INCOMPLETE → CLARIFY OR DROP
    # =================================================
    if not intake_is_complete(intake):

        if intake.clarification_count >= MAX_CLARIFICATIONS:
            mark_intake_dropped(intake)
            await db.commit()
            return {
                "action": "DROPPED",
                "reason": "Maximum clarification attempts exceeded",
            }

        missing: list[str] = []
        if not intake.invoice_number:
            missing.append("invoice_number")
        if not intake.purchase_order_number:
            missing.append("purchase_order_number")
        if not intake.reason:
            missing.append("reason")
        if intake.amount is None:
            missing.append("amount")

        clarification_text = build_clarification_email(
            intent_reason=email.intent_reason or "The issue details are unclear.",
            known_facts=extraction["facts"],
            missing_fields=missing,
        )

        send_reply(
            service=gmail_service,
            to=sender,
            subject=build_reply_subject(email.subject),
            body=clarification_text,
            in_reply_to=intake.root_gmail_message_id,
            thread_id=intake.thread_id,
        )

        mark_clarification_sent(intake)
        await db.commit()

        return {
            "action": "CLARIFICATION_SENT",
            "reason": f"Clarification attempt {intake.clarification_count}/{MAX_CLARIFICATIONS}",
        }


    # =================================================
    # 5. INTAKE COMPLETE → PROMOTE TO DISPUTE
    # =================================================
    summary = generate_dispute_summary_from_intake(
        invoice_number=intake.invoice_number,
        purchase_order_number=intake.purchase_order_number,
        amount=intake.amount,
        currency=intake.currency,
        reason=intake.reason,
    )

    dispute = await promote_intake_to_dispute(
        db=db,
        intake=intake,
        summary=summary,
    )

    email.dispute_id = dispute.id
    await db.flush()

    # =================================================
    # 6. OPTIONAL MATCH WITH EXISTING DISPUTES
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

        if decision.get("action") == "MATCH":
            dispute_id_raw = decision.get("dispute_id")

            # Normalize UUID safely
            if isinstance(dispute_id_raw, str):
                dispute_id = UUID(dispute_id_raw)
            elif isinstance(dispute_id_raw, UUID):
                dispute_id = dispute_id_raw
            else:
                dispute_id = None

            if dispute_id:
                email.dispute_id = dispute_id
                intake.dispute_id = dispute_id

                existing = await db.get(Dispute, dispute_id)
                if existing:
                    await resummarize_dispute(db=db, dispute=existing)

                await db.commit()
                return {
                    "action": "MATCH",
                    "dispute_id": dispute_id,
                    "reason": decision.get("reason"),
                }

    # =================================================
    # 7. NEW DISPUTE (DEFAULT)
    # =================================================
    await db.commit()

    return {
        "action": "NEW",
        "dispute_id": dispute.id,
        "reason": "New dispute created from completed intake",
    }
