import os
import smtplib
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
PROGRAMS_DB = os.environ["NOTION_PROGRAMS_DB_ID"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
ALERT_EMAIL = os.environ["ALERT_EMAIL"]

notion_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

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

def log_alert(program_name, alert_text):
    """Append alert to alert_log.txt for newsletter inclusion"""
    try:
        with open("alert_log.txt", "a") as f:
            f.write(f"{date.today().isoformat()} | {program_name} | {alert_text}\n")
    except Exception as e:
        print(f"  ⚠️ Failed to log alert: {e}")

def get_programs():
    r = httpx.post(
        f"https://api.notion.com/v1/databases/{PROGRAMS_DB}/query",
        headers=notion_headers,
        json={"page_size": 100},
        timeout=30.0
    )
    return r.json().get("results", [])

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except:
        return None

def format_date(d):
    return d.strftime("%B %d, %Y")

def days_until(d):
    return (d - date.today()).days

today = date.today()
programs = get_programs()
alerts_sent = 0
checked = 0

print(f"\n🔔 Countdown alerts — {today}\n")

for program in programs:
    props = program.get("properties", {})

    name_parts = props.get("Name", {}).get("title", [])
    name = name_parts[0].get("text", {}).get("content", "Unknown") if name_parts else "Unknown"

    opens_raw = props.get("Opens On", {}).get("date")
    deadline_raw = props.get("Deadline", {}).get("date")
    alert_days_raw = props.get("Alert Days Before", {}).get("number")
    notes_parts = props.get("Notes", {}).get("rich_text", [])
    notes = notes_parts[0].get("text", {}).get("content", "") if notes_parts else ""

    opens_date = parse_date(opens_raw.get("start") if opens_raw else None)
    deadline_date = parse_date(deadline_raw.get("start") if deadline_raw else None)
    alert_days = int(alert_days_raw) if alert_days_raw else 14

    checked += 1

    # Check Opens On date
    if opens_date:
        days = days_until(opens_date)

        # Alert X days before
        if days == alert_days:
            subject = f"⏰ Opens in {days} days: {name}"
            body = f"""
            <h2 style="color:#1a1a1a">⏰ Opening in {days} days</h2>
            <h3 style="color:#333">{name}</h3>
            <p><strong>Opens:</strong> {format_date(opens_date)}</p>
            {"<p><strong>Notes:</strong> " + notes + "</p>" if notes else ""}
            <p style="color:#888;font-size:12px">Sent by your Opportunity Tracker</p>
            """
            send_email(subject, body)
            log_alert(name, f"⏰ Opens in {days} days")
            alerts_sent += 1

        # Alert day it opens
        elif days == 0:
            subject = f"🚀 Opens TODAY: {name}"
            body = f"""
            <h2 style="color:#1a1a1a">🚀 Opens today!</h2>
            <h3 style="color:#333">{name}</h3>
            <p><strong>Opens:</strong> {format_date(opens_date)}</p>
            {"<p><strong>Notes:</strong> " + notes + "</p>" if notes else ""}
            <p style="color:#888;font-size:12px">Sent by your Opportunity Tracker</p>
            """
            send_email(subject, body)
            log_alert(name, "🚀 Opens TODAY")
            alerts_sent += 1

        # Also alert 1 day before (if alert_days isn't already 1)
        elif days == 1 and alert_days != 1:
            subject = f"⚡ Opens TOMORROW: {name}"
            body = f"""
            <h2 style="color:#1a1a1a">⚡ Opens tomorrow!</h2>
            <h3 style="color:#333">{name}</h3>
            <p><strong>Opens:</strong> {format_date(opens_date)}</p>
            {"<p><strong>Notes:</strong> " + notes + "</p>" if notes else ""}
            <p style="color:#888;font-size:12px">Sent by your Opportunity Tracker</p>
            """
            send_email(subject, body)
            log_alert(name, "⚡ Opens TOMORROW")
            alerts_sent += 1

    # Check Deadline date
    if deadline_date:
        days = days_until(deadline_date)

        if days == alert_days:
            subject = f"⏰ Deadline in {days} days: {name}"
            body = f"""
            <h2 style="color:#c0392b">⏰ Deadline in {days} days</h2>
            <h3 style="color:#333">{name}</h3>
            <p><strong>Deadline:</strong> {format_date(deadline_date)}</p>
            {"<p><strong>Notes:</strong> " + notes + "</p>" if notes else ""}
            <p style="color:#888;font-size:12px">Sent by your Opportunity Tracker</p>
            """
            send_email(subject, body)
            log_alert(name, f"⏰ Deadline in {days} days")
            alerts_sent += 1

        elif days == 1:
            subject = f"🚨 Deadline TOMORROW: {name}"
            body = f"""
            <h2 style="color:#c0392b">🚨 Deadline tomorrow!</h2>
            <h3 style="color:#333">{name}</h3>
            <p><strong>Deadline:</strong> {format_date(deadline_date)}</p>
            {"<p><strong>Notes:</strong> " + notes + "</p>" if notes else ""}
            <p style="color:#888;font-size:12px">Sent by your Opportunity Tracker</p>
            """
            send_email(subject, body)
            log_alert(name, "🚨 Deadline TOMORROW")
            alerts_sent += 1

        elif days == 0:
            subject = f"🚨 Deadline TODAY: {name}"
            body = f"""
            <h2 style="color:#c0392b">🚨 Deadline is TODAY!</h2>
            <h3 style="color:#333">{name}</h3>
            <p><strong>Deadline:</strong> {format_date(deadline_date)}</p>
            {"<p><strong>Notes:</strong> " + notes + "</p>" if notes else ""}
            <p style="color:#888;font-size:12px">Sent by your Opportunity Tracker</p>
            """
            send_email(subject, body)
            log_alert(name, "🚨 Deadline TODAY")
            alerts_sent += 1

print(f"Checked {checked} programs — {alerts_sent} alerts sent")
if alerts_sent == 0:
    print("No alerts due today")
