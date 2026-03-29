# Opportunity Tracker

**What it is:** A personal pipeline that collects internship and job postings that match your filters, stores them in **Notion**, and emails you a **weekly digest**, **deadline reminders**, and a short **system health** summary (recent errors from local logs). Scheduling runs on your **Mac** via **launchd** (with catch-up if the laptop was off).

**Why it exists:** Cut manual checking across YC, aggregated lists, and company career pages—while keeping everything in one Notion database and your inbox.

---

## Stack

- **Python 3** — orchestration, HTTP (Notion API, scraping)
- **Playwright** — browser automation where pages need a real browser
- **Notion** — jobs database, companies/programs as configured in your workspace
- **Gmail (app password)** — outbound email
- **macOS `launchd`** — repeating “what’s due?” checks (`check_missed_tasks.py`)

---

## Architecture (high level)

1. **Scrapers** (`scrape_yc.py`, `scrape_simplify.py`, `scrape_companies.py`) — fetch or drive listings, filter, write to Notion.
2. **`run_all.py`** — runs the three scrapers in order; logs to `scraper.log`.
3. **`countdown_alerts.py`** — reads program deadlines from Notion, sends reminder emails, appends lines to `alert_log.txt` for the newsletter.
4. **`newsletter.py`** — builds the digest email: new roles (Notion **Date Added**), `alert_log.txt` lines, and **`error_monitor`** log lines. After the first run, content is scoped **since the previous successful digest** via `task_log.json` → `newsletter` (not a blind rolling 7-day window from “today”).
5. **`check_missed_tasks.py`** — decides what’s due (time slots + `task_log.json`), runs `run_all`, `countdown_alerts`, and `newsletter` when appropriate. Uses a **file lock** (`.check_missed_tasks.lock`) so overlapping `launchd` runs can’t send duplicate emails. The **weekly digest** is only scheduled for **Sunday after 5pm** (local time), with **Monday** as catch-up if Sunday was missed—not Tuesday–Saturday, so it won’t fire on the wrong night.
6. **`install_launch_agent.sh` + `.plist`** — register the checker with macOS so it runs on login, on an interval, and at calendar times.

Nothing runs in the cloud unless you add that yourself; if the Mac was asleep, the next run **catches up** missed slots.

---

## Setup (short)

1. Clone the repo, create a venv, install dependencies (Playwright, httpx, python-dotenv, beautifulsoup4, etc.—match your imports).
2. Create a `.env` file with your Notion tokens, database IDs, Gmail app password, and any scraper credentials.
3. Run **`./install_launch_agent.sh`** once so `launchd` loads the LaunchAgent.
4. Optional: **`python3 verify_setup.py`** — confirms files exist and the scheduler registered the job.

---

## Useful commands

| Command | Purpose |
|--------|---------|
| `python3 verify_setup.py` | Friendly check: files + scheduler registration |
| `python3 -m unittest discover -v` | Tests (schedule logic + setup) |
| `python3 check_missed_tasks.py --dry-run` | Show what would run; no side effects |
| `python3 run_all.py` | Full scrape only |
| `python3 newsletter.py` | Send digest manually (needs env + data) |

Logs (ignored by git): `scraper.log`, `logs/`, `task_log.json`, `alert_log.txt`.

---

## Repo layout (main scripts)

| File | Role |
|------|------|
| `run_all.py` | Chains all scrapers |
| `check_missed_tasks.py` | Due-date logic + runs other scripts on schedule |
| `countdown_alerts.py` | Deadline emails + `alert_log.txt` lines |
| `newsletter.py` | Weekly HTML email (jobs + alerts + **error_monitor**) |
| `error_monitor.py` | Reads `scraper.log` + `logs/*.log`; builds the “system health” block in the newsletter |
| `install_launch_agent.sh` | Installs LaunchAgent plist into `~/Library/LaunchAgents/` |

Setup/seed scripts (`setup_all.py`, `seed_*.py`, etc.) are for one-time Notion schema or data bootstrapping.

---

## License

Private / personal project unless you add one.
