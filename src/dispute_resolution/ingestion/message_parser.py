import base64
from dispute_resolution.utils.logging import logger


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data).decode(errors="ignore")


def _extract_text(payload: dict) -> str:
    # Single-part plain text
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data")
        if data:
            return _decode(data)

    # Multipart
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data")
            if data:
                return _decode(data)

    return ""


def parse_gmail_message(message: dict) -> dict:
    payload = message.get("payload", {})
    headers = payload.get("headers", [])

    subject = next(
        (h["value"] for h in headers if h["name"].lower() == "subject"),
        "(no subject)",
    )
    sender = next(
        (h["value"] for h in headers if h["name"].lower() == "from"),
        "(unknown sender)",
    )

    body = _extract_text(payload)
    body = "\n".join(line.strip() for line in body.splitlines() if line.strip())

    logger.info(f"Parsed email | From: {sender} | Subject: {subject[:60]}")

    return {
        "gmail_message_id": message["id"],
        "sender": sender,
        "subject": subject,
        "body": body,
    }
