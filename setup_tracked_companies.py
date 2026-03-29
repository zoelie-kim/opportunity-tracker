"""Configure which companies appear in the companies database for career-page scraping."""
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["NOTION_TOKEN"]
COMPANIES_DB = os.environ["NOTION_COMPANIES_DB_ID"]

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# Update schema
r = httpx.patch(
    f"https://api.notion.com/v1/databases/{COMPANIES_DB}",
    headers=headers,
    json={
        "title": [{"text": {"content": "Tracked Companies"}}],
        "properties": {
            "Name": {"title": {}},
            "Platform": {
                "select": {
                    "options": [
                        {"name": "Greenhouse Board", "color": "green"},
                        {"name": "Career Page", "color": "blue"},
                        {"name": "Workday", "color": "purple"},
                    ]
                }
            },
            "Careers URL": {"url": {}},
            "Active": {"checkbox": {}},
            "Notes": {"rich_text": {}},
            "Last Checked": {"date": {}},
        }
    },
    timeout=30.0
)

if r.status_code == 200:
    print("✅ Tracked Companies schema updated")
else:
    print(f"❌ {r.status_code} {r.text}")

# Seed companies
COMPANIES = [
    # Greenhouse Board — URL field is just the board ID
    ("Glean",       "Greenhouse Board", "gleanwork"),
    ("Scale AI",    "Greenhouse Board", "scaleai"),
    ("Brex",        "Greenhouse Board", "brex"),
    ("Notion",      "Greenhouse Board", "notion"),
    ("Figma",       "Greenhouse Board", "figma"),
    ("Discord",     "Greenhouse Board", "discord"),
    ("Duolingo",    "Greenhouse Board", "duolingo"),
    # Career Page — URL field is full careers page URL
    ("Anthropic",   "Career Page", "https://www.anthropic.com/careers"),
    ("Cursor",      "Career Page", "https://www.cursor.com/careers"),
    ("Perplexity",  "Career Page", "https://www.perplexity.ai/careers"),
    ("Cohere",      "Career Page", "https://cohere.com/careers"),
    ("Rippling",    "Career Page", "https://www.rippling.com/careers"),
    # Workday — URL field is full Workday base URL
    ("Salesforce",  "Workday", "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site"),
]

print("\nSeeding companies...")
for name, platform, url in COMPANIES:
    r = httpx.post(
        "https://api.notion.com/v1/pages",
        headers=headers,
        json={
            "parent": {"database_id": COMPANIES_DB},
            "properties": {
                "Name": {"title": [{"text": {"content": name}}]},
                "Platform": {"select": {"name": platform}},
                "Careers URL": {"url": url},
                "Active": {"checkbox": True},
            }
        },
        timeout=30.0
    )
    print(f"  {'✅' if r.status_code == 200 else '❌'} {name} ({platform})")

print("\n✅ Done! Manage companies in your Tracked Companies Notion database.")
print("   Add companies anytime — no code needed.")
