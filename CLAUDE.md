# Opportunity Tracker

Personal automation pipeline that scrapes internship/job postings from multiple sources, stores them in Notion, and sends weekly digest emails and countdown alerts.

## Architecture

```
opportunity-tracker/
├── automation/              # Scheduling, email, and orchestration
│   ├── check_missed_tasks.py   # Main scheduler (invoked by launchd every 15min)
│   ├── run_all.py              # Runs all 3 scrapers sequentially
│   ├── countdown_alerts.py     # Daily email reminders for program deadlines
│   ├── newsletter.py           # Weekly HTML digest email (Sunday 5pm)
│   ├── error_monitor.py        # Scans logs for errors → health section in newsletter
│   └── verify_setup.py         # One-time validation of installation
├── scrapers/                # Job/internship scraping scripts
│   ├── scrape_yc.py            # Y Combinator Work at a Startup (Playwright + login)
│   ├── scrape_simplify.py      # SimplifyJobs GitHub README (BeautifulSoup)
│   └── scrape_companies.py     # Tracked companies via Greenhouse/Ashby/Workday/Career Pages
├── setup/                   # One-time initialization scripts
│   ├── setup_all.py            # Bootstrap Notion database schemas
│   ├── seed_companies.py       # Populate companies list
│   └── seed_programs.py        # Populate programs/fellowships
├── tests/                   # Unit tests
├── paths.py                 # Defines REPO_ROOT (used by all scripts)
├── requirements.txt         # Python dependencies
├── run_check_missed_tasks.sh   # Bash wrapper for launchd
└── com.zoelie.opportunity-tracker.check-missed-tasks.plist  # macOS LaunchAgent
```

## Scheduling

macOS launchd runs `run_check_missed_tasks.sh` → `automation/check_missed_tasks.py`:

| Task | Schedule | Script |
|------|----------|--------|
| `run_all` | Tue & Fri 10:00 AM | `automation/run_all.py` |
| `countdown_alerts` | Every day 10:00 AM | `automation/countdown_alerts.py` |
| `newsletter` | Sunday 5:00 PM (catch-up Monday) | `automation/newsletter.py` |

The scheduler uses `task_log.json` to track last successful run per task and looks back 21 days to catch missed runs when the Mac was asleep.

## Runtime Files (gitignored)

| File | Purpose |
|------|---------|
| `.env` | API credentials (see below) |
| `task_log.json` | Last successful run timestamps |
| `scraper.log` | Timestamped log of scraper runs |
| `alert_log.txt` | Deadline alerts appended daily for newsletter |
| `logs/check_missed_tasks.log` | Stdout from launchd |
| `logs/check_missed_tasks.error.log` | Stderr from launchd |

## Environment Variables (.env)

```
NOTION_TOKEN=
NOTION_DATABASE_ID=          # Jobs database
NOTION_COMPANIES_DB_ID=      # Companies database
NOTION_PROGRAMS_DB_ID=       # Programs/Fellowships database
NOTION_EVENTS_DB_ID=         # Events database

YC_EMAIL=                    # Y Combinator account
YC_PASSWORD=

GMAIL_ADDRESS=               # Sender Gmail account
GMAIL_APP_PASSWORD=          # Gmail app-specific password (not your regular password)
ALERT_EMAIL=                 # Recipient address for alerts/digest
```

## Setup

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install Playwright browser
python -m playwright install chromium

# 3. Copy and fill in credentials
cp .env.example .env  # then edit .env

# 4. Initialize Notion databases (one-time)
python setup/setup_all.py

# 5. Install macOS LaunchAgent (one-time)
./install_launch_agent.sh

# 6. Verify everything
python automation/verify_setup.py
```

## Running Manually

```bash
# Run all scrapers
python automation/run_all.py

# Run scheduler (checks what's due and runs it)
python automation/check_missed_tasks.py

# Dry run — see what would fire without running
python automation/check_missed_tasks.py --dry-run

# Send countdown alerts now
python automation/countdown_alerts.py

# Send newsletter now
python automation/newsletter.py
```

## Running Tests

```bash
python -m unittest discover -s tests -v
```

## Data Flow

1. **Scrapers** pull new internships → Notion Jobs DB
2. **countdown_alerts** checks Notion Programs DB daily → sends email + appends to `alert_log.txt`
3. **newsletter** reads Jobs DB + `alert_log.txt` + logs → sends weekly HTML digest
4. **error_monitor** scans `scraper.log` + `logs/*.log` for failure patterns → health section in newsletter

## Key Design Notes

- **File locking** (`fcntl.flock`): prevents duplicate runs if launchd triggers overlap
- **De-duplication**: scrapers check existing Notion links before adding
- **Stealth mode**: `playwright-stealth` is optional; scrape_companies.py imports it with a fallback
- **SimplifyJobs URL**: Update `REPO_URL` in `scrape_simplify.py` when Summer2027 repo drops (July 2026)
- **Notion as source of truth**: companies, programs, and jobs all live in Notion
