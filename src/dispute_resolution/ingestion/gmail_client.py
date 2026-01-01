import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_FILE = Path("token.pickle")

LABELS = {
    "processed": "Processed",
    "dispute": "Dispute",
    "not_dispute": "Not Dispute",
    "ambiguous": "Needs Clarification",
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


def ensure_label(service, label_name: str) -> str:
    """
    Ensure a Gmail label exists. Returns labelId.
    """
    labels = service.users().labels().list(userId="me").execute()["labels"]

    for label in labels:
        if label["name"] == label_name:
            return label["id"]

    label = service.users().labels().create(
        userId="me",
        body={
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
    ).execute()

    return label["id"]

def add_labels(service, message_id: str, label_ids: list[str]) -> None:
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": label_ids},
    ).execute()