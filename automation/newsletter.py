"""
Weekly HTML email: new Notion roles, program reminder lines from alert_log.txt, and log-based
system health. Content is scoped to *since the last successful digest* using task_log.json’s
``newsletter`` timestamp (written by check_missed_tasks after each send). If that is missing,
falls back to a rolling 7-day window.
"""
import json
import os
import sys
import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, datetime, time, timedelta
from pathlib import Path
from dotenv import load_dotenv

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
from paths import REPO_ROOT

load_dotenv(REPO_ROOT / ".env")

from error_monitor import build_weekly_health_html

TASK_LOG_PATH = REPO_ROOT / "task_log.json"

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
ALERT_EMAIL = os.environ["ALERT_EMAIL"]

notion_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}


def load_last_successful_digest_time() -> datetime | None:
    """ISO time from task_log ``newsletter`` — updated after each successful send from the scheduler."""
    if not TASK_LOG_PATH.is_file():
        return None
    try:
        with open(TASK_LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("newsletter")
        if not raw:
            return None
        s = str(raw).strip()
        if "T" in s:
            return datetime.fromisoformat(s)
        try:
            d = date.fromisoformat(s)
            return datetime.combine(d, time(23, 59, 59))
        except ValueError:
            return None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def digest_window_start_date(last_digest: datetime | None) -> date:
    """First calendar day to include for date-based fields (Notion Date Added, alert_log dates)."""
    if last_digest is None:
        return date.today() - timedelta(days=6)
    return last_digest.date() + timedelta(days=1)


def send_email(subject, body_html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[TRACKER] {subject}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = ALERT_EMAIL
    msg.attach(MIMEText(body_html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, ALERT_EMAIL, msg.as_string())
    print(f"  📧 Sent: {subject}")


def get_jobs_on_or_after(start: date):
    """Query Notion for jobs whose Date Added is on or after ``start`` (paginated)."""
    results = []
    cursor = None
    start_s = start.isoformat()
    while True:
        body = {
            "page_size": 100,
            "filter": {
                "property": "Date Added",
                "date": {"on_or_after": start_s},
            },
        }
        if cursor:
            body["start_cursor"] = cursor
        r = httpx.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers=notion_headers,
            json=body,
            timeout=60.0,
        )
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return results


def parse_text(rich_text_array):
    if not rich_text_array:
        return ""
    return "".join([item.get("plain_text", "") for item in rich_text_array])


def parse_date(date_obj):
    if not date_obj or not date_obj.get("start"):
        return None
    return date_obj.get("start")


def read_alert_log_on_or_after(start: date):
    """Reminder lines in alert_log.txt whose date is >= ``start``."""
    alerts = []
    path = REPO_ROOT / "alert_log.txt"
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            try:
                parts = line.strip().split(" | ")
                if len(parts) >= 3:
                    alert_date = datetime.strptime(parts[0], "%Y-%m-%d").date()
                    if alert_date >= start:
                        alerts.append({
                            "date": alert_date,
                            "program": parts[1],
                            "text": parts[2],
                        })
            except Exception:
                continue
    except FileNotFoundError:
        pass

    return sorted(alerts, key=lambda x: x["date"], reverse=True)


def format_html(
    jobs,
    alerts,
    health_html: str,
    *,
    start: date,
    end: date,
    using_last_digest: bool,
):
    """Generate HTML (always includes health, new roles, reminder alerts sections)."""

    period_line = f"{start.strftime('%b %d, %Y')} – {end.strftime('%b %d, %Y')}"
    scope_note = (
        f"Items since the previous digest (dates on or after <strong>{start.isoformat()}</strong>)."
        if using_last_digest
        else f"First digest or no prior send in <code>task_log.json</code> — using a rolling window from <strong>{start.isoformat()}</strong>."
    )

    nj = len(jobs)
    if jobs:
        jobs_html = '<section style="margin-bottom: 28px;">'
        jobs_html += f'<h2 style="color: #1a1a1a; border-bottom: 2px solid #007bff; padding-bottom: 10px;">📌 New roles ({nj})</h2>'
        for job in jobs:
            props = job.get("properties", {})
            company = parse_text(props.get("Name", {}).get("title", []))
            role = parse_text(props.get("Role", {}).get("rich_text", []))
            link = props.get("Link", {}).get("url")
            source = parse_text(props.get("Source", {}).get("rich_text", []))
            notes = parse_text(props.get("Notes", {}).get("rich_text", []))
            date_added = parse_date(props.get("Date Added", {}).get("date"))
            jobs_html += f'''
            <div style="margin: 15px 0; padding: 12px; background-color: #f8f9fa; border-left: 4px solid #007bff;">
                <h3 style="margin: 0 0 5px 0; color: #1a1a1a;">{company}</h3>
                <p style="margin: 3px 0; color: #333;"><strong>{role}</strong></p>
                {f'<p style="margin: 3px 0; color: #666; font-size: 13px;">{notes}</p>' if notes else ''}
                <p style="margin: 8px 0 0 0; font-size: 12px; color: #888;">
                    <em>{source}</em> — {date_added}
                    {f'<a href="{link}" style="color: #007bff; text-decoration: none; margin-left: 10px;">→ View</a>' if link else ''}
                </p>
            </div>
            '''
        jobs_html += '</section>'
    else:
        jobs_html = (
            '<section style="margin-bottom: 28px;">'
            '<h2 style="color: #1a1a1a; border-bottom: 2px solid #007bff; padding-bottom: 10px;">📌 New roles (0)</h2>'
            f'<p style="margin: 0; color: #666; font-size: 14px;">No roles with <strong>Date Added</strong> on or after {start.isoformat()}.</p>'
            '</section>'
        )

    na = len(alerts)
    if alerts:
        alerts_html = '<section style="margin-bottom: 28px;">'
        alerts_html += f'<h2 style="color: #d9534f; border-bottom: 2px solid #d9534f; padding-bottom: 10px;">⏰ Reminder alerts ({na})</h2>'
        for alert in alerts:
            alerts_html += f'''
            <div style="margin: 12px 0; padding: 10px; background-color: #fff3cd; border-left: 4px solid #ffc107;">
                <p style="margin: 0; color: #333;"><strong>{alert["program"]}</strong></p>
                <p style="margin: 5px 0 0 0; color: #666; font-size: 13px;">{alert["text"]}</p>
            </div>
            '''
        alerts_html += '</section>'
    else:
        alerts_html = (
            '<section style="margin-bottom: 28px;">'
            '<h2 style="color: #d9534f; border-bottom: 2px solid #d9534f; padding-bottom: 10px;">⏰ Reminder alerts (0)</h2>'
            f'<p style="margin: 0; color: #666; font-size: 14px;">No reminder lines in <code>alert_log.txt</code> on or after {start.isoformat()}.</p>'
            '</section>'
        )

    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; color: #333; line-height: 1.6; }}
            a {{ color: #007bff; text-decoration: none; }}
        </style>
    </head>
    <body style="background-color: #f5f5f5; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">

            <h1 style="color: #1a1a1a; margin-top: 0;">📊 Weekly Opportunity Digest</h1>
            <p style="color: #333; font-size: 14px;"><strong>Period:</strong> {period_line}</p>
            <p style="color: #666; font-size: 13px; margin-top: 8px;">{scope_note}</p>

            {health_html}
            {jobs_html}
            {alerts_html}

            <p style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #888; font-size: 12px;">
                Your Opportunity Tracker • Automated digest
            </p>
        </div>
    </body>
    </html>
    '''

    return html


def main():
    print("\n📊 Generating weekly digest email...\n")

    last_digest = load_last_successful_digest_time()
    start = digest_window_start_date(last_digest)
    end = date.today()
    using_last = last_digest is not None

    health_html, err_count = build_weekly_health_html(since=last_digest)
    jobs = get_jobs_on_or_after(start)
    alerts = read_alert_log_on_or_after(start)

    print(f"  Last digest: {last_digest.isoformat(sep=' ') if last_digest else '(none — use rolling window)'}")
    print(f"  Window: {start.isoformat()} through {end.isoformat()} (jobs & alerts by date ≥ start)")
    print(f"  Health: {err_count} error line(s) in logs ({'since last digest' if last_digest else 'past 7 days'})")
    print(f"  Found {len(jobs)} new roles")
    print(f"  Found {len(alerts)} reminder alerts")

    html = format_html(
        jobs,
        alerts,
        health_html,
        start=start,
        end=end,
        using_last_digest=using_last,
    )
    send_email("Weekly Digest", html)
    print()


if __name__ == "__main__":
    main()
