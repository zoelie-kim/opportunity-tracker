"""Second batch of company rows for the Notion companies database."""
import os
import httpx
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.environ["NOTION_TOKEN"]
COMPANIES_DB = os.environ["NOTION_COMPANIES_DB_ID"]
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}

ADD = [
    ("Adobe",            "Workday",  "https://adobe.wd5.myworkdayjobs.com/external_experienced"),
    ("Intel",            "LinkedIn", ""),
    ("IBM",              "LinkedIn", ""),
    ("Nvidia",           "Workday",  "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"),
    ("American Express", "LinkedIn", ""),
    ("Visa",             "LinkedIn", ""),
    ("Capital One",      "LinkedIn", ""),
    ("Mastercard",       "LinkedIn", ""),
    ("Fidelity",         "LinkedIn", ""),
    ("Bloomberg",        "LinkedIn", ""),
]

print("Adding companies...\n")
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
    print(f"  {'✅' if r.status_code == 200 else '❌'} {name}")

print(f"\nDone! {len(ADD)} companies added.")
