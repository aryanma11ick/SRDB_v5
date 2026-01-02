from sqlalchemy.ext.asyncio import AsyncSession

from dispute_resolution.ingestion.message_parser import parse_gmail_message
from dispute_resolution.ingestion.gmail_client import modify_message_labels
from dispute_resolution.models import Email, ProcessedGmailMessage
from dispute_resolution.services.dispute_resolution_service import resolve_email
from dispute_resolution.services.supplier_service import get_supplier_by_domain
from dispute_resolution.utils.logging import logger
from dispute_resolution.config import settings


def _extract_domain(from_header: str) -> str | None:
    if "@" not in from_header:
        return None
    return from_header.split("@")[-1].strip(">").lower()


def is_system_email(parsed: dict) -> bool:
    sender = parsed.get("sender", "").lower()
    return settings.SYSTEM_EMAIL_ADDRESS.lower() in sender


async def process_message(
    db: AsyncSession,
    gmail_service,
    label_map: dict[str, str],
    gmail_message: dict,
) -> None:
    """
    Ingest a Gmail message and delegate all business logic to resolve_email().
    Gmail labeling is applied AFTER DB commit.
    """

    parsed = parse_gmail_message(gmail_message)
    gmail_id = parsed["gmail_message_id"]

    # -------------------------------------------------
    # 0. HARD STOP: Ignore system-generated emails
    # -------------------------------------------------
    if is_system_email(parsed):
        logger.info(f"Ignoring SYSTEM email {gmail_id}")

        # Ensure idempotency
        if not await db.get(ProcessedGmailMessage, gmail_id):
            db.add(
                ProcessedGmailMessage(
                    gmail_message_id=gmail_id,
                    was_dispute=False,
                )
            )
            await db.commit()

        # Mark processed + read in Gmail
        modify_message_labels(
            service=gmail_service,
            message_id=gmail_id,
            add=[label_map["Processed"]],
            remove=["UNREAD"],
        )
        return

    # -------------------------------------------------
    # 1. Idempotency
    # -------------------------------------------------
    if await db.get(ProcessedGmailMessage, gmail_id):
        logger.info(f"Skipping already processed message {gmail_id}")
        return

    # -------------------------------------------------
    # 2. Supplier detection
    # -------------------------------------------------
    domain = _extract_domain(parsed["sender"])
    if not domain:
        logger.warning(f"Could not extract domain from sender: {parsed['sender']}")
        return

    supplier = await get_supplier_by_domain(db, domain)
    if not supplier:
        logger.info(f"Unknown supplier domain '{domain}', skipping")
        return

    # -------------------------------------------------
    # 3. Create Email record (NO business logic)
    # -------------------------------------------------
    email = Email(
        supplier_id=supplier.id,
        subject=parsed["subject"],
        body=parsed["body"],
        gmail_message_id=gmail_id,
        thread_id=parsed.get("thread_id"),
    )
    db.add(email)
    await db.flush()

    # -------------------------------------------------
    # 4. Delegate to dispute resolution pipeline
    # -------------------------------------------------
    decision = await resolve_email(
        db=db,
        email=email,
        gmail_service=gmail_service,
        sender=parsed["sender"],
    )

    # -------------------------------------------------
    # 5. Persist processed state
    # -------------------------------------------------
    was_dispute = decision is not None and decision["action"] in {"NEW", "MATCH"}

    db.add(
        ProcessedGmailMessage(
            gmail_message_id=gmail_id,
            was_dispute=was_dispute,
        )
    )
    await db.commit()

    # -------------------------------------------------
    # 6. Gmail labeling (AFTER commit)
    # -------------------------------------------------
    labels_to_add = [label_map["Processed"]]
    labels_to_remove = ["UNREAD"]

    if decision is None:
        if email.intent_status == "NOT_DISPUTE":
            labels_to_add.append(label_map["Not_Dispute"])
        else:
            labels_to_add.append(label_map["Needs_Clarification"])
    else:
        if decision["action"] in {"NEW", "MATCH"}:
            labels_to_add.append(label_map["Dispute"])
        else:
            labels_to_add.append(label_map["Needs_Clarification"])

    modify_message_labels(
        service=gmail_service,
        message_id=gmail_id,
        add=labels_to_add,
        remove=labels_to_remove,
    )

    # -------------------------------------------------
    # 7. Logging
    # -------------------------------------------------
    if decision is None:
        logger.info(f"Processed email {gmail_id} | No dispute created")
    else:
        logger.info(
            f"Processed DISPUTE email {gmail_id} | "
            f"Action={decision['action']} | "
            f"Dispute={decision.get('dispute_id')}"
        )
