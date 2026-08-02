"""
Scan local log files from the last 7 days and summarize lines that look like failures
(tracebacks, ❌ markers, timeouts, subprocess failures), plus flag tasks that have stopped
running at all. Used by the weekly newsletter for a short “system health” section.

A task that dies quietly writes *nothing*, so log scanning alone cannot see it — the only
evidence is a task_log.json timestamp that stops advancing. See collect_stale_tasks.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
from paths import REPO_ROOT

LOGS_DIR = REPO_ROOT / "logs"
TASK_LOG_PATH = REPO_ROOT / "task_log.json"

# Longest plausible gap between successful runs before something is wrong. Each is the task's
# own cadence (see TASKS in check_missed_tasks.py) plus a day of slack, so a Mac asleep over
# a single scheduled slot does not raise a false alarm.
STALENESS_LIMITS: dict[str, tuple[timedelta, str]] = {
    "run_all": (timedelta(days=5), "Tue & Fri 10:00"),
    "countdown_alerts": (timedelta(days=2), "daily 10:00"),
    "newsletter": (timedelta(days=9), "Sunday 17:00"),
}

# scraper.log / run_all.py format:  [2026-05-01 10:34:25] ...
_TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
# check_missed_tasks.log format:    🔍 ... schedule check at 2026-05-21T10:00:05
_TS_ISO = re.compile(r"schedule check at (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")


def _parse_line_ts(line: str) -> datetime | None:
    m = _TS.match(line.strip())
    if m:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    m = _TS_ISO.search(line)
    if m:
        return datetime.fromisoformat(m.group(1))
    return None


def line_looks_like_error(line: str) -> bool:
    if "❌" in line:
        return True
    low = line.lower()
    if "traceback" in low:
        return True
    if "error:" in low or "exception:" in low:
        return True
    if "failed" in low and ("script" in low or "timed out" in low or "code" in low):
        return True
    return False


def _discover_log_paths() -> list[Path]:
    out: list[Path] = []
    root = REPO_ROOT / "scraper.log"
    if root.is_file():
        out.append(root)
    if LOGS_DIR.is_dir():
        for p in sorted(LOGS_DIR.iterdir()):
            if p.is_file() and p.suffix == ".log":
                out.append(p)
    return out


def collect_error_events(
    lookback_days: int = 7,
    max_events: int = 25,
    since: datetime | None = None,
) -> list[dict]:
    """
    Return error-like log lines, newest first. If ``since`` is set (last digest time),
    only lines at or after that moment; otherwise use a rolling window of lookback_days.
    """
    if since is not None:
        cutoff = since
    else:
        cutoff = datetime.now() - timedelta(days=lookback_days)
    found: list[dict] = []

    for path in _discover_log_paths():
        try:
            raw = path.read_text(errors="replace")
        except OSError:
            continue
        if len(raw) > 400_000:
            raw = raw[-400_000:]
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = datetime.now().timestamp()

        last_ts: datetime | None = None
        for line in raw.splitlines():
            ts = _parse_line_ts(line)
            if ts is not None:
                last_ts = ts
            if not line_looks_like_error(line):
                continue
            effective = (
                last_ts if last_ts is not None else datetime.fromtimestamp(mtime)
            )
            if effective < cutoff:
                continue
            found.append(
                {
                    "source": path.name,
                    "time": effective,
                    "text": (line.strip())[:2000],
                }
            )
            if len(found) >= max_events * 3:
                break

    found.sort(key=lambda x: x["time"], reverse=True)
    # De-dupe identical source+text while preserving order
    seen: set[tuple[str, str]] = set()
    uniq: list[dict] = []
    for ev in found:
        key = (ev["source"], ev["text"][:200])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(ev)
        if len(uniq) >= max_events:
            break
    return uniq


def _parse_task_log_ts(raw: object) -> datetime | None:
    """Timestamps are normally ISO datetimes, but tolerate a bare date from older writers."""
    if not raw:
        return None
    s = str(raw).strip()
    if "T" in s:
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    try:
        return datetime.combine(date.fromisoformat(s), time(23, 59, 59))
    except ValueError:
        return None


def collect_stale_tasks(now: datetime | None = None) -> list[dict]:
    """
    Tasks whose last recorded success is older than their cadence allows, newest first.

    This is the counterpart to log scanning: it catches silence rather than noise. A task that
    never starts — launchd pointed at a stale path, a crash before the first print — produces
    no error lines to find, so the only signal is task_log.json failing to advance.
    """
    now = now or datetime.now()

    try:
        with open(TASK_LOG_PATH, "r", encoding="utf-8") as f:
            task_log = json.load(f)
    except (OSError, ValueError):
        # No readable task log means nothing has ever recorded a success. Report every task
        # rather than staying silent, since that is the same shape as total scheduler failure.
        task_log = {}

    stale: list[dict] = []
    for task, (limit, cadence) in STALENESS_LIMITS.items():
        last_run = _parse_task_log_ts(task_log.get(task))
        if last_run is None:
            stale.append(
                {"task": task, "last_run": None, "overdue_by": None, "cadence": cadence}
            )
            continue
        overdue_by = now - last_run - limit
        if overdue_by > timedelta(0):
            stale.append(
                {
                    "task": task,
                    "last_run": last_run,
                    "overdue_by": overdue_by,
                    "cadence": cadence,
                }
            )

    stale.sort(key=lambda s: (s["last_run"] is not None, s["last_run"] or datetime.min))
    return stale


def _format_stale_html(stale: list[dict]) -> str:
    if not stale:
        return ""

    rows = []
    for s in stale:
        if s["last_run"] is None:
            detail = "no successful run on record"
        else:
            days = s["overdue_by"].days
            plural = "s" if days != 1 else ""
            detail = (
                f"last succeeded {s['last_run'].strftime('%Y-%m-%d %H:%M')} — "
                f"{days} day{plural} beyond its normal gap"
            )
        rows.append(
            f'<li style="margin: 8px 0; font-size: 13px; color: #333;">'
            f'<code>{s["task"]}</code> <span style="color:#666;">({s["cadence"]})</span><br/>'
            f'<span style="color:#8a6d3b;">{detail}</span></li>'
        )

    return (
        '<section style="margin-bottom: 28px; padding: 14px 16px; background-color: #fff3cd; '
        'border-left: 4px solid #ffc107; border-radius: 4px;">'
        f'<h2 style="margin: 0 0 8px 0; color: #8a6d3b; font-size: 18px;">'
        f"Tasks not running ({len(stale)})</h2>"
        '<p style="margin: 0 0 10px 0; color: #8a6d3b; font-size: 14px;">'
        "These have stopped recording successes in <code>task_log.json</code>. Check that the "
        "LaunchAgent is loaded: <code>launchctl list | grep opportunity</code>."
        "</p>"
        f'<ul style="padding-left: 18px; margin: 0;">{"".join(rows)}</ul></section>'
    )


def format_health_html(events: list[dict], period_note: str) -> str:
    """HTML block for the newsletter: all clear, or a compact list of issues."""
    if not events:
        return (
            '<section style="margin-bottom: 28px; padding: 14px 16px; background-color: #e8f5e9; '
            'border-left: 4px solid #2e7d32; border-radius: 4px;">'
            '<h2 style="margin: 0 0 8px 0; color: #1b5e20; font-size: 18px;">System health (0 issues)</h2>'
            '<p style="margin: 0; color: #1b5e20;">'
            f"No error lines matched in <code>scraper.log</code> or <code>logs/*.log</code> ({period_note})."
            "</p></section>"
        )

    rows = []
    for ev in events:
        t = ev["time"].strftime("%Y-%m-%d %H:%M")
        esc = ev["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        rows.append(
            f'<li style="margin: 8px 0; font-size: 13px; color: #333;">'
            f'<span style="color:#666;">{t}</span> · <code>{ev["source"]}</code><br/>'
            f'<span style="font-family: ui-monospace, monospace; font-size: 12px;">{esc}</span></li>'
        )

    return f"""
    <section style="margin-bottom: 28px;">
        <h2 style="color: #c62828; border-bottom: 2px solid #c62828; padding-bottom: 8px; margin-top: 0;">
            System health ({len(events)} issue{"s" if len(events) != 1 else ""})
        </h2>
        <p style="color: #555; font-size: 14px; margin: 0 0 12px 0;">
            Error lines from <code>scraper.log</code> and <code>logs/*.log</code> ({period_note}).
        </p>
        <ul style="padding-left: 18px; margin: 0;">{"".join(rows)}</ul>
    </section>
    """


def build_weekly_health_html(since: datetime | None = None) -> tuple[str, int]:
    """
    Returns (html_fragment, issue_count). Pass ``since`` = last digest time to scope errors.

    The count covers error lines *and* stalled tasks, so a silent stall still shows up as a
    non-zero issue count even when no log line matched.
    """
    events = collect_error_events(since=since)
    stale = collect_stale_tasks()
    if since is not None:
        period_note = "since last digest"
    else:
        period_note = "past 7 days (no prior digest in task log)"
    # Stalled tasks lead: "nothing ran" outranks any individual error line below it.
    html = _format_stale_html(stale) + format_health_html(
        events, period_note=period_note
    )
    return html, len(events) + len(stale)
