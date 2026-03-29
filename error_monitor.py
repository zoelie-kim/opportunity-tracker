"""
Scan local log files from the last 7 days and summarize lines that look like failures
(tracebacks, ❌ markers, timeouts, subprocess failures). Used by the weekly newsletter
for a short “system health” section.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LOGS_DIR = SCRIPT_DIR / "logs"

# Timestamps written by run_all / check_missed_tasks style loggers
_TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")


def _parse_line_ts(line: str) -> datetime | None:
    m = _TS.match(line.strip())
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")


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
    root = SCRIPT_DIR / "scraper.log"
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
            effective = last_ts if last_ts is not None else datetime.fromtimestamp(mtime)
            if effective < cutoff:
                continue
            found.append(
                {
                    "source": path.name,
                    "time": effective,
                    "text": (line.strip())[:420],
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


def format_health_html(events: list[dict], period_note: str) -> str:
    """HTML block for the newsletter: all clear, or a compact list of issues."""
    if not events:
        return (
            '<section style="margin-bottom: 28px; padding: 14px 16px; background-color: #e8f5e9; '
            'border-left: 4px solid #2e7d32; border-radius: 4px;">'
            '<h2 style="margin: 0 0 8px 0; color: #1b5e20; font-size: 18px;">System health (0 issues)</h2>'
            "<p style=\"margin: 0; color: #1b5e20;\">"
            f"No error lines matched in <code>scraper.log</code> or <code>logs/*.log</code> ({period_note})."
            "</p></section>"
        )

    rows = []
    for ev in events:
        t = ev["time"].strftime("%Y-%m-%d %H:%M")
        esc = (
            ev["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        rows.append(
            f'<li style="margin: 8px 0; font-size: 13px; color: #333;">'
            f'<span style="color:#666;">{t}</span> · <code>{ev["source"]}</code><br/>'
            f'<span style="font-family: ui-monospace, monospace; font-size: 12px;">{esc}</span></li>'
        )

    return f'''
    <section style="margin-bottom: 28px;">
        <h2 style="color: #c62828; border-bottom: 2px solid #c62828; padding-bottom: 8px; margin-top: 0;">
            System health ({len(events)} issue{"s" if len(events) != 1 else ""})
        </h2>
        <p style="color: #555; font-size: 14px; margin: 0 0 12px 0;">
            Error lines from <code>scraper.log</code> and <code>logs/*.log</code> ({period_note}).
        </p>
        <ul style="padding-left: 18px; margin: 0;">{"".join(rows)}</ul>
    </section>
    '''


def build_weekly_health_html(since: datetime | None = None) -> tuple[str, int]:
    """Returns (html_fragment, error_count). Pass ``since`` = last digest time to scope errors."""
    events = collect_error_events(since=since)
    if since is not None:
        period_note = "since last digest"
    else:
        period_note = "past 7 days (no prior digest in task log)"
    return format_health_html(events, period_note=period_note), len(events)
