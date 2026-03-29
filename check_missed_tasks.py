#!/usr/bin/env python3
"""
Decide which automation scripts are due (scrape bundle, daily alerts, weekly newsletter),
run them once each, and record last success times in task_log.json. Invoked by macOS launchd.

The newsletter is scheduled for Sunday 17:00 local time; catch-up is allowed on Monday only
if Sunday was missed—never Tue–Sat, so the digest is not sent on the wrong weekday.
"""
import fcntl
import json
import subprocess
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TASK_LOG = SCRIPT_DIR / "task_log.json"
SCHEDULER_LOCK = SCRIPT_DIR / ".check_missed_tasks.lock"

# Python weekday(): Monday=0 … Sunday=6. (hour, minute) local time.
TASKS = {
    "run_all": {
        "script": SCRIPT_DIR / "run_all.py",
        "schedule": [(1, 10, 0), (4, 10, 0)],  # Tue & Fri 10:00
        "description": "Full scraper run",
    },
    "countdown_alerts": {
        "script": SCRIPT_DIR / "countdown_alerts.py",
        "schedule": [(d, 10, 0) for d in range(7)],  # every day 10:00
        "description": "Countdown alerts",
    },
    "newsletter": {
        "script": SCRIPT_DIR / "newsletter.py",
        "schedule": [(6, 17, 0)],  # Sunday 17:00
        "description": "Weekly newsletter",
    },
}


def load_task_log():
    if not TASK_LOG.exists():
        return {}
    try:
        with open(TASK_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_task_log(log):
    try:
        with open(TASK_LOG, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save task log: {e}")


def acquire_scheduler_lock():
    """
    Non-blocking exclusive lock so two launchd-triggered runs cannot overlap.
    Without this, both can see the same 'due' tasks and send duplicate emails.
    """
    SCHEDULER_LOCK.parent.mkdir(parents=True, exist_ok=True)
    fp = open(SCHEDULER_LOCK, "a+")
    try:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fp.close()
        return None
    return fp


def parse_last_run(raw):
    """ISO datetime, or legacy YYYY-MM-DD (treated as noon that day)."""
    if not raw:
        return None
    if isinstance(raw, dict):
        return None
    s = str(raw).strip()
    if not s:
        return None
    if "T" in s:
        return datetime.fromisoformat(s)
    try:
        d = date.fromisoformat(s)
        return datetime.combine(d, time(12, 0, 0))
    except ValueError:
        return None


def slot_datetime(d: date, hour: int, minute: int) -> datetime:
    return datetime.combine(d, time(hour, minute, 0))


def missed_slot_pending(last_run: datetime | None, schedule, now: datetime) -> bool:
    """True if some scheduled slot S satisfies last_run < S <= now."""
    if last_run is None:
        last_run = datetime.min
    # Look back far enough to catch a missed run after a long shutdown
    start_date = now.date() - timedelta(days=21)
    d = start_date
    end_date = now.date()
    while d <= end_date:
        wd = d.weekday()
        for w, h, m in schedule:
            if wd != w:
                continue
            s = slot_datetime(d, h, m)
            if last_run < s <= now:
                return True
        d += timedelta(days=1)
    return False


def newsletter_due(last_run: datetime | None, now: datetime) -> bool:
    """
    True only on Sunday after 17:00 (this week's slot), or on Monday for catch-up after a missed
    Sunday. False Tue–Sat so a 'weekly' email does not fire on e.g. Saturday night.
    """
    if last_run is None:
        last_run = datetime.min

    wd = now.weekday()  # Mon=0 … Sun=6

    if wd in (1, 2, 3, 4, 5):  # Tue–Sat
        return False

    if wd == 6:  # Sunday
        s = slot_datetime(now.date(), 17, 0)
        if now < s:
            return False
        return last_run < s <= now

    if wd == 0:  # Monday — catch up for the Sunday that just passed
        prev_sun = now.date() - timedelta(days=1)
        s = slot_datetime(prev_sun, 17, 0)
        return last_run < s <= now

    return False


def run_task(task_key, task_config):
    script = task_config["script"]
    if not script.exists():
        print(f"  ❌ {task_key}: Script not found at {script}")
        return False
    try:
        print(f"  ▶️  Running {task_config['description']}...")
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(SCRIPT_DIR),
            capture_output=True,
            timeout=3600,
        )
        if result.returncode == 0:
            print(f"  ✅ {task_key} completed successfully")
            return True
        print(f"  ❌ {task_key} failed with code {result.returncode}")
        if result.stderr:
            print(f"     Error: {result.stderr.decode()[:500]}")
        return False
    except subprocess.TimeoutExpired:
        print(f"  ❌ {task_key} timed out")
        return False
    except Exception as e:
        print(f"  ❌ {task_key} error: {e}")
        return False


def main(dry_run: bool = False):
    now = datetime.now()
    print(f"\n🔍 Opportunity tracker — schedule check at {now.isoformat(timespec='seconds')}")
    if dry_run:
        print("   (dry-run: no scripts executed, task log unchanged)\n")
    else:
        print()

    lock_fp = None
    if not dry_run:
        lock_fp = acquire_scheduler_lock()
        if lock_fp is None:
            print("  ⏳ Another run is already in progress — skipping (avoids duplicate jobs/emails).\n")
            return

    try:
        task_log = load_task_log()
        ran_anything = False

        # Tue/Fri: run_all before countdown_alerts
        order = ["run_all", "countdown_alerts", "newsletter"]

        for task_key in order:
            if task_key not in TASKS:
                continue
            cfg = TASKS[task_key]
            last_run = parse_last_run(task_log.get(task_key))

            if task_key == "newsletter":
                due = newsletter_due(last_run, now)
            else:
                due = missed_slot_pending(last_run, cfg["schedule"], now)

            if not due:
                print(f"  ✓ {task_key}: nothing due")
                continue

            print(f"  ⚠️  {task_key}: due (missed slot or not yet run for a passed slot)")
            if dry_run:
                print(f"  ⏭️  Would run {cfg['script'].name}")
                ran_anything = True
                continue
            if run_task(task_key, cfg):
                task_log[task_key] = datetime.now().isoformat(timespec="seconds")
                ran_anything = True
                save_task_log(task_log)

        if ran_anything:
            print("\n✅ Scheduled tasks completed\n" if not dry_run else "\n✅ Dry-run: would have run tasks above\n")
        else:
            print("\n✓ Nothing to run right now\n")
    finally:
        if lock_fp is not None:
            try:
                fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            lock_fp.close()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Run due scheduled jobs (scrape, alerts, newsletter).")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would run without executing scripts or changing task_log.json",
    )
    args = p.parse_args()
    main(dry_run=args.dry_run)
