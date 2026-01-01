from sqlalchemy.ext.asyncio import AsyncSession

from dispute_resolution.ingestion.message_parser import parse_gmail_message
from dispute_resolution.models import Email, ProcessedGmailMessage
from dispute_resolution.services.dispute_resolution_service import resolve_email
from dispute_resolution.services.supplier_service import get_supplier_by_domain
from dispute_resolution.utils.logging import logger


def _extract_domain(from_header: str) -> str | None:
    if "@" not in from_header:
        return None
    return from_header.split("@")[-1].strip(">").lower()


async def process_message(db: AsyncSession, gmail_message: dict) -> None:
    """
    Ingest a Gmail message and delegate full processing to resolve_email().
    """

    parsed = parse_gmail_message(gmail_message)
    gmail_id = parsed["gmail_message_id"]

    # 1. Idempotency
    if await db.get(ProcessedGmailMessage, gmail_id):
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

    # 3. Create email record (NO business logic here)
    email = Email(
        supplier_id=supplier.id,
        subject=parsed["subject"],
        body=parsed["body"],
        gmail_message_id=gmail_id,
    )
    db.add(email)
    await db.flush()

    # 4. Delegate to dispute resolution pipeline
    decision = await resolve_email(
        db=db,
        email=email,
    )

    # 5. Mark Gmail message as processed
    db.add(
        ProcessedGmailMessage(
            gmail_message_id=gmail_id,
            was_dispute=decision is not None,
        )
    )

    await db.commit()

    if decision is None:
        logger.info(f"Processed email {gmail_id} | No dispute created")
    else:
        logger.info(
            f"Processed DISPUTE email {gmail_id} | "
            f"Action={decision['action']} | "
            f"Dispute={decision.get('dispute_id')}"
        )
