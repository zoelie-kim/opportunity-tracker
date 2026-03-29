# Opportunity Tracker

**What it is:** A personal pipeline that collects internship and job postings that match your filters, stores them in **Notion**, and emails you a **weekly digest**, **deadline reminders**, and a short **system health** summary (recent errors from local logs). Scheduling runs on your **Mac** via **launchd** (with catch-up if the laptop was off).

**Why it exists:** Cut manual checking across YC, aggregated lists, and company career pages—while keeping everything in one Notion database and your inbox.

---

## Stack

- **Python 3** — orchestration, HTTP (Notion API, scraping)
- **Playwright** — browser automation where pages need a real browser
- **Notion** — jobs database, companies/programs as configured in your workspace
- **Gmail (app password)** — outbound email
- **macOS `launchd`** — repeating “what’s due?” checks (`automation/check_missed_tasks.py`)

---

## Folder layout

| Folder | Contents |
|--------|----------|
| **`automation/`** | Scheduler (`check_missed_tasks.py`), `run_all.py`, `newsletter.py`, `countdown_alerts.py`, `error_monitor.py`, `verify_setup.py` |
| **`scrapers/`** | `scrape_yc.py`, `scrape_simplify.py`, `scrape_companies.py` |
| **`setup/`** | One-time Notion bootstrap: `setup_all.py`, `seed_*.py`, `add_*.py`, `clear_database.py`, etc. |
| **`tests/`** | `unittest` modules for schedule logic, error monitor, and setup checks |
| **Repo root** | `.env`, `paths.py` (repo root constant), `task_log.json`, logs, `run_check_missed_tasks.sh`, plist, `install_launch_agent.sh` |

Data files (`task_log.json`, `alert_log.txt`, `scraper.log`, `logs/`) stay at the **project root** so paths stay stable for `launchd`.

---

## Architecture (high level)

1. **Scrapers** (`scrapers/`) — fetch or drive listings, filter, write to Notion.
2. **`automation/run_all.py`** — runs the three scrapers in order; logs to `scraper.log` at repo root.
3. **`automation/countdown_alerts.py`** — reads program deadlines from Notion, sends reminder emails, appends lines to `alert_log.txt` for the newsletter.
4. **`automation/newsletter.py`** — builds the digest email: new roles (Notion **Date Added**), `alert_log.txt` lines, and **`error_monitor`** log lines. After the first run, content is scoped **since the previous successful digest** via `task_log.json` → `newsletter`.
5. **`automation/check_missed_tasks.py`** — decides what’s due (time slots + `task_log.json`), runs the scripts above on schedule. Uses a **file lock** so overlapping `launchd` runs can’t send duplicate emails. The **weekly digest** is only for **Sunday after 5pm** (local), with **Monday** catch-up if Sunday was missed.
6. **`install_launch_agent.sh` + `.plist`** — register the checker with macOS.

Nothing runs in the cloud unless you add that yourself; if the Mac was asleep, the next run **catches up** missed slots.

---

## Setup (short)

1. Clone the repo, create a venv, install dependencies (Playwright, httpx, python-dotenv, beautifulsoup4, etc.—match your imports).
2. Create a `.env` file at the **repo root** with your Notion tokens, database IDs, Gmail app password, and any scraper credentials.
3. Run **`./install_launch_agent.sh`** once so `launchd` loads the LaunchAgent.
4. Optional: **`python3 automation/verify_setup.py`** — confirms files exist and the scheduler registered the job.

---

## Useful commands

Run these from the **repository root** (where `.env` lives).

| Command | Purpose |
|--------|---------|
| `python3 automation/verify_setup.py` | Friendly check: files + scheduler registration |
| `python3 -m unittest discover -s tests -v` | All tests |
| `python3 automation/check_missed_tasks.py --dry-run` | Show what would run; no side effects |
| `python3 automation/run_all.py` | Full scrape only |
| `python3 automation/newsletter.py` | Send digest manually (needs env + data) |

Logs (ignored by git): `scraper.log`, `logs/`, `task_log.json`, `alert_log.txt`.

---

## License

Private / personal project unless you add one.
