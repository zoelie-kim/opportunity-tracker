"""Tests for error_monitor log scanning and newsletter HTML."""
import sys
import unittest
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "automation"))

from error_monitor import format_health_html, line_looks_like_error, _parse_line_ts


class TestErrorHeuristics(unittest.TestCase):
    def test_detects_failure_markers(self):
        self.assertTrue(line_looks_like_error("❌ scrape_simplify.py failed"))
        self.assertTrue(line_looks_like_error("Traceback (most recent call last):"))
        self.assertTrue(line_looks_like_error("Error: connection refused"))

    def test_ignores_normal_lines(self):
        self.assertFalse(line_looks_like_error("✅ script completed"))
        self.assertFalse(line_looks_like_error("[2026-01-01 10:00:00] Starting foo.py..."))


class TestParseLineTs(unittest.TestCase):
    def test_scraper_log_format(self):
        ts = _parse_line_ts("[2026-04-17 10:10:43] ❌ scrape_yc.py failed")
        self.assertEqual(ts, datetime(2026, 4, 17, 10, 10, 43))

    def test_check_missed_tasks_log_format(self):
        # This was the broken case: timestamps in this format got mtime fallback,
        # causing old April errors to always appear as current in the newsletter.
        ts = _parse_line_ts("🔍 Opportunity tracker — schedule check at 2026-04-19T17:02:32")
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


if __name__ == "__main__":
    unittest.main()
