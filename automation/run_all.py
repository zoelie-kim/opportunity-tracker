"""Run the three scrapers in order and append status lines to scraper.log at repo root."""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
from paths import REPO_ROOT

SCRAPERS = REPO_ROOT / "scrapers"
LOG_FILE = REPO_ROOT / "scraper.log"


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_scraper(filename: str):
    script = SCRAPERS / filename
    log(f"Starting {filename}...")
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            log(f"✅ {filename} completed")
            lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
            if lines:
                log(f"   {lines[-1]}")
        else:
            log(f"❌ {filename} failed")
            log(f"   {result.stderr.strip()[:200]}")
    except subprocess.TimeoutExpired:
        log(f"❌ {filename} timed out after 5 minutes")
    except Exception as e:
        log(f"❌ {filename} error: {str(e)}")


log("=" * 50)
log("🚀 Opportunity Tracker — starting full scrape run")
log("=" * 50)

run_scraper("scrape_yc.py")
run_scraper("scrape_simplify.py")
run_scraper("scrape_companies.py")

log("=" * 50)
log("✅ All scrapers complete")
log("=" * 50)
