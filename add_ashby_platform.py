"""One-time Notion patch: add Ashby as a platform option on the companies database."""
import os
import httpx
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.environ["NOTION_TOKEN"]
COMPANIES_DB = os.environ["NOTION_COMPANIES_DB_ID"]
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}

# Add Ashby to Platform select options
r = httpx.patch(
    f"https://api.notion.com/v1/databases/{COMPANIES_DB}",
    headers=headers,
    json={"properties": {"Platform": {"select": {"options": [
        {"name": "Greenhouse Board"},
        {"name": "Ashby"},
        {"name": "Career Page"},
        {"name": "Workday"},
    ]}}}},
    timeout=30.0
)
print("✅ Ashby added to Platform options" if r.status_code == 200 else f"❌ {r.status_code}")

# Seed Ashby companies
COMPANIES = [
    ("Anthropic",  "anthropic"),
    ("Perplexity", "perplexity"),
    ("Cohere",     "cohere"),
    ("Harvey",     "harvey"),
]

print("\nAdding Ashby companies...")
for name, board_id in COMPANIES:
    r = httpx.post(
        "https://api.notion.com/v1/pages",
        headers=headers,
        json={
            "parent": {"database_id": COMPANIES_DB},
            "properties": {
                "Name": {"title": [{"text": {"content": name}}]},
                "Platform": {"select": {"name": "Ashby"}},
                "Careers URL": {"url": board_id},
                "Active": {"checkbox": True},
            }
        },
        timeout=30.0
    )
    print(f"  {'✅' if r.status_code == 200 else '❌'} {name}")

print("\nDone! Also update Cursor and Rippling in Notion:")
print("  - Cursor: change Platform to Ashby, Careers URL to 'cursor'")
print("  - Rippling: check if they use Ashby or keep as Career Page")
