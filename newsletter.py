"""
Weekly HTML email: new Notion roles from the last 7 days, program reminder lines from
alert_log.txt, and a “system health” block from error_monitor (recent log failures).
"""
import os
import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, datetime, timedelta
from dotenv import load_dotenv

from error_monitor import build_weekly_health_html

load_dotenv()

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

def get_jobs_from_past_7_days():
    """Query jobs added in the last 7 days"""
    seven_days_ago = (date.today() - timedelta(days=6)).isoformat()  # Last 7 days inclusive
    
    r = httpx.post(
        f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
        headers=notion_headers,
        json={
            "page_size": 100,
            "filter": {
                "property": "Date Added",
                "date": {
                    "on_or_after": seven_days_ago
                }
            }
        },
        timeout=30.0
    )
    return r.json().get("results", [])

def parse_text(rich_text_array):
    """Extract plain text from Notion rich_text array"""
    if not rich_text_array:
        return ""
    return "".join([item.get("plain_text", "") for item in rich_text_array])

def parse_date(date_obj):
    """Extract date from Notion date object"""
    if not date_obj or not date_obj.get("start"):
        return None
    return date_obj.get("start")

def read_alert_log():
    """Read alerts from the past 7 days from alert_log.txt"""
    alerts = []
    try:
        with open("alert_log.txt", "r") as f:
            lines = f.readlines()
        
        seven_days_ago = date.today() - timedelta(days=6)
        for line in lines:
            try:
                parts = line.strip().split(" | ")
                if len(parts) >= 3:
                    alert_date_str = parts[0]
                    alert_date = datetime.strptime(alert_date_str, "%Y-%m-%d").date()
                    if alert_date >= seven_days_ago:
                        program_name = parts[1]
                        alert_text = parts[2]
                        alerts.append({
                            "date": alert_date,
                            "program": program_name,
                            "text": alert_text
                        })
            except:
                continue
    except FileNotFoundError:
        pass
    
    return sorted(alerts, key=lambda x: x["date"], reverse=True)

def format_html(jobs, alerts, health_html: str):
    """Generate HTML for newsletter."""
    
    week_start = (date.today() - timedelta(days=6)).strftime("%b %d")
    week_end = date.today().strftime("%b %d, %Y")
    
    # Jobs section
    jobs_html = ""
    if jobs:
        jobs_html = '<section style="margin-bottom: 40px;">'
        jobs_html += f'<h2 style="color: #1a1a1a; border-bottom: 2px solid #007bff; padding-bottom: 10px;">📌 New Roles ({len(jobs)})</h2>'
        
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
    
    # Alerts section
    alerts_html = ""
    if alerts:
        alerts_html = '<section style="margin-bottom: 40px;">'
        alerts_html += f'<h2 style="color: #d9534f; border-bottom: 2px solid #d9534f; padding-bottom: 10px;">⏰ Reminder Alerts ({len(alerts)})</h2>'
        
        for alert in alerts:
            alerts_html += f'''
            <div style="margin: 12px 0; padding: 10px; background-color: #fff3cd; border-left: 4px solid #ffc107;">
                <p style="margin: 0; color: #333;"><strong>{alert["program"]}</strong></p>
                <p style="margin: 5px 0 0 0; color: #666; font-size: 13px;">{alert["text"]}</p>
            </div>
            '''
        
        alerts_html += '</section>'
    
    # Full email template
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
            <p style="color: #666; font-size: 14px;">Week of {week_start} – {week_end}</p>
            
            {health_html}
            {jobs_html}
            {alerts_html}
            
            <p style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #888; font-size: 12px;">
                Your Opportunity Tracker • Automated on Sundays
            </p>
        </div>
    </body>
    </html>
    '''
    
    return html

def main():
    print("\n📊 Generating Sunday newsletter...\n")

    health_html, err_count = build_weekly_health_html()
    jobs = get_jobs_from_past_7_days()
    alerts = read_alert_log()

    print(f"  Health: {err_count} error line(s) in logs (past 7 days)")
    print(f"  Found {len(jobs)} new roles")
    print(f"  Found {len(alerts)} reminder alerts")

    if not jobs and not alerts and err_count == 0:
        print("\n  ⚠️ No jobs, alerts, or log issues — skipping newsletter\n")
        return

    html = format_html(jobs, alerts, health_html)
    send_email("Weekly Digest", html)
    print()

if __name__ == "__main__":
    main()
