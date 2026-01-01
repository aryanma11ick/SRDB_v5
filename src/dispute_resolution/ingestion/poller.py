import asyncio
from dispute_resolution.database import AsyncSessionLocal
from dispute_resolution.ingestion.gmail_client import get_gmail_service
from dispute_resolution.ingestion.processor import process_message
from dispute_resolution.utils.logging import logger


DRY_RUN = False

GMAIL_QUERY = "is:unread newer_than:3d"


async def _poll_async(max_results: int = 10) -> None:
    """
    Fetch recent Gmail messages and pass them to the processor.
    """
    service = get_gmail_service()

    result = service.users().messages().list(
        userId="me",
        q=GMAIL_QUERY,
        maxResults=max_results,
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        logger.info("No new emails found")
        return

    logger.info(f"Fetched {len(messages)} Gmail messages")

    async with AsyncSessionLocal() as db:
        for m in messages:
            msg = service.users().messages().get(
                userId="me",
                id=m["id"],
                format="full",
            ).execute()

            if DRY_RUN:
                logger.info(
                    f"[DRY RUN] Processing email "
                    f"ID={m['id']} | "
                    f"Snippet={msg.get('snippet', '')[:80]}"
                )

            await process_message(db, service, msg)


def poll(max_results: int = 10) -> None:
    asyncio.run(_poll_async(max_results))


def main():
    """
    Minimal CLI entrypoint:
    python -m dispute_resolution.ingestion.poller --max-results 5
    """
    import argparse

    parser = argparse.ArgumentParser(description="Poll Gmail and ingest messages.")
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="How many recent messages to fetch (default: 10)",
    )
    args = parser.parse_args()

    poll(max_results=args.max_results)


if __name__ == "__main__":
    main()
