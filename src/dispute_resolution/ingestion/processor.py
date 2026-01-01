from sqlalchemy.ext.asyncio import AsyncSession

from dispute_resolution.ingestion.message_parser import parse_gmail_message
from dispute_resolution.models import Email, ProcessedGmailMessage
from dispute_resolution.utils.logging import logger

from dispute_resolution.services.intent_service import classify_intent
from dispute_resolution.services.clarification_service import generate_clarification_email
from dispute_resolution.services.embedding_service import embed_email
from dispute_resolution.services.vector_search_service import find_candidate_disputes
from dispute_resolution.services.dispute_resolution_service import resolve_email
from dispute_resolution.services.supplier_service import get_supplier_by_domain


def _extract_domain(from_header: str) -> str | None:
    if "@" not in from_header:
        return None
    return from_header.split("@")[-1].strip(">").lower()


async def process_message(db: AsyncSession, gmail_message: dict) -> None:
    """
    Process a single Gmail message with intent gating.
    """

    parsed = parse_gmail_message(gmail_message)
    gmail_id = parsed["gmail_message_id"]

    # 1. Idempotency
    exists = await db.get(ProcessedGmailMessage, gmail_id)
    if exists:
        logger.info(f"Skipping already processed message {gmail_id}")
        return

    # 2. Supplier detection
    domain = _extract_domain(parsed["sender"])
    if not domain:
        logger.warning(f"Could not extract domain from sender: {parsed['sender']}")
        return

    supplier = await get_supplier_by_domain(db, domain)
    if not supplier:
        logger.info(f"Unknown supplier domain '{domain}', skipping")
        return

    # 3. Intent classification (NEW)
    intent_result = classify_intent(
        subject=parsed["subject"],
        body=parsed["body"],
    )

    intent = intent_result["intent"]
    reason = intent_result["reason"]

    # 4. Store email metadata first (no embeddings yet)
    email = Email(
        supplier_id=supplier.id,
        subject=parsed["subject"],
        body=parsed["body"],
        gmail_message_id=gmail_id,
        intent_status=intent,
        intent_reason=reason,
    )
    db.add(email)
    await db.flush()  # get email.id

    # 5. Handle intent cases
    if intent == "NOT_DISPUTE":
        logger.info(f"Email {gmail_id} classified as NOT_DISPUTE")
        db.add(ProcessedGmailMessage(
            gmail_message_id=gmail_id,
            was_dispute=False,
        ))
        await db.commit()
        return

    if intent == "AMBIGUOUS":
        logger.info(f"Email {gmail_id} classified as AMBIGUOUS")

        clarification_text = generate_clarification_email(
            subject=parsed["subject"],
            body=parsed["body"],
        )

        # TODO: send clarification via Gmail API
        logger.info("Generated clarification email:")
        logger.info(clarification_text)

        email.intent_status = "PENDING_CLARIFICATION"

        db.add(ProcessedGmailMessage(
            gmail_message_id=gmail_id,
            was_dispute=False,
        ))
        await db.commit()
        return

    # 6. DISPUTE → continue pipeline
    logger.info(f"Email {gmail_id} classified as DISPUTE")

    email.embedding = embed_email(
        subject=parsed["subject"],
        body=parsed["body"],
    )

    candidates = await find_candidate_disputes(
        db=db,
        supplier_id=supplier.id,
        email_embedding=email.embedding,
        k=3,
    )

    decision = await resolve_email(
        db=db,
        email=email,
        candidate_disputes=candidates,
    )

    db.add(ProcessedGmailMessage(
        gmail_message_id=gmail_id,
        was_dispute=True,
    ))

    await db.commit()

    logger.info(
        f"Processed DISPUTE email {gmail_id} | "
        f"Action={decision['action']} | "
        f"Dispute={decision.get('dispute_id')}"
    )
