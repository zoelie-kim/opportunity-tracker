import subprocess
import sys
import os
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper.log")

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def run_scraper(script):
    log(f"Starting {script}...")
    try:
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            log(f"✅ {script} completed")
            # Log last line of output (usually the summary)
            lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
            if lines:
                log(f"   {lines[-1]}")
        else:
            log(f"❌ {script} failed")
            log(f"   {result.stderr.strip()[:200]}")
    except subprocess.TimeoutExpired:
        log(f"❌ {script} timed out after 5 minutes")
    except Exception as e:
        log(f"❌ {script} error: {str(e)}")

log("=" * 50)
log("🚀 Opportunity Tracker — starting full scrape run")
log("=" * 50)

run_scraper("scrape_yc.py")
run_scraper("scrape_simplify.py")
run_scraper("scrape_companies.py")

log("=" * 50)
log("✅ All scrapers complete")
log("=" * 50)
