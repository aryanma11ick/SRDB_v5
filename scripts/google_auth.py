from google_auth_oauthlib.flow import InstalledAppFlow
import pickle
from pathlib import Path

# Read + modify (labels, mark read later). No send/delete.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

CREDENTIALS_FILE = Path("credentials.json")
TOKEN_FILE = Path("token.pickle")


def main():
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            "credentials.json not found. Download it from Google Cloud Console."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        SCOPES
    )

    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)

    print("✅ Gmail authentication successful")
    print(f"✅ Token saved to {TOKEN_FILE}")
    print("➡️ You can now run the ingestion poller")


if __name__ == "__main__":
    main()
