import asyncio
from sqlalchemy import select

from dispute_resolution.database import AsyncSessionLocal
from dispute_resolution.models import Email, Dispute
from dispute_resolution.services.dispute_resolution_service import resolve_email


TEST_EMAILS = [
    # --- CLEAR DISPUTE (new) ---
    {
        "subject": "Overcharge identified on Invoice INV-9123",
        "body": (
            "Hi AP Team,\n\n"
            "We noticed an overcharge on Invoice INV-9123. "
            "The invoiced amount is INR 18,750, whereas the agreed PO value was INR 16,500.\n\n"
            "Please advise on the correction.\n\n"
            "Regards,\nABC Chemicals"
        ),
        "expected_intent": "DISPUTE",
    },

    # --- FOLLOW-UP (same dispute, should MATCH) ---
    {
        "subject": "Follow-up: Overcharge on Invoice INV-9123",
        "body": (
            "Hi Team,\n\n"
            "Following up on our earlier email regarding the overcharge on Invoice INV-9123.\n"
            "Awaiting the revised invoice.\n\n"
            "Regards,\nABC Chemicals"
        ),
        "expected_intent": "DISPUTE",
    },

    # --- DIFFERENT DISPUTE (new invoice) ---
    {
        "subject": "Short payment on Invoice INV-8812",
        "body": (
            "Hello,\n\n"
            "Invoice INV-8812 was partially paid. "
            "There is an outstanding balance of INR 3,200.\n\n"
            "Please clarify.\n\n"
            "Thanks,\nABC Chemicals"
        ),
        "expected_intent": "DISPUTE",
    },

    # --- NON-DISPUTE (should be ignored) ---
    {
        "subject": "Happy New Year!",
        "body": (
            "Hi Team,\n\n"
            "Wishing you and your team a very happy new year.\n\n"
            "Best regards,\nABC Chemicals"
        ),
        "expected_intent": "NON_DISPUTE",
    },

    # --- AMBIGUOUS (clarification path) ---
    {
        "subject": "Invoice INV-9901",
        "body": (
            "Hi,\n\n"
            "There seems to be an issue with Invoice INV-9901.\n"
            "Please look into it.\n\n"
            "Regards,\nABC Chemicals"
        ),
        "expected_intent": "AMBIGUOUS",
    },
]


SUPPLIER_ID = "45917f45-baa5-4b53-8e7b-5c504b74f85e"


async def run():
    async with AsyncSessionLocal() as db:
        for i, item in enumerate(TEST_EMAILS, start=1):
            print(f"\n--- Processing email {i} ---")
            print("Subject:", item["subject"])

            email = Email(
                supplier_id=SUPPLIER_ID,
                subject=item["subject"],
                body=item["body"],
            )
            db.add(email)
            await db.flush()

            decision = await resolve_email(
                db=db,
                email=email,
            )

            print("Expected intent:", item["expected_intent"])
            print("Actual intent:", email.intent_status)
            print("Confidence score:", email.intent_confidence)
            if decision is None:
                print("Decision: None (no dispute created)")
            else:
                print("Decision:", decision)

        # ---- FINAL STATE ----
        disputes = (await db.execute(select(Dispute))).scalars().all()

        print("\n=== FINAL STATE ===")
        print("Total disputes:", len(disputes))
        for d in disputes:
            summary_preview = d.summary[:80] if d.summary else "<no summary>"
            print("-", d.id, summary_preview)


if __name__ == "__main__":
    asyncio.run(run())
