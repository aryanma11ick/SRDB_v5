from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

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