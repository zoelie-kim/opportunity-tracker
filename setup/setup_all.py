"""One-time Notion API setup: create or update jobs, programs, and events database schemas."""
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

TOKEN = os.environ["NOTION_TOKEN"]
JOBS_DB = os.environ["NOTION_DATABASE_ID"]
PROGRAMS_DB = os.environ["NOTION_PROGRAMS_DB_ID"]
EVENTS_DB = os.environ["NOTION_EVENTS_DB_ID"]

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def update_db(database_id, title, properties):
    response = httpx.patch(
        f"https://api.notion.com/v1/databases/{database_id}",
        headers=headers,
        json={"title": [{"text": {"content": title}}], "properties": properties},
        timeout=30.0
    )
    if response.status_code == 200:
        print(f"✅ {title} ready")
    else:
        print(f"❌ {title} failed: {response.status_code} {response.text}")

# --- JOBS DATABASE ---
update_db(JOBS_DB, "Jobs", {
    "Name": {"title": {}},
    "Role": {"rich_text": {}},
    "Type": {"select": {"options": [
        {"name": "Startup Job", "color": "blue"},
        {"name": "Big Tech", "color": "green"},
        {"name": "Other", "color": "gray"},
    ]}},
    "Stage": {"select": {"options": [
        {"name": "Seed"},
        {"name": "Series A-B"},
        {"name": "Series C+"},
        {"name": "Big Tech"},
        {"name": "Nonprofit / Research"},
    ]}},
    "Status": {"select": {"options": [
        {"name": "Preparing"},
        {"name": "Applied"},
        {"name": "In Contact"},
        {"name": "Accepted"},
        {"name": "Rejected"},
    ]}},
    "Priority": {"select": {"options": [
        {"name": "High"},
        {"name": "Medium"},
        {"name": "Low"},
    ]}},
    "Warm Intro": {"checkbox": {}},
    "Opens On": {"date": {}},
    "Deadline": {"date": {}},
    "Link": {"url": {}},
    "Source": {"rich_text": {}},
    "Date Added": {"date": {}},
    "Notes": {"rich_text": {}},
})

# --- PROGRAMS & FELLOWSHIPS DATABASE ---
update_db(PROGRAMS_DB, "Programs & Fellowships", {
    "Name": {"title": {}},
    "Type": {"select": {"options": [
        {"name": "Fellowship"},
        {"name": "AI Safety Program"},
        {"name": "Policy"},
        {"name": "Research"},
        {"name": "Internship Program"},
        {"name": "Other"},
    ]}},
    "Status": {"select": {"options": [
        {"name": "Preparing"},
        {"name": "Applied"},
        {"name": "In Contact"},
        {"name": "Accepted"},
        {"name": "Rejected"},
    ]}},
    "Priority": {"select": {"options": [
        {"name": "High"},
        {"name": "Medium"},
        {"name": "Low"},
    ]}},
    "Opens On": {"date": {}},
    "Deadline": {"date": {}},
    "Historical Pattern": {"rich_text": {}},
    "Alert Days Before": {"number": {}},
    "Link": {"url": {}},
    "Date Added": {"date": {}},
    "Notes": {"rich_text": {}},
})

# --- EVENTS DATABASE ---
update_db(EVENTS_DB, "Events", {
    "Name": {"title": {}},
    "Type": {"select": {"options": [
        {"name": "Job Fair"},
        {"name": "Networking"},
        {"name": "Conference"},
        {"name": "Career Fair"},
        {"name": "Info Session"},
        {"name": "Other"},
    ]}},
    "Date": {"date": {}},
    "Location": {"rich_text": {}},
    "RSVP Status": {"select": {"options": [
        {"name": "Interested"},
        {"name": "RSVP'd"},
        {"name": "Attended"},
        {"name": "Skipped"},
    ]}},
    "Link": {"url": {}},
    "Date Added": {"date": {}},
    "Notes": {"rich_text": {}},
})

print("\n🎯 All three databases are ready!")
