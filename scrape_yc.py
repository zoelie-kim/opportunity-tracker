import os
import time
import httpx
from dotenv import load_dotenv
from datetime import date
from playwright.sync_api import sync_playwright

load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
YC_EMAIL = os.environ["YC_EMAIL"]
YC_PASSWORD = os.environ["YC_PASSWORD"]

notion_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

EXCLUDE_KEYWORDS = [
    # Technical
    "software engineer", "swe", "backend", "frontend", "fullstack", "full-stack",
    "machine learning", "ml engineer", "ai engineer", "research engineer",
    "research scientist", "data engineer", "devops", "security engineer",
    "infrastructure", "firmware", "embedded", "robotics", "ios engineer",
    "android", "hardware", "mechanical engineer", "electrical engineer",
    "computer vision", "deep learning", "nlp engineer",
    "full stack engineer", "full-stack engineer", "fullstack engineer",
    "game developer", "game design", "qa testing", "unreal engine",
    "3d artist", "member of technical staff", "chip", "eda",
    "product engineering", "engineering intern",
    # Design
    "ux", "ui/ux", "design intern", "design engineering", "graphic design",
    # Seniority / level
    "phd", "senior", "manager", "director", "principal", "staff engineer",
    "head of", "vp ", "vice president", "mba", "graduate",
    # Content / social
    "content creator", "content writer", "content specialist", "copywriter",
    "content intern", "social media", "video editor", "photographer",
    "videographer", "brand content",
    # Irrelevant
    "accountant", "controller", "tax", "loan", "credit", "wealth advisor",
    "forward deployed", "recruiting", "legal", "furniture",
    "materials engineering", "manufacturing", "structures engineering",
    "community architect", "game builder", "sandbox game",
    # Location
    "india", "bangalore", "remote (india", "hyderabad", "pune", "mumbai",
    "chennai", "delhi",
    # Research / ML / Science
    "ml research", "ai/ml", "ai internship", "research intern",
    "computational biology", "bioinformatics", "genomics", "clinical",
    "wet lab", "laboratory", "biology intern", "biotech intern",
    "life science", "drug discovery", "chemistry intern", "physics intern",
    "neuroscience", "materials science",
    # Vague
    "technical intern",
]

APPROVED_LOCATIONS = [
    "san francisco", "bay area", "san jose", "palo alto", "mountain view",
    "new york", "nyc", "brooklyn", "boston", "cambridge", "massachusetts",
    "chicago", "illinois", "los angeles", "la", "culver city",
    "austin", "texas", "seattle", "washington", "washington dc",
    "denver", "colorado", "miami", "san diego", "nashville",
    "toronto", "london", "paris", "amsterdam",
    "remote", "united states", "usa", "us remote", "anywhere",
]

def is_approved_location(location):
    if not location:
        return True
    loc = location.lower()
    if any(r in loc for r in ["remote", "anywhere", "us remote", "worldwide"]):
        return True
    return any(a in loc for a in APPROVED_LOCATIONS)

# Removed "product" from NAV_WORDS so Product Manager Intern gets through
NAV_WORDS = {
    "engineering", "design", "recruiting", "science",
    "operations", "sales", "marketing", "legal", "finance", "support"
}

INTERN_URLS = [
    "https://www.workatastartup.com/companies?demographic=any&hasEquity=any&hasSalary=any&industry=any&interviewProcess=any&jobType=intern&layout=list-compact&role=any&sortBy=created_desc&tab=any&usVisaNotRequired=any",
    "https://www.workatastartup.com/companies?demographic=any&hasEquity=any&hasSalary=any&industry=any&interviewProcess=any&jobType=intern&layout=list-compact&role=marketing&sortBy=created_desc&tab=any&usVisaNotRequired=any",
    "https://www.workatastartup.com/companies?demographic=any&hasEquity=any&hasSalary=any&industry=any&interviewProcess=any&jobType=intern&layout=list-compact&role=sales&sortBy=created_desc&tab=any&usVisaNotRequired=any",
    "https://www.workatastartup.com/companies?demographic=any&hasEquity=any&hasSalary=any&industry=any&interviewProcess=any&jobType=intern&layout=list-compact&role=operations&sortBy=created_desc&tab=any&usVisaNotRequired=any",
    "https://www.workatastartup.com/companies?demographic=any&hasEquity=any&hasSalary=any&industry=any&interviewProcess=any&jobType=intern&layout=list-compact&role=finance&sortBy=created_desc&tab=any&usVisaNotRequired=any",
]

def is_valid(title):
    t = title.lower().strip()
    if t in NAV_WORDS or len(title) < 6:
        return False
    if t == "intern":  # bare "intern" with nothing else
        return False
    if "intern" not in t:
        return False
    if any(kw in t for kw in EXCLUDE_KEYWORDS):
        return False
    return True

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

def scrape_text(job_page, selectors):
    for selector in selectors:
        try:
            el = job_page.query_selector(selector)
            if el:
                text = el.inner_text().strip()
                if text:
                    return text
        except:
            pass
    return ""

def get_job_details(context, job_url):
    try:
        job_page = context.new_page()
        job_page.goto(job_url, wait_until="networkidle", timeout=20000)
        time.sleep(1)

        company = scrape_text(job_page, [
            ".company-name", "h1 a", "[class*='company-name']",
            "[class*='companyName']", "h1"
        ]) or "YC Company"

        meta_parts = []

        location = scrape_text(job_page, [
            "[class*='location']", "[class*='Location']",
            "span:has-text('Remote')", "span:has-text('San Francisco')",
            "span:has-text('New York')"
        ])
        if location:
            meta_parts.append(f"📍 {location}")

        salary = scrape_text(job_page, [
            "[class*='salary']", "[class*='compensation']",
            "[class*='pay']", "span:has-text('$')"
        ])
        if salary and "$" in salary:
            meta_parts.append(f"💰 {salary[:80]}")

        size = scrape_text(job_page, [
            "[class*='size']", "[class*='employees']",
            "span:has-text('people')", "span:has-text('employees')"
        ])
        if size and any(w in size.lower() for w in ["people", "employee", "person"]):
            meta_parts.append(f"👥 {size[:50]}")

        posted = scrape_text(job_page, [
            "[class*='posted']", "[class*='date']", "time",
            "span:has-text('Posted')", "span:has-text('ago')"
        ])
        if posted:
            meta_parts.append(f"📅 {posted[:50]}")

        about = scrape_text(job_page, [
            "[class*='about']", "[class*='description']", "p:first-of-type"
        ])
        if about and len(about) > 20:
            first_sentence = about.split(".")[0][:150]
            meta_parts.append(f"🏢 {first_sentence}")

        notes = " | ".join(meta_parts) if meta_parts else ""
        job_page.close()
        return company, notes
    except:
        return "YC Company", ""

def add_to_notion(company, title, link, notes=""):
    properties = {
        "Name": {"title": [{"text": {"content": company}}]},
        "Role": {"rich_text": [{"text": {"content": title}}]},
        "Type": {"select": {"name": "Startup Job"}},
        "Status": {"select": {"name": "Preparing"}},
        "Priority": {"select": {"name": "High"}},
        "Date Added": {"date": {"start": date.today().isoformat()}},
        "Source": {"rich_text": [{"text": {"content": "YC Work at a Startup"}}]},
    }
    if link:
        properties["Link"] = {"url": link}
    if notes:
        properties["Notes"] = {"rich_text": [{"text": {"content": notes[:2000]}}]}
    r = httpx.post(
        "https://api.notion.com/v1/pages",
        headers=notion_headers,
        json={"parent": {"database_id": DATABASE_ID}, "properties": properties},
        timeout=30.0
    )
    return r.status_code == 200

print("\n🚀 Logging into YC Work at a Startup...\n")

print("Checking existing Notion entries to prevent duplicates...")
existing_links = get_existing_links()
print(f"Found {len(existing_links)} existing entries\n")

added = 0
skipped = 0
dupes = 0
seen = set()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = context.new_page()

    page.goto("https://account.ycombinator.com/", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    page.fill("#ycid-input", YC_EMAIL)
    page.fill("#password-input", YC_PASSWORD)
    page.click("button:has-text('Log In')")
    time.sleep(4)

    page.goto("https://www.workatastartup.com", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    try:
        page.click("a:has-text('Log In')", timeout=5000)
        time.sleep(4)
    except:
        pass
    print("✅ Logged in\n")

    for url in INTERN_URLS:
        print(f"Fetching: {url[:80]}...")
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        for _ in range(10):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)

        jobs = page.query_selector_all("a[href*='/jobs/']")
        print(f"  Found {len(jobs)} links")

        for job in jobs:
            href = job.get_attribute("href") or ""
            if not href or href in seen:
                continue
            seen.add(href)

            full_link = f"https://www.workatastartup.com{href}" if href.startswith("/") else href

            if full_link in existing_links:
                dupes += 1
                continue

            title = job.inner_text().strip()
            for noise in ["\nInterview Process", "\nJob match", "; Full-time", "; Full-Time"]:
                title = title.split(noise)[0].strip()

            if not is_valid(title):
                skipped += 1
                continue

            company, notes = get_job_details(context, full_link)

            # Location filter — extract from notes
            location = ""
            if "📍" in notes:
                loc_part = notes.split("📍")[1].split("|")[0].strip()
                location = loc_part
            # If no location scraped, check if India keywords in notes or title
            if not location:
                combined = (notes + " " + title).lower()
                if any(kw in combined for kw in ["india", "bangalore", "hyderabad", "pune", "mumbai", "chennai", "delhi"]):
                    skipped += 1
                    continue
            if location and not is_approved_location(location):
                skipped += 1
                continue

            success = add_to_notion(company, title, full_link, notes)
            if success:
                print(f"  ✅ {company} — {title}")
                added += 1
            else:
                print(f"  ❌ Failed: {title}")
            time.sleep(0.5)

    browser.close()

print(f"\n🎯 Done! Added {added} new YC internships")
print(f"   {dupes} duplicates skipped | {skipped} filtered out")
