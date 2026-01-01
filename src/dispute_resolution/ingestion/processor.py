from sqlalchemy.ext.asyncio import AsyncSession

from dispute_resolution.ingestion.message_parser import parse_gmail_message
from dispute_resolution.ingestion.gmail_client import add_labels, LABELS
from dispute_resolution.models import Email, ProcessedGmailMessage
from dispute_resolution.services.dispute_resolution_service import resolve_email
from dispute_resolution.services.supplier_service import get_supplier_by_domain
from dispute_resolution.utils.logging import logger


def _extract_domain(from_header: str) -> str | None:
    if "@" not in from_header:
        return None
    return from_header.split("@")[-1].strip(">").lower()


async def process_message(
    db: AsyncSession,
    gmail_service,
    gmail_message: dict,
) -> None:
    """
    Ingest a Gmail message and delegate all business logic to resolve_email().
    Gmail labeling is applied AFTER DB commit.
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

    # 3. Create Email record (NO business logic)
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

    # 5. Mark as processed
    db.add(
        ProcessedGmailMessage(
            gmail_message_id=gmail_id,
            was_dispute=decision is not None,
        )
    )

    await db.commit()

    # ---------------- Gmail labeling ----------------
    labels_to_add = [LABELS["processed"]]

    if decision is None:
        if email.intent_status == "NOT_DISPUTE":
            labels_to_add.append(LABELS["not_dispute"])
        else:
            # AMBIGUOUS / CLARIFICATION
            labels_to_add.append(LABELS["ambiguous"])
    else:
        labels_to_add.append(LABELS["dispute"])

    add_labels(
        service=gmail_service,
        message_id=gmail_id,
        label_ids=labels_to_add,
    )

    # Remove UNREAD label
    gmail_service.users().messages().modify(
        userId="me",
        id=gmail_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()
    # ------------------------------------------------

    # Logging
    if decision is None:
        logger.info(f"Processed email {gmail_id} | No dispute created")
    else:
        logger.info(
            f"Processed DISPUTE email {gmail_id} | "
            f"Action={decision['action']} | "
            f"Dispute={decision.get('dispute_id')}"
        )
