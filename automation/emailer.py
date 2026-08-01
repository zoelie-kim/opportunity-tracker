"""
Shared outbound email for the tracker, sent through Resend.

Uses the same Resend account as the `newsletter` project (verified sender domain
zoeliekim.com), so there is one place to rotate the key and one sending reputation
to look after. Talks to the REST endpoint directly with httpx rather than pulling
in the `resend` SDK — the whole integration is a single POST.
"""

import os

import httpx

RESEND_ENDPOINT = "https://api.resend.com/emails"
DEFAULT_FROM = "Opportunity Tracker <opportunities@zoeliekim.com>"
SUBJECT_PREFIX = "[TRACKER] "


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is missing from .env — cannot send email.")
    return value


def send_email(subject: str, body_html: str) -> str:
    """Send one HTML email and return the Resend message id. Raises on failure."""
    api_key = _require("RESEND_API_KEY")
    to_address = _require("ALERT_EMAIL")
    from_address = os.environ.get("RESEND_FROM") or DEFAULT_FROM

    response = httpx.post(
        RESEND_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": from_address,
            "to": [to_address],
            "subject": f"{SUBJECT_PREFIX}{subject}",
            "html": body_html,
        },
        timeout=30.0,
    )

    if response.status_code >= 400:
        # Surface Resend's own message (bad key, unverified domain, invalid recipient)
        # so error_monitor's log scan reports something actionable.
        raise RuntimeError(
            f"Resend rejected the send ({response.status_code}): {response.text}"
        )

    message_id = response.json().get("id", "unknown")
    print(f"  📧 Sent: {subject}")
    return message_id


if __name__ == "__main__":
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    send_email(
        "Resend smoke test",
        "<p>If you are reading this, opportunity-tracker is sending through Resend.</p>",
    )
