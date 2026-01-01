from sqlalchemy.ext.asyncio import AsyncSession

from dispute_resolution.ingestion.message_parser import parse_gmail_message
from dispute_resolution.models import Email, ProcessedGmailMessage
from dispute_resolution.utils.logging import logger
from dispute_resolution.services.supplier_service import get_supplier_by_domain
from dispute_resolution.services.embedding_service import embed_email


def _extract_domain(from_header: str) -> str | None:
    if "@" not in from_header:
        return None
    return from_header.split("@")[-1].strip(">").lower()


async def process_message(db: AsyncSession, gmail_message: dict) -> None:
    """
    Process a single Gmail message:
    - idempotency check
    - supplier lookup
    - generate embedding
    - store email
    - mark as processed
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

    # 3. Generate embedding (NEW)
    embedding = embed_email(
        subject=parsed["subject"],
        body=parsed["body"],
    )

    # 4. Insert email with embedding
    email = Email(
        supplier_id=supplier.id,
        dispute_id=None,
        subject=parsed["subject"],
        body=parsed["body"],
        embedding=embedding,
        gmail_message_id=gmail_id,
    )
    db.add(email)

    # 5. Mark Gmail message as processed
    db.add(
        ProcessedGmailMessage(
            gmail_message_id=gmail_id,
            was_dispute=False,
        )
    )

    await db.commit()
    logger.info(f"Ingested + embedded email {gmail_id} for supplier {supplier.name}")
