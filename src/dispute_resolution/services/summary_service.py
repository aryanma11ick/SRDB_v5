from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from typing import Optional
from dispute_resolution.models import Dispute, Email
from dispute_resolution.services.embedding_service import embed_email
from dispute_resolution.llm.client import llm
from dispute_resolution.llm.prompts import SUMMARY_PROMPT, DISPUTE_CANONICAL_SUMMARY_PROMPT
from dispute_resolution.utils.llm import normalize_llm_content

def generate_dispute_summary(subject: str, body: str) -> str:
    prompt = SUMMARY_PROMPT.format(subject=subject, body=body)
    response = llm.invoke(prompt)
    return normalize_llm_content(response.content).strip()

async def resummarize_dispute(
    *,
    db: AsyncSession,
    dispute: Dispute,
) -> None:
    """
    Rebuild the canonical dispute summary from ALL linked supplier emails
    and update summary + embedding.
    """

    # 1. Fetch all emails linked to the dispute
    result = await db.execute(
        select(Email)
        .where(Email.dispute_id == dispute.id)
        .order_by(Email.received_at.asc())
    )
    emails = result.scalars().all()

    # Defensive filtering
    emails = [e for e in emails if not e.clarification_sent]

    if not emails:
        return

    # 2. Build canonical context
    combined_body = "\n\n---\n\n".join(
        f"Subject: {e.subject}\nBody:\n{e.body}"
        for e in emails
    )

    # 3. Generate canonical summary
    prompt = DISPUTE_CANONICAL_SUMMARY_PROMPT.format(
        body=combined_body
    )

    response = llm.invoke(prompt)
    summary = normalize_llm_content(response.content).strip()

    # 4. Update dispute
    dispute.summary = summary
    dispute.summary_embedding = embed_email(
        subject="Dispute summary",
        body=summary,
    )
    dispute.updated_at = datetime.now(timezone.utc)

    await db.flush()

def generate_dispute_summary_from_intake(
    *,
    invoice_number: str,
    purchase_order_number: str,
    amount: float,
    currency: str,
    reason: Optional[str] = None,
) -> str:
    """
    Generate a canonical dispute summary using ONLY intake-level facts.

    This summary is:
    - Deterministic
    - Stable across emails
    - Safe from LLM hallucination
    """

    base = (
        f"This dispute relates to invoice {invoice_number} against purchase order "
        f"{purchase_order_number}, where an amount of {currency} {amount:,.2f} "
        f"is being disputed."
    )

    if reason:
        return f"{base} The supplier has indicated the following reason for the dispute: {reason}."

    return base