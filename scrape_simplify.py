import os
import re
import httpx
import time
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import date

load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]

notion_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# Update this URL when Summer2027 repo drops in July 2026
REPO_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md"

# Only include roles posted within this many days
MAX_DAYS_OLD = 7

# Approved locations — role must be in one of these or Remote
APPROVED_LOCATIONS = [
    "san francisco", "sf", "bay area", "south bay", "silicon valley",
    "san jose", "oakland", "berkeley", "palo alto", "mountain view",
    "new york", "nyc", "new york city", "brooklyn",
    "boston", "cambridge", "massachusetts",
    "chicago", "illinois",
    "los angeles", "la", "culver city", "santa monica",
    "austin", "texas",
    "seattle", "washington",
    "washington dc", "dc", "arlington, va",
    "denver", "colorado",
    "miami", "florida",
    "san diego",
    "toronto", "ontario",
    "london", "uk", "united kingdom",
    "paris", "france",
    "amsterdam", "netherlands",
    "remote",
]

TARGET_ROLES = [
    "gtm", "go-to-market", "business development", "biz dev",
    "sales intern", "sales development", "account executive", "account manager",
    "business analyst", "data analyst", "business operations",
    "strategy and operations", "strategy intern", "operations intern",
    "product marketing", "growth intern", "growth marketing",
    "partnerships intern", "revenue operations",
    "solutions engineer intern", "sales engineer intern",
    "customer success intern", "program manager intern",
    "product manager intern", "apm intern",
    "market research intern", "sales enablement",
    "marketing intern", "marketing analytics",
]

EXCLUDE_KEYWORDS = [
    "software engineer", "swe", "backend", "frontend", "fullstack", "full-stack",
    "machine learning", "ml ", "research scientist", "data engineer",
    "devops", "security engineer", "infrastructure", "firmware", "embedded",
    "hardware", "mechanical", "electrical engineer", "chemical",
    "phd", "mba", "graduate", "senior", "manager", "director", "principal",
    "content creator", "content writer", "social media", "graphic design",
    "video editor", "recruiter", "legal", "developer intern",
    "software developer", "lab operations", "gmp", "biotherapeutics",
    "broadcast", "supply chain", "anti money laundering", "risk data",
    "cyber security", "reliability", "capacity management",
    "transportation", "vascular", "pharmaceutical", "clinical",
]

def is_approved_location(location):
    loc = location.lower()
    if not loc or loc == "unknown":
        return False
    return any(approved in loc for approved in APPROVED_LOCATIONS)

def is_relevant(role_title):
    t = role_title.lower()
    if "intern" not in t and "co-op" not in t and "coop" not in t:
        return False
    if any(kw in t for kw in EXCLUDE_KEYWORDS):
        return False
    if any(kw in t for kw in TARGET_ROLES):
        return True
    return False

def parse_days_old(days_str):
    try:
        return int(re.sub(r'[^0-9]', '', days_str))
    except:
        return 999

def get_existing_links():
    existing = set()
    has_more = True
    cursor = None
    while has_more:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        r = httpx.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers=notion_headers,
            json=payload,
            timeout=30.0
        )
        data = r.json()
        for page in data.get("results", []):
            link = page.get("properties", {}).get("Link", {}).get("url")
            if link:
                existing.add(link)
        has_more = data.get("has_more", False)
        cursor = data.get("next_cursor")
    return existing

def add_to_notion(company, title, link, location=""):
    properties = {
        "Name": {"title": [{"text": {"content": company}}]},
        "Role": {"rich_text": [{"text": {"content": title}}]},
        "Type": {"select": {"name": "Startup Job"}},
        "Status": {"select": {"name": "Preparing"}},
        "Priority": {"select": {"name": "High"}},
        "Date Added": {"date": {"start": date.today().isoformat()}},
        "Source": {"rich_text": [{"text": {"content": f"SimplifyJobs | {location}"}}]},
    }
    if link:
        properties["Link"] = {"url": link}
    r = httpx.post(
        "https://api.notion.com/v1/pages",
        headers=notion_headers,
        json={"parent": {"database_id": DATABASE_ID}, "properties": properties},
        timeout=30.0
    )
    return r.status_code == 200

print(f"\n📋 Fetching SimplifyJobs (last {MAX_DAYS_OLD} days, approved locations only)...\n")

response = httpx.get(REPO_URL, timeout=30.0)
if response.status_code != 200:
    print(f"❌ Failed to fetch README: {response.status_code}")
    exit()

soup = BeautifulSoup(response.text, "html.parser")
rows = soup.find_all("tr")
print(f"✅ Found {len(rows)} rows\n")

existing_links = get_existing_links()
print(f"Found {len(existing_links)} existing entries (duplicate check)\n")

added = 0
skipped_old = 0
skipped_location = 0
skipped_irrelevant = 0
skipped_dupe = 0
seen_links = set()

for row in rows:
    cols = row.find_all("td")
    if len(cols) < 3:
        continue

    # Age filter
    days_old = parse_days_old(cols[-1].get_text(strip=True))
    if days_old > MAX_DAYS_OLD:
        skipped_old += 1
        continue

    # Skip closed
    if "🔒" in row.get_text():
        skipped_irrelevant += 1
        continue

    # Company
    company_tag = cols[0].find("a")
    company = company_tag.get_text(strip=True) if company_tag else cols[0].get_text(strip=True)
    if company == "↳":
        continue

    # Role
    role = cols[1].get_text(strip=True)

    # Location
    location = cols[2].get_text(strip=True).replace("\n", ", ")[:100]

    # Location filter
    if not is_approved_location(location):
        skipped_location += 1
        continue

    # Role filter
    if not is_relevant(role):
        skipped_irrelevant += 1
        continue

    # Apply link
    link = ""
    for a in (cols[3].find_all("a") if len(cols) > 3 else []):
        href = a.get("href", "")
        if href and "simplify.jobs/p/" not in href and "GHList" not in href and "imgur" not in href:
            link = href
            break
    if not link:
        for a in (cols[3].find_all("a") if len(cols) > 3 else []):
            href = a.get("href", "")
            if href and "imgur" not in href:
                link = href
                break

    # Dupe check
    if link and (link in existing_links or link in seen_links):
        skipped_dupe += 1
        continue
    if link:
        seen_links.add(link)

    success = add_to_notion(company, role, link, location)
    if success:
        print(f"  ✅ [{days_old}d] {company} — {role} ({location})")
        added += 1
    else:
        print(f"  ❌ Failed: {company} — {role}")
    time.sleep(0.3)

print(f"\n🎯 Done! Added {added} roles from SimplifyJobs")
print(f"   {skipped_old} too old | {skipped_location} wrong location | {skipped_irrelevant} irrelevant | {skipped_dupe} dupes")
print(f"💡 Update REPO_URL when Summer2027 drops in July 2026")
