"""Create youtube_token.json for automatic YouTube uploads.

Run once on the machine that owns the YouTube channel:
    python backend/scripts/youtube_oauth_setup.py

Before running, download an OAuth client JSON from Google Cloud Console and save
it at the path configured by YOUTUBE_CLIENT_SECRETS_FILE.
"""

from pathlib import Path
import sys

from google_auth_oauthlib.flow import InstalledAppFlow


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import settings  # noqa: E402


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT_DIR.parent / path


def main() -> None:
    secrets_path = resolve_project_path(settings.YOUTUBE_CLIENT_SECRETS_FILE)
    token_path = resolve_project_path(settings.YOUTUBE_TOKEN_FILE)

    if not secrets_path.exists():
        raise SystemExit(
            f"OAuth client secret file not found: {secrets_path}\n"
            "Create a Google Cloud OAuth Desktop app, download the JSON, and "
            "set YOUTUBE_CLIENT_SECRETS_FILE to that file."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
    credentials = flow.run_local_server(port=0)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    print(f"Saved YouTube OAuth token to: {token_path}")


if __name__ == "__main__":
    main()
