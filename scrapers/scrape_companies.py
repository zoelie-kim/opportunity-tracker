"""For each tracked company in Notion, scrape careers pages (Playwright) for target roles."""
import os
import re
import httpx
import time
from pathlib import Path
from datetime import date
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
try:
    from playwright_stealth import Stealth
    def stealth_sync(page):
        Stealth().apply_stealth_sync(page)
    STEALTH = True
except Exception:
    try:
        from playwright_stealth import stealth_sync
        STEALTH = True
    except Exception:
        STEALTH = False

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
JOBS_DB = os.environ["NOTION_DATABASE_ID"]
COMPANIES_DB = os.environ["NOTION_COMPANIES_DB_ID"]

notion_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

TARGET_ROLES = [
    "gtm", "go-to-market", "business development", "biz dev",
    "sales intern", "sales development", "account executive",
    "business analyst", "data analyst", "business operations",
    "strategy", "operations intern", "product marketing",
    "growth intern", "growth marketing", "partnerships",
    "revenue operations", "solutions engineer intern",
    "sales engineer intern", "customer success intern",
    "program manager intern", "product manager intern",
    "apm intern", "market research", "sales enablement",
    "marketing intern", "marketing analytics",
]

EXCLUDE_KEYWORDS = [
    "software engineer", "swe", "backend", "frontend", "fullstack",
    "machine learning", "ml engineer", "research scientist", "data engineer",
    "devops", "security engineer", "infrastructure", "firmware", "embedded",
    "phd", "mba", "graduate", "senior", "manager", "director", "principal",
    "content creator", "social media", "graphic design", "recruiter", "legal",
    "developer intern", "software developer",
]

APPROVED_LOCATIONS = [
    "san francisco", "bay area", "san jose", "palo alto", "mountain view",
    "new york", "nyc", "brooklyn", "boston", "cambridge", "massachusetts",
    "chicago", "illinois", "los angeles", "la", "culver city",
    "austin", "texas", "seattle", "washington", "washington dc",
    "denver", "colorado", "miami", "san diego",
    "toronto", "london", "paris", "amsterdam",
    "nashville", "tennessee",
    "remote", "united states", "usa", "us remote", "anywhere",
]

def is_approved_location(location):
    if not location:
        return True  # no location = probably remote, allow it
    loc = location.lower()
    if any(r in loc for r in ["remote", "anywhere", "us remote", "worldwide"]):
        return True
    return any(a in loc for a in APPROVED_LOCATIONS)

def is_relevant(title):
    t = title.lower()
    if "intern" not in t:
        return False
    if any(kw in t for kw in EXCLUDE_KEYWORDS):
        return False
    return any(kw in t for kw in TARGET_ROLES)

def get_companies():
    r = httpx.post(
        f"https://api.notion.com/v1/databases/{COMPANIES_DB}/query",
        headers=notion_headers,
        json={"filter": {"property": "Active", "checkbox": {"equals": True}}},
        timeout=30.0
    )
    companies = []
    for page in r.json().get("results", []):
        props = page.get("properties", {})
        name = props.get("Name", {}).get("title", [{}])[0].get("text", {}).get("content", "")
        platform_data = props.get("Platform", {}).get("select")
        platform = platform_data.get("name", "") if platform_data else ""
        url = props.get("Careers URL", {}).get("url", "")
        page_id = page["id"]
        if name and platform and url:
            companies.append((name, platform, url, page_id))
    return companies

def get_existing_links():
    existing = set()
    has_more = True
    cursor = None
    while has_more:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        r = httpx.post(
            f"https://api.notion.com/v1/databases/{JOBS_DB}/query",
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

def update_last_checked(page_id):
    httpx.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=notion_headers,
        json={"properties": {"Last Checked": {"date": {"start": date.today().isoformat()}}}},
        timeout=30.0
    )

def add_to_notion(company, title, link, location="", source=""):
    properties = {
        "Name": {"title": [{"text": {"content": company}}]},
        "Role": {"rich_text": [{"text": {"content": title}}]},
        "Type": {"select": {"name": "Startup Job"}},
        "Status": {"select": {"name": "Preparing"}},
        "Priority": {"select": {"name": "High"}},
        "Date Added": {"date": {"start": date.today().isoformat()}},
        "Source": {"rich_text": [{"text": {"content": f"{source} | {location}" if location else source}}]},
    }
    if link:
        properties["Link"] = {"url": link}
    r = httpx.post(
        "https://api.notion.com/v1/pages",
        headers=notion_headers,
        json={"parent": {"database_id": JOBS_DB}, "properties": properties},
        timeout=30.0
    )
    return r.status_code == 200

def scrape_greenhouse(page, company, board_id, existing_links):
    """Scrape Greenhouse job board with Playwright — handles pagination."""
    added = 0
    try:
        url = f"https://job-boards.greenhouse.io/{board_id}"
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        def process_current_page():
            nonlocal added
            links = page.query_selector_all("a[href*='/jobs/']")
            for link_el in links:
                href = link_el.get_attribute("href") or ""
                full_text = link_el.inner_text().strip()
                lines = [l.strip() for l in full_text.split("\n") if l.strip()]
                if not lines:
                    continue
                title = lines[0]
                location = lines[1] if len(lines) > 1 else ""
                full_link = href if href.startswith("http") else f"https://job-boards.greenhouse.io{href}"
                if not is_relevant(title):
                    continue
                if not is_approved_location(location):
                    continue
                if full_link in existing_links:
                    continue
                success = add_to_notion(company, title, full_link, location, "Greenhouse")
                if success:
                    print(f"  ✅ {title}" + (f" ({location})" if location else ""))
                    existing_links.add(full_link)
                    added += 1
                time.sleep(0.3)

        # Process page 1
        process_current_page()

        # Click through remaining pages
        page_num = 2
        while True:
            next_btn = page.query_selector(f"button:has-text('{page_num}')")
            if not next_btn:
                break
            next_btn.click()
            time.sleep(2)
            process_current_page()
            page_num += 1
            if page_num > 20:  # safety limit
                break

        return added, None
    except Exception as e:
        return 0, str(e)[:60]

def scrape_ashby(page, company, board_id, existing_links):
    """Scrape Ashby job board — uses UUID-based URLs."""
    added = 0
    try:
        url = f"https://jobs.ashbyhq.com/{board_id}"
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Scroll to load all jobs
        prev_count = 0
        for _ in range(10):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)
            current_count = len(page.query_selector_all(f"a[href*='/{board_id}/']"))
            if current_count == prev_count:
                break
            prev_count = current_count

        links = page.query_selector_all(f"a[href*='/{board_id}/']")

        for link_el in links:
            href = link_el.get_attribute("href") or ""
            full_text = link_el.inner_text().strip()
            # Ashby link text format: "Job Title | | Department • Location • Type"
            lines = [l.strip() for l in full_text.split("\n") if l.strip() and l.strip() != "|"]
            if not lines:
                continue

            title = lines[0]
            # Location is usually in the first line after title, separated by •
            location = ""
            for part in full_text.split("•"):
                part = part.strip()
                if any(loc in part.lower() for loc in ["san francisco", "new york", "remote", "boston", "seattle", "london", "toronto"]):
                    location = part
                    break

            full_link = f"https://jobs.ashbyhq.com{href}" if href.startswith("/") else href

            if not is_relevant(title):
                continue
            if location and not is_approved_location(location):
                continue
            if full_link in existing_links:
                continue

            success = add_to_notion(company, title, full_link, location, "Ashby")
            if success:
                print(f"  ✅ {title}" + (f" ({location})" if location else ""))
                existing_links.add(full_link)
                added += 1
            time.sleep(0.3)
        return added, None
    except Exception as e:
        return 0, str(e)[:60]

def scrape_workday(company, base_url, existing_links):
    """Hit Workday internal API."""
    added = 0
    try:
        parts = base_url.replace("https://", "").split("/")
        host_parts = parts[0].split(".")
        subdomain, wd_num, jobsite = host_parts[0], host_parts[1], parts[1] if len(parts) > 1 else ""
        api_url = f"https://{subdomain}.{wd_num}.myworkdayjobs.com/wday/cxs/{subdomain}/{jobsite}/jobs"
        payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "intern"}
        headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        r = httpx.post(api_url, json=payload, headers=headers, timeout=15.0)
        if r.status_code != 200:
            return 0, f"HTTP {r.status_code}"

        jobs = r.json().get("jobPostings", [])
        for job in jobs:
            title = job.get("title", "")
            location = job.get("locationsText", "")
            job_path = job.get("externalPath", "")
            host = parts[0]
            link = f"https://{host}/en-US/{jobsite}{job_path}" if job_path else ""

            if not is_relevant(title) or not is_approved_location(location):
                continue
            if link in existing_links:
                continue

            success = add_to_notion(company, title, link, location, "Workday")
            if success:
                print(f"  ✅ {title} ({location})")
                existing_links.add(link)
                added += 1
            time.sleep(0.3)
        return added, None
    except Exception as e:
        return 0, str(e)[:60]

def scrape_career_page(page, company, url, existing_links):
    """Scrape careers page with Playwright + stealth."""
    added = 0
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)
        for _ in range(3):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)

        links = page.query_selector_all("a[href]")
        for link_el in links:
            href = link_el.get_attribute("href") or ""
            title = link_el.inner_text().strip()

            if not title or len(title) < 4 or len(title) > 120:
                continue
            if not is_relevant(title):
                continue

            # Build full URL
            if href.startswith("http"):
                full_link = href
            elif href.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                full_link = f"{parsed.scheme}://{parsed.netloc}{href}"
            else:
                continue

            if full_link in existing_links:
                continue

            success = add_to_notion(company, title, full_link, "", "Career Page")
            if success:
                print(f"  ✅ {title}")
                existing_links.add(full_link)
                added += 1
            time.sleep(0.3)
        return added, None
    except Exception as e:
        return 0, str(e)[:60]

# ── Main ──────────────────────────────────────────────────────────────────────

print("\n🔍 Scraping tracked companies...\n")
print(f"Stealth mode: {'✅ enabled' if STEALTH else '⚠️ not installed'}\n")

companies = get_companies()
existing_links = get_existing_links()
print(f"Checking {len(companies)} active companies | {len(existing_links)} existing entries\n")

total_added = 0
errors = []

greenhouse = [(n, u, p) for n, pl, u, p in companies if pl == "Greenhouse Board"]
workday = [(n, u, p) for n, pl, u, p in companies if pl == "Workday"]
ashby = [(n, u, p) for n, pl, u, p in companies if pl == "Ashby"]
career_pages = [(n, u, p) for n, pl, u, p in companies if pl == "Career Page"]

# Run everything with one browser instance
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    pg = context.new_page()
    if STEALTH:
        stealth_sync(pg)

    # --- Greenhouse ---
    if greenhouse:
        print("📋 Greenhouse job boards...")
        for name, board_id, page_id in greenhouse:
            print(f"  {name}...")
            added, error = scrape_greenhouse(pg, name, board_id, existing_links)
            if error:
                errors.append(f"{name} (Greenhouse): {error}")
            else:
                total_added += added
                if added == 0:
                    print(f"  — No matching roles")
            update_last_checked(page_id)
            time.sleep(1)

    # --- Workday ---
    if workday:
        print("\n📋 Workday...")
        for name, url, page_id in workday:
            print(f"  {name}...")
            added, error = scrape_workday(name, url, existing_links)
            if error:
                errors.append(f"{name} (Workday): {error}")
            else:
                total_added += added
                if added == 0:
                    print(f"  — No matching roles")
            update_last_checked(page_id)
            time.sleep(1)

    # --- Ashby ---
    if ashby:
        print("\n📋 Ashby job boards...")
        for name, board_id, page_id in ashby:
            print(f"  {name}...")
            added, error = scrape_ashby(pg, name, board_id, existing_links)
            if error:
                errors.append(f"{name} (Ashby): {error}")
            else:
                total_added += added
                if added == 0:
                    print(f"  — No matching roles")
            update_last_checked(page_id)
            time.sleep(1)

    # --- Career Pages ---
    if career_pages:
        print("\n📋 Career pages...")
        for name, url, page_id in career_pages:
            print(f"  {name}...")
            added, error = scrape_career_page(pg, name, url, existing_links)
            if error:
                errors.append(f"{name} (Career Page): {error}")
            else:
                total_added += added
                if added == 0:
                    print(f"  — No matching intern roles")
            update_last_checked(page_id)
            time.sleep(1)

    browser.close()

print(f"\n🎯 Done! Added {total_added} roles across {len(companies)} companies")
if errors:
    print(f"\n⚠️ {len(errors)} errors:")
    for e in errors:
        print(f"   • {e}")
