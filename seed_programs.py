import os
import httpx
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.environ["NOTION_TOKEN"]
PROGRAMS_DB = os.environ["NOTION_PROGRAMS_DB_ID"]
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}

# Only adding new entries — not touching existing ones
ADD = [
    {
        "name": "Amazon internship recruiting opens",
        "opens": "2026-07-01",
        "notes": "Amazon opens earliest among big tech, historically July. Check amazon.jobs and LinkedIn alert.",
    },
    {
        "name": "Big Tech internship recruiting opens (Microsoft, Meta, Apple, etc.)",
        "opens": "2026-08-15",
        "notes": "Microsoft mid-Aug, Meta early Sept, Apple Sept-Nov rolling. Set LinkedIn alerts now. Apply ASAP when open — rolling admissions.",
    },
    {
        "name": "Google internship recruiting opens",
        "opens": "2026-10-15",
        "notes": "Google opens mid-October with a 2-4 WEEK window only. Miss it and you're out for the cycle. High priority alert.",
    },
    {
        "name": "Finance / Big 4 internship recruiting opens",
        "opens": "2026-08-01",
        "notes": "Capital One, Visa, Amex, Mastercard, Big 4 consulting open Aug-Sept. Note: Goldman/JPMorgan IB opens Dec-Jan — already passed for 2027 cycle.",
    },
]

print("Adding entries to Recruiting Calendar...\n")
for entry in ADD:
    props = {
        "Name": {"title": [{"text": {"content": entry["name"]}}]},
        "Notes": {"rich_text": [{"text": {"content": entry["notes"]}}]},
    }
    if entry.get("opens"):
        props["Opens On"] = {"date": {"start": entry["opens"]}}

    r = httpx.post(
        "https://api.notion.com/v1/pages",
        headers=headers,
        json={"parent": {"database_id": PROGRAMS_DB}, "properties": props},
        timeout=30.0
    )
    print(f"  {'✅' if r.status_code == 200 else f'❌ {r.status_code} {r.text[:100]}'} {entry['name']}")

print("\nDone! Existing entries untouched.")
