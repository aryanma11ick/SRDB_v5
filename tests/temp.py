import asyncio
from sqlalchemy import select
from dispute_resolution.database import AsyncSessionLocal
from dispute_resolution.models import Dispute
from dispute_resolution.services.embedding_service import embed_email


DISPUTE_ID = "1889bfed-2ec2-46f2-83e4-735a07144f7d"


async def embed_summary():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Dispute).where(Dispute.id == DISPUTE_ID)
        )
        dispute = result.scalar_one()

        embedding = embed_email(
            subject="Dispute summary",
            body=dispute.summary
        )

        dispute.summary_embedding = embedding
        await db.commit()

        print("✅ Dispute summary embedded")


asyncio.run(embed_summary())