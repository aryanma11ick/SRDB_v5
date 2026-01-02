from googleapiclient.errors import HttpError
from dispute_resolution.utils.logging import logger
import base64
from email.message import EmailMessage


def send_reply(
    *,
    service,
    to: str,
    subject: str,
    body: str,
    in_reply_to: str,
    thread_id: str | None = None,
):
    """
    Sends a clarification reply in the same Gmail thread.
    Gmail automatically handles 'Re:'.
    """

    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject               # ❌ NO manual "Re:"
    message["In-Reply-To"] = in_reply_to
    message["References"] = in_reply_to

    # 🔒 Mark as system-generated
    message["X-DR-SYSTEM"] = "clarification"

    message.set_content(body)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    payload = {"raw": raw}

    # Only include threadId if it exists
    if thread_id:
        payload["threadId"] = thread_id

    try:
        service.users().messages().send(
            userId="me",
            body=payload,
        ).execute()
    except HttpError:
        logger.exception("Failed to send clarification reply")
        raise
    