"""
Quick smoke test for scrape_yc.py — verifies login and page load work with
wait_until="load" without running the full hour-long scrape.

Run from the repo root:
    python3 tests/smoke_test_yc.py

Pass:  Logs in, loads the first intern listing page, finds at least 1 job link.
Fail:  Any exception or 0 job links found.
"""
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

YC_EMAIL = os.environ["YC_EMAIL"]
YC_PASSWORD = os.environ["YC_PASSWORD"]

FIRST_URL = (
    "https://www.workatastartup.com/companies"
    "?demographic=any&hasEquity=any&hasSalary=any&industry=any"
    "&interviewProcess=any&jobType=intern&layout=list-compact"
    "&role=any&sortBy=created_desc&tab=any&usVisaNotRequired=any"
)

from playwright.sync_api import sync_playwright

print("\n🧪 YC scraper smoke test\n")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    )
    page = context.new_page()

    print("Step 1: Loading YC login page...")
    page.goto("https://account.ycombinator.com/", wait_until="load", timeout=30000)
    time.sleep(2)
    print("  ✅ Login page loaded")

    print("Step 2: Logging in...")
    page.fill("#ycid-input", YC_EMAIL)
    page.fill("#password-input", YC_PASSWORD)
    page.click("button:has-text('Log In')")
    time.sleep(4)
    print("  ✅ Login submitted")

    print("Step 3: Loading workatastartup.com...")
    page.goto("https://www.workatastartup.com", wait_until="load", timeout=30000)
    time.sleep(2)
    try:
        page.click("a:has-text('Log In')", timeout=5000)
        time.sleep(4)
    except Exception:
        pass
    print("  ✅ Main site loaded")

    print("Step 4: Loading first intern listing page...")
    page.goto(FIRST_URL, wait_until="load", timeout=30000)
    time.sleep(2)

    # Scroll once to trigger lazy loading
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)

    jobs = page.query_selector_all("a[href*='/jobs/']")
    print(f"  Found {len(jobs)} job links")

    browser.close()

if len(jobs) == 0:
    print("\n❌ FAIL — page loaded but no job links found (login may have failed)\n")
    sys.exit(1)

print(f"\n✅ PASS — login works and job listings load correctly with wait_until='load'\n")
