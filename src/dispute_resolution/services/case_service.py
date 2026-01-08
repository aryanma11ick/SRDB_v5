# src/dispute_resolution/services/case_service.py

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from dispute_resolution.models import Case, Email


# -------------------------
# Fetch
# -------------------------

async def get_open_intake_case_by_thread(
    *,
    db: AsyncSession,
    supplier_id,
    thread_id: str | None,
) -> Case | None:
    if not thread_id:
        return None

    stmt = (
        select(Case)
        .where(
            Case.supplier_id == supplier_id,
            Case.thread_id == thread_id,
            Case.case_type == "INTAKE",
            Case.status.in_(["INTAKE_PENDING", "INTAKE_WAITING"]),
        )
        .limit(1)
    )

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# -------------------------
# Create
# -------------------------

async def create_intake_case(
    *,
    db: AsyncSession,
    email: Email,
) -> Case:
    case = Case(
        supplier_id=email.supplier_id,
        thread_id=email.thread_id,
        case_type="INTAKE",
        status="INTAKE_PENDING",
        intake_email_id=email.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(case)
    await db.flush()
    return case


# -------------------------
# Transition
# -------------------------

async def mark_intake_waiting(case: Case) -> None:
    if case.status != "INTAKE_WAITING":
        case.status = "INTAKE_WAITING"
        case.updated_at = datetime.now(timezone.utc)


async def promote_intake_to_dispute(
    *,
    case: Case,
    dispute_id,
) -> None:
    """
    Convert an INTAKE case into an active DISPUTE case.
    """
    case.case_type = "DISPUTE"
    case.status = "DISPUTE_OPEN"
    case.dispute_id = dispute_id
    case.updated_at = datetime.now(timezone.utc)