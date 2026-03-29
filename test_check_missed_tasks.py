"""Unit tests for schedule / catch-up logic in check_missed_tasks.py."""
import unittest
from datetime import date, datetime, time, timedelta

from check_missed_tasks import missed_slot_pending, parse_last_run, TASKS


class TestParseLastRun(unittest.TestCase):
    def test_iso_datetime(self):
        t = parse_last_run("2026-03-25T10:05:00")
        self.assertEqual(t, datetime(2026, 3, 25, 10, 5, 0))

    def test_legacy_date_is_noon(self):
        t = parse_last_run("2026-03-25")
        self.assertEqual(t, datetime.combine(date(2026, 3, 25), time(12, 0, 0)))

    def test_empty(self):
        self.assertIsNone(parse_last_run(None))
        self.assertIsNone(parse_last_run(""))


class TestMissedSlotPending(unittest.TestCase):
    """Behavior: if Mac was off at slot time, next run after slot with last_run before slot => due."""

    def test_tuesday_before_10_not_due(self):
        # Tuesday 09:00 — today's 10:00 slot not passed; prior Fri already ran
        now = datetime(2026, 3, 24, 9, 0, 0)
        last = datetime(2026, 3, 20, 10, 30, 0)  # last Friday scrape done
        sched = TASKS["run_all"]["schedule"]
        self.assertFalse(missed_slot_pending(last, sched, now))

    def test_tuesday_after_10_due_when_never_ran(self):
        now = datetime(2026, 3, 24, 11, 0, 0)
        sched = TASKS["run_all"]["schedule"]
        self.assertTrue(missed_slot_pending(None, sched, now))

    def test_tuesday_after_10_not_due_if_already_ran_after_slot(self):
        now = datetime(2026, 3, 24, 11, 0, 0)
        last = datetime(2026, 3, 24, 10, 30, 0)
        sched = TASKS["run_all"]["schedule"]
        self.assertFalse(missed_slot_pending(last, sched, now))

    def test_wednesday_catches_missed_tuesday(self):
        # Open laptop Wed 11am; Tue 10am was missed
        now = datetime(2026, 3, 25, 11, 0, 0)
        last = datetime(2026, 3, 20, 10, 0, 0)  # prior Friday's run
        sched = TASKS["run_all"]["schedule"]
        self.assertTrue(missed_slot_pending(last, sched, now))

    def test_newsletter_sunday_5pm_catch_up_monday(self):
        # Sunday 2026-03-22 17:00 slot; Monday 09:00, never ran newsletter
        now = datetime(2026, 3, 23, 9, 0, 0)
        sched = TASKS["newsletter"]["schedule"]
        self.assertTrue(missed_slot_pending(None, sched, now))

    def test_newsletter_not_due_before_sunday_5pm(self):
        now = datetime(2026, 3, 22, 16, 0, 0)  # Sunday 4pm
        last = datetime(2026, 3, 15, 17, 30, 0)  # last week's newsletter already sent
        sched = TASKS["newsletter"]["schedule"]
        self.assertFalse(missed_slot_pending(last, sched, now))

    def test_countdown_daily_10am_due_after_10(self):
        now = datetime(2026, 3, 28, 11, 0, 0)  # Saturday 11am
        sched = TASKS["countdown_alerts"]["schedule"]
        self.assertTrue(missed_slot_pending(None, sched, now))

    def test_countdown_not_due_before_10(self):
        now = datetime(2026, 3, 28, 9, 30, 0)  # Saturday 9:30
        last = datetime(2026, 3, 27, 10, 15, 0)  # yesterday's 10am alerts done
        sched = TASKS["countdown_alerts"]["schedule"]
        self.assertFalse(missed_slot_pending(last, sched, now))

    def test_countdown_same_day_already_ran(self):
        now = datetime(2026, 3, 28, 15, 0, 0)
        last = datetime(2026, 3, 28, 10, 15, 0)
        sched = TASKS["countdown_alerts"]["schedule"]
        self.assertFalse(missed_slot_pending(last, sched, now))


if __name__ == "__main__":
    unittest.main()
