"""CLI helper to insert a single job or program entry into Notion with structured fields."""
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv
from datetime import date

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
JOBS_DB = os.environ["NOTION_DATABASE_ID"]
PROGRAMS_DB = os.environ["NOTION_PROGRAMS_DB_ID"]

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def prompt(label, options=None, optional=False):
    if options:
        print(f"\n{label}:")
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        while True:
            val = input("Pick a number (or press Enter to skip): " if optional else "Pick a number: ").strip()
            if optional and val == "":
                return None
            if val.isdigit() and 1 <= int(val) <= len(options):
                return options[int(val) - 1]
            print("Invalid choice, try again.")
    else:
        suffix = " (optional, press Enter to skip)" if optional else ""
        val = input(f"\n{label}{suffix}: ").strip()
        return val if val else None

def prompt_date(label, optional=True):
    suffix = " (optional, press Enter to skip)" if optional else ""
    while True:
        val = input(f"\n{label} YYYY-MM-DD{suffix}: ").strip()
        if optional and val == "":
            return None
        try:
            date.fromisoformat(val)
            return val
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD (e.g. 2026-09-01)")

print("\n🎯 Add New Opportunity\n" + "="*30)

# First choice — which database
db_type = prompt("Where do you want to add this?", ["Job", "Program / Fellowship"])

if db_type == "Job":
    database_id = JOBS_DB
    print("\n── JOB DETAILS ──")
    name        = prompt("Company name")
    role        = prompt("Role title")
    type_       = prompt("Type", ["Startup Job", "Big Tech", "Other"])
    stage       = prompt("Stage", ["Seed", "Series A-B", "Series C+", "Big Tech", "Nonprofit / Research"], optional=True)
    priority    = prompt("Priority", ["High", "Medium", "Low"])
    status      = prompt("Status", ["Preparing", "Applied", "In Contact", "Accepted", "Rejected"])
    warm_intro  = prompt("Warm intro?", ["Yes", "No"])
    link        = prompt("Link", optional=True)
    opens_on    = prompt_date("Opens On", optional=True)
    deadline    = prompt_date("Deadline", optional=True)
    source      = prompt("Where did you find this?", optional=True)
    notes       = prompt("Notes", optional=True)

    properties = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Role": {"rich_text": [{"text": {"content": role or ""}}]},
        "Type": {"select": {"name": type_}},
        "Priority": {"select": {"name": priority}},
        "Status": {"select": {"name": status}},
        "Warm Intro": {"checkbox": warm_intro == "Yes"},
        "Date Added": {"date": {"start": date.today().isoformat()}},
    }
    if stage:
        properties["Stage"] = {"select": {"name": stage}}
    if link:
        properties["Link"] = {"url": link}
    if opens_on:
        properties["Opens On"] = {"date": {"start": opens_on}}
    if deadline:
        properties["Deadline"] = {"date": {"start": deadline}}
    if source:
        properties["Source"] = {"rich_text": [{"text": {"content": source}}]}
    if notes:
        properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

else:
    database_id = PROGRAMS_DB
    print("\n── PROGRAM DETAILS ──")
    name        = prompt("Program / Fellowship name")
    type_       = prompt("Type", ["Fellowship", "AI Safety Program", "Policy", "Research", "Internship Program", "Other"])
    priority    = prompt("Priority", ["High", "Medium", "Low"])
    status      = prompt("Status", ["Preparing", "Applied", "In Contact", "Accepted", "Rejected"])
    link        = prompt("Link", optional=True)
    opens_on    = prompt_date("Opens On (or historical open date)", optional=True)
    deadline    = prompt_date("Deadline (or historical deadline)", optional=True)
    alert_days  = input("\nAlert X days before it opens (e.g. 14, press Enter to skip): ").strip()
    pattern     = prompt("Historical pattern (e.g. 'Opens every September')", optional=True)
    notes       = prompt("Notes", optional=True)

    properties = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Type": {"select": {"name": type_}},
        "Priority": {"select": {"name": priority}},
        "Status": {"select": {"name": status}},
        "Date Added": {"date": {"start": date.today().isoformat()}},
    }
    if link:
        properties["Link"] = {"url": link}
    if opens_on:
        properties["Opens On"] = {"date": {"start": opens_on}}
    if deadline:
        properties["Deadline"] = {"date": {"start": deadline}}
    if alert_days.isdigit():
        properties["Alert Days Before"] = {"number": int(alert_days)}
    if pattern:
        properties["Historical Pattern"] = {"rich_text": [{"text": {"content": pattern}}]}
    if notes:
        properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

# Add to Notion
response = httpx.post(
    "https://api.notion.com/v1/pages",
    headers=headers,
    json={"parent": {"database_id": database_id}, "properties": properties},
    timeout=30.0
)

if response.status_code == 200:
    print(f"\n✅ Added '{name}' to your tracker!")
else:
    print(f"\n❌ Error: {response.status_code}")
    print(response.text)
