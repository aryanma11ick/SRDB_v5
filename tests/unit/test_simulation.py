import asyncio
from sqlalchemy import select
from dispute_resolution.database import AsyncSessionLocal
from dispute_resolution.models import Email, Dispute
from dispute_resolution.services.embedding_service import embed_email
from dispute_resolution.services.dispute_resolution_service import resolve_email
from dispute_resolution.services.vector_search_service import find_candidate_disputes

TEST_EMAILS = [
    # Dispute A: Overcharge INV-9123
    {
        "subject": "Overcharge identified on Invoice INV-9123",
        "body": "We noticed an overcharge on Invoice INV-9123. Amount exceeds PO.",
    },
    {
        "subject": "Follow-up on Invoice INV-9123",
        "body": "Following up on the overcharge for Invoice INV-9123.",
    },

    # Dispute B: Short payment INV-8812
    {
        "subject": "Short payment on Invoice INV-8812",
        "body": "Payment received is INR 2,500 short for Invoice INV-8812.",
    },
    {
        "subject": "Reminder: Short payment INV-8812",
        "body": "Reminder regarding pending amount for Invoice INV-8812.",
    },

    # Ambiguous (should create NEW)
    {
        "subject": "Pending clarification",
        "body": "Please clarify the discrepancy on the recent invoice.",
    },
]


async def run():
    async with AsyncSessionLocal() as db:
        for i, item in enumerate(TEST_EMAILS, start=1):
            print(f"\n--- Processing email {i} ---")

            email = Email(
                supplier_id='45917f45-baa5-4b53-8e7b-5c504b74f85e',  # put your test supplier UUID here
                subject=item["subject"],
                body=item["body"],
                embedding=embed_email(item["subject"], item["body"]),
            )
            db.add(email)
            await db.flush()

            candidates = await find_candidate_disputes(
                db=db,
                supplier_id=email.supplier_id,
                email_embedding=email.embedding,
                k=3,
            )

            decision = await resolve_email(
                db=db,
                email=email,
                candidate_disputes=candidates,
            )

            print("Decision:", decision)

        # Summary
        disputes = (await db.execute(select(Dispute))).scalars().all()
        print("\n=== FINAL STATE ===")
        print("Total disputes:", len(disputes))
        for d in disputes:
            print("-", d.id, d.summary[:60])


if __name__ == "__main__":
    asyncio.run(run())
