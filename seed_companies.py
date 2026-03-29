"""Batch-add company rows to the Notion companies database for scraping."""
import os
import httpx
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.environ["NOTION_TOKEN"]
COMPANIES_DB = os.environ["NOTION_COMPANIES_DB_ID"]
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}

# Companies to add
# Platform options: Greenhouse Board, Ashby, Workday, Career Page, LinkedIn
# For LinkedIn companies, URL is blank — they're covered by alerts not scraper
ADD = [
    ("Etched",      "Ashby",    "etched"),
    ("OpenAI",      "LinkedIn", ""),
    ("Google",      "LinkedIn", ""),
    ("Meta",        "LinkedIn", ""),
    ("Microsoft",   "LinkedIn", ""),
    ("Amazon",      "LinkedIn", ""),
    ("Apple",       "LinkedIn", ""),
    ("Netflix",     "LinkedIn", ""),
    ("Uber",        "LinkedIn", ""),
    ("Airbnb",      "LinkedIn", ""),
    ("TikTok",      "LinkedIn", ""),
    ("Stripe",      "LinkedIn", ""),
    ("Coinbase",    "LinkedIn", ""),
    ("Ramp",        "Ashby",    "ramp"),
    ("Databricks",  "Greenhouse Board", "databricks"),
    ("Neuralink",   "Ashby",    "neuralink"),
    ("Waymo",       "LinkedIn", ""),
    ("Twitch",      "LinkedIn", ""),
    ("LinkedIn",    "LinkedIn", ""),
    ("AWS",         "LinkedIn", ""),
]

print("Adding companies to Tracked Companies...\n")
added = 0
for name, platform, url in ADD:
    props = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Platform": {"select": {"name": platform}},
        "Active": {"checkbox": True},
    }
    if url:
        props["Careers URL"] = {"url": url}

    r = httpx.post(
        "https://api.notion.com/v1/pages",
        headers=headers,
        json={"parent": {"database_id": COMPANIES_DB}, "properties": props},
        timeout=30.0
    )
    status = "✅" if r.status_code == 200 else f"❌ {r.status_code}"
    print(f"  {status} {name} ({platform})")
    if r.status_code == 200:
        added += 1

print(f"\n✅ Added {added}/{len(ADD)} companies")
print("\nNext: manually uncheck Duolingo in your Tracked Companies Notion database (set Active = false)")
