import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_FILE = Path("token.pickle")

REQUIRED_LABELS = {
    "Processed": {
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    },
    "Dispute": {
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    },
    "Not_Dispute": {
        "labelListVisibility": "labelShow",
        "messageListVisibility": "hide",
    },
    "Needs_Clarification": {
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    },
}


def get_gmail_service():
    """
    Load Gmail credentials and return an authenticated Gmail API client.
    """
    if not TOKEN_FILE.exists():
        raise RuntimeError(
            "token.pickle not found. Run scripts/google_auth.py first to generate it."
        )

    with open(TOKEN_FILE, "rb") as f:
        creds = pickle.load(f)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build("gmail", "v1", credentials=creds)


def fetch_and_print_one_email():
    """
    Fetch a single email and print basic metadata.
    """
    service = get_gmail_service()

    result = service.users().messages().list(userId="me", maxResults=1).execute()
    messages = result.get("messages", [])
    if not messages:
        print("No emails found.")
        return

    msg_id = messages[0]["id"]
    msg = service.users().messages().get(
        userId="me",
        id=msg_id,
        format="full",
    ).execute()

    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    subject = headers.get("Subject", "(no subject)")
    sender = headers.get("From", "(unknown sender)")

    print("--- EMAIL FETCHED ---")
    print("From   :", sender)
    print("Subject:", subject)
    print("Message ID:", msg_id)


def ensure_labels(service) -> dict[str, str]:
    """
    Ensure required Gmail labels exist.
    Returns: {label_name: label_id}
    """
    existing = service.users().labels().list(userId="me").execute()
    label_map = {l["name"]: l["id"] for l in existing.get("labels", [])}

    for name, config in REQUIRED_LABELS.items():
        if name not in label_map:
            label = (
                service.users()
                .labels()
                .create(
                    userId="me",
                    body={
                        "name": name,
                        "type": "user",
                        **config,
                    },
                )
                .execute()
            )
            label_map[name] = label["id"]

    return label_map

def modify_message_labels(
    service,
    *,
    message_id: str,
    add: list[str],
    remove: list[str] | None = None,
):
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={
            "addLabelIds": add,
            "removeLabelIds": remove or [],
        },
    ).execute()