from googleapiclient.errors import HttpError
from dispute_resolution.utils.logging import logger
import base64
import re
from email.message import EmailMessage


def build_reply_subject(original_subject: str) -> str:
    """
    Build an idempotent reply subject.
    Gmail-safe: subject will NEVER grow across replies.
    """

    base = original_subject.strip()

    # Remove existing Re:
    base = re.sub(r"^re:\s*", "", base, flags=re.IGNORECASE)

    # Remove existing clarification markers
    base = re.sub(
        r"\s*\[Clarification Required\]|\s*—\s*Clarification Required",
        "",
        base,
        flags=re.IGNORECASE,
    )

    return f"Re: {base} [Clarification Required]"


def send_reply(
    *,
    service,
    to: str,
    subject: str,
    body: str,
    in_reply_to: str,
    thread_id: str,
):
    """
    Sends a system-generated reply that is GUARANTEED
    to stay in the same Gmail thread.
    """

    if not in_reply_to:
        raise ValueError("in_reply_to (root_gmail_message_id) is required")

    if not thread_id:
        raise ValueError("thread_id is required to preserve Gmail threading")

    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message["In-Reply-To"] = in_reply_to
    message["References"] = in_reply_to

    # Mark as system-generated (optional but useful)
    message["X-DR-SYSTEM"] = "clarification"

    message.set_content(body)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    payload = {
        "raw": raw,
        "threadId": thread_id,  # 🔒 FORCE SAME THREAD
    }

    try:
        service.users().messages().send(
            userId="me",
            body=payload,
        ).execute()
    except HttpError:
        logger.exception("Failed to send clarification reply")
        raise
