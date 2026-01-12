# src/dispute_resolution/services/intake_service.py

from datetime import datetime, timezone

from typing import Dict, Any, Optional, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from dispute_resolution.models import Dispute, DisputeIntake
from dispute_resolution.models import (
    INTAKE_WAITING,
    INTAKE_CLARIFYING,
    INTAKE_READY,
    INTAKE_DROPPED,
)
from dispute_resolution.services.embedding_service import embed_email

# ==================================================
# Constants
# ==================================================

MAX_CLARIFICATIONS = 5

ACTIVE_STATES = (INTAKE_WAITING, INTAKE_CLARIFYING)


# ==================================================
# Helpers
# ==================================================

def _first_valid(values: Optional[List[str]]) -> Optional[str]:
    if not values:
        return None
    value = values[0]
    if not value or value == "UNKNOWN":
        return None
    return value


def extract_keys(
    extracted_facts: Dict[str, Any],
) -> Tuple[Optional[str], Optional[str], Optional[float], Optional[str]]:
    """
    Extract canonical identifiers from extracted facts.
    """
    ci = extracted_facts.get("commercial_identifiers", {})
    fin = extracted_facts.get("financials", {})

    invoice = _first_valid(ci.get("invoice_numbers"))
    po = _first_valid(ci.get("purchase_order_numbers"))

    disputed = fin.get("disputed_amount", {}) or {}
    amount = disputed.get("value")
    currency = disputed.get("currency")

    return invoice, po, amount, currency


# ==================================================
# Intake lookup (BUSINESS KEY BASED)
# ==================================================

async def find_open_intake(
    *,
    db: AsyncSession,
    supplier_id,
    invoice_number: Optional[str],
    purchase_order_number: Optional[str],
) -> Optional[DisputeIntake]:
    """
    Find an existing open intake using business identifiers.
    Priority:
      1. Invoice number
      2. Purchase order number
    """

    if invoice_number:
        stmt = (
            select(DisputeIntake)
            .where(
                DisputeIntake.supplier_id == supplier_id,
                DisputeIntake.invoice_number == invoice_number,
                DisputeIntake.status.in_(ACTIVE_STATES),
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        intake = result.scalar_one_or_none()
        if intake:
            return intake

    if purchase_order_number:
        stmt = (
            select(DisputeIntake)
            .where(
                DisputeIntake.supplier_id == supplier_id,
                DisputeIntake.purchase_order_number == purchase_order_number,
                DisputeIntake.status.in_(ACTIVE_STATES),
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    return None


# ==================================================
# Intake creation
# ==================================================

async def get_or_create_dispute_intake(
    *,
    db: AsyncSession,
    supplier_id,
    thread_id: Optional[str],
    root_gmail_message_id: str,
    extracted_facts: Dict[str, Any],
) -> DisputeIntake:
    """
    Returns an existing open intake or creates a new one.
    """

    invoice, po, _, _ = extract_keys(extracted_facts)

    existing = await find_open_intake(
        db=db,
        supplier_id=supplier_id,
        invoice_number=invoice,
        purchase_order_number=po,
    )

    if existing:
        return existing

    intake = DisputeIntake(
        supplier_id=supplier_id,
        thread_id=thread_id,
        root_gmail_message_id=root_gmail_message_id,
        status=INTAKE_WAITING,
        clarification_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    merge_facts_into_intake(
        intake=intake,
        extracted_facts=extracted_facts,
    )

    db.add(intake)

    try:
        await db.flush()
        return intake

    except IntegrityError:
        # Race condition fallback
        await db.rollback()

        fallback = await find_open_intake(
            db=db,
            supplier_id=supplier_id,
            invoice_number=invoice,
            purchase_order_number=po,
        )

        if not fallback:
            raise RuntimeError(
                "IntegrityError occurred but no intake could be recovered"
            )

        return fallback


# ==================================================
# Fact aggregation (SAFE MERGE)
# ==================================================

def merge_facts_into_intake(
    *,
    intake: DisputeIntake,
    extracted_facts: Dict[str, Any],
) -> None:
    invoice, po, amount, currency = extract_keys(extracted_facts)

    if not intake.invoice_number and invoice:
        intake.invoice_number = invoice

    if not intake.purchase_order_number and po:
        intake.purchase_order_number = po

    if intake.amount is None and amount is not None:
        intake.amount = amount
        intake.currency = currency

    # ✅ NEW: merge reason
    issue = extracted_facts.get("issue", {})
    description = issue.get("description")

    if not intake.reason and description:
        lowered = description.lower()
        if lowered not in ("issue", "invoice issue", "discrepancy", "unknown"):
            intake.reason = description

    intake.updated_at = datetime.now(timezone.utc)


# ==================================================
# Completeness rules
# ==================================================

def intake_is_complete(intake):
    return (
        bool(intake.invoice_number)
        and bool(intake.purchase_order_number)
        and intake.amount is not None
        and intake.reason
    )


# ==================================================
# Clarification control
# ==================================================


def can_send_clarification(intake: DisputeIntake) -> bool:
    return (
        intake.status not in (INTAKE_READY, INTAKE_DROPPED)
        and not intake_is_complete(intake)
        and intake.clarification_count < MAX_CLARIFICATIONS
    )


def mark_clarification_sent(intake: DisputeIntake) -> None:
    """
    Record that a clarification was sent.
    Hard-safe: will not modify completed intakes.
    """

    if intake_is_complete(intake):
        return

    intake.clarification_count += 1
    intake.last_clarification_at = datetime.now(timezone.utc)
    intake.status = INTAKE_CLARIFYING
    intake.updated_at = datetime.now(timezone.utc)


def mark_intake_dropped(intake: DisputeIntake) -> None:
    intake.status = INTAKE_DROPPED
    intake.updated_at = datetime.now(timezone.utc)


# ==================================================
# Promotion
# ==================================================

async def promote_intake_to_dispute(
    *,
    db: AsyncSession,
    intake: DisputeIntake,
    summary: str,
) -> Dispute:
    """
    Convert a completed intake into a Dispute.
    """

    summary_embedding = embed_email(
        subject="Dispute summary",
        body=summary,
    )
    
    dispute = Dispute(
        supplier_id=intake.supplier_id,
        summary=summary,
        summary_embedding=summary_embedding,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(dispute)
    await db.flush()

    intake.dispute_id = dispute.id
    intake.status = INTAKE_READY
    intake.updated_at = datetime.now(timezone.utc)

    return dispute
