"""Tests for error_monitor log scanning and newsletter HTML."""
import unittest

from datetime import datetime

from error_monitor import format_health_html, line_looks_like_error


class TestErrorHeuristics(unittest.TestCase):
    def test_detects_failure_markers(self):
        self.assertTrue(line_looks_like_error("❌ scrape_simplify.py failed"))
        self.assertTrue(line_looks_like_error("Traceback (most recent call last):"))
        self.assertTrue(line_looks_like_error("Error: connection refused"))

    def test_ignores_normal_lines(self):
        self.assertFalse(line_looks_like_error("✅ script completed"))
        self.assertFalse(line_looks_like_error("[2026-01-01 10:00:00] Starting foo.py..."))


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
