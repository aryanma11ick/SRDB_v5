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
    thread_id: str | None = None,
    in_reply_to: str,
):
    """
    Sends a reply in the same Gmail thread.
    """
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = f"Re: {subject}"
    message["In-Reply-To"] = in_reply_to
    message["References"] = in_reply_to
    message.set_content(body)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    try:
        service.users().messages().send(
            userId="me",
            body={
                "raw": raw,
                "threadId": thread_id,
            },
        ).execute()
    except HttpError as e:
        logger.error("Failed to send clarification reply")
        raise
