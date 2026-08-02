"""Tests for error_monitor log scanning, task staleness, and newsletter HTML."""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "automation"))

import error_monitor
from error_monitor import (
    _format_stale_html,
    _parse_line_ts,
    collect_stale_tasks,
    format_health_html,
    line_looks_like_error,
)


class TestErrorHeuristics(unittest.TestCase):
    def test_detects_failure_markers(self):
        self.assertTrue(line_looks_like_error("❌ scrape_simplify.py failed"))
        self.assertTrue(line_looks_like_error("Traceback (most recent call last):"))
        self.assertTrue(line_looks_like_error("Error: connection refused"))

    def test_ignores_normal_lines(self):
        self.assertFalse(line_looks_like_error("✅ script completed"))
        self.assertFalse(
            line_looks_like_error("[2026-01-01 10:00:00] Starting foo.py...")
        )


class TestParseLineTs(unittest.TestCase):
    def test_scraper_log_format(self):
        ts = _parse_line_ts("[2026-04-17 10:10:43] ❌ scrape_yc.py failed")
        self.assertEqual(ts, datetime(2026, 4, 17, 10, 10, 43))

    def test_check_missed_tasks_log_format(self):
        # This was the broken case: timestamps in this format got mtime fallback,
        # causing old April errors to always appear as current in the newsletter.
        ts = _parse_line_ts(
            "🔍 Opportunity tracker — schedule check at 2026-04-19T17:02:32"
        )
        self.assertEqual(ts, datetime(2026, 4, 19, 17, 2, 32))

    def test_plain_error_line_returns_none(self):
        self.assertIsNone(_parse_line_ts("  ❌ countdown_alerts failed with code 1"))


class TestHealthHtml(unittest.TestCase):
    def test_empty_is_green(self):
        html = format_health_html([], "since last digest")
        self.assertIn("System health (0 issues)", html)
        self.assertIn("#e8f5e9", html)

    def test_with_events(self):
        html = format_health_html(
            [
                {
                    "source": "scraper.log",
                    "time": datetime(2026, 3, 1, 10, 0, 0),
                    "text": "❌ x failed",
                }
            ],
            "since last digest",
        )
        self.assertIn("System health", html)
        self.assertIn("scraper.log", html)


class TestStaleTasks(unittest.TestCase):
    """
    Staleness detection covers the failure mode log scanning cannot see: a task that never
    starts writes no error line, so task_log.json standing still is the only evidence.
    """

    NOW = datetime(2026, 8, 1, 12, 0, 0)

    def _with_task_log(self, contents):
        """Point error_monitor at a temp task log. ``contents`` of None writes no file."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "task_log.json"
        if contents is not None:
            path.write_text(json.dumps(contents), encoding="utf-8")
        patcher = mock.patch.object(error_monitor, "TASK_LOG_PATH", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_recent_runs_are_not_stale(self):
        self._with_task_log(
            {
                "run_all": "2026-07-31T10:00:00",
                "countdown_alerts": "2026-08-01T10:00:00",
                "newsletter": "2026-07-27T17:00:00",
            }
        )
        self.assertEqual(collect_stale_tasks(now=self.NOW), [])

    def test_flags_task_that_stopped_running(self):
        # The real incident: launchd pointed at a stale path, so nothing advanced after Jul 28.
        self._with_task_log(
            {
                "run_all": "2026-07-28T21:56:43",
                "countdown_alerts": "2026-07-28T22:57:37",
                "newsletter": "2026-07-27T10:52:21",
            }
        )
        stale = collect_stale_tasks(now=self.NOW)
        self.assertEqual({s["task"] for s in stale}, {"countdown_alerts"})

    def test_total_stall_flags_every_task(self):
        self._with_task_log(
            {
                "run_all": "2026-06-01T10:00:00",
                "countdown_alerts": "2026-06-01T10:00:00",
                "newsletter": "2026-06-01T17:00:00",
            }
        )
        stale = collect_stale_tasks(now=self.NOW)
        self.assertEqual(len(stale), 3)

    def test_missing_task_log_flags_every_task(self):
        self._with_task_log(None)
        stale = collect_stale_tasks(now=self.NOW)
        self.assertEqual(len(stale), 3)
        self.assertTrue(all(s["last_run"] is None for s in stale))

    def test_missing_key_is_stale(self):
        self._with_task_log({"countdown_alerts": "2026-08-01T10:00:00"})
        stale = collect_stale_tasks(now=self.NOW)
        self.assertEqual({s["task"] for s in stale}, {"run_all", "newsletter"})

    def test_tolerates_bare_date_timestamp(self):
        self._with_task_log({"countdown_alerts": "2026-08-01"})
        stale = collect_stale_tasks(now=self.NOW)
        self.assertNotIn("countdown_alerts", {s["task"] for s in stale})

    def test_corrupt_task_log_flags_every_task(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "task_log.json"
        path.write_text("{not json", encoding="utf-8")
        with mock.patch.object(error_monitor, "TASK_LOG_PATH", path):
            self.assertEqual(len(collect_stale_tasks(now=self.NOW)), 3)


class TestStaleHtml(unittest.TestCase):
    def test_no_stale_renders_nothing(self):
        self.assertEqual(_format_stale_html([]), "")

    def test_stale_block_names_task_and_recovery_step(self):
        html = _format_stale_html(
            [
                {
                    "task": "run_all",
                    "last_run": datetime(2026, 7, 28, 21, 56),
                    "overdue_by": timedelta(days=3),
                    "cadence": "Tue & Fri 10:00",
                }
            ]
        )
        self.assertIn("Tasks not running (1)", html)
        self.assertIn("run_all", html)
        self.assertIn("3 days beyond its normal gap", html)
        self.assertIn("launchctl list", html)

    def test_never_run_task_reads_clearly(self):
        html = _format_stale_html(
            [
                {
                    "task": "newsletter",
                    "last_run": None,
                    "overdue_by": None,
                    "cadence": "Sunday 17:00",
                }
            ]
        )
        self.assertIn("no successful run on record", html)


if __name__ == "__main__":
    unittest.main()
