import unittest
from datetime import datetime, timedelta, timezone
from startup_check import due


class DueTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)

    def check_due(self, hours, deadline_hours=100, dispatch=None, blocked=None):
        review = {"last_completed_utc": (self.now - timedelta(hours=hours)).isoformat(),
                  "last_blocked_utc": blocked}
        account = {"next_deadline_utc": (self.now + timedelta(hours=deadline_hours)).isoformat()}
        return due(self.now, review, account, dispatch or {})[0]

    def test_routine_boundary(self):
        self.assertFalse(self.check_due(55.9))
        self.assertTrue(self.check_due(56))

    def test_deadline_boundaries(self):
        self.assertFalse(self.check_due(5.9, 12))
        self.assertTrue(self.check_due(6, 12))
        self.assertFalse(self.check_due(.74, 1))
        self.assertTrue(self.check_due(.75, 1))

    def test_deadline_passed_needs_catch_up(self):
        self.assertTrue(self.check_due(2, -1))
        self.assertFalse(self.check_due(.5, -1))

    def test_duplicate_and_retry_protection(self):
        recent = (self.now - timedelta(minutes=10)).isoformat()
        self.assertFalse(self.check_due(60, dispatch={"queued_utc": recent}))
        self.assertFalse(self.check_due(60, dispatch={"last_attempt_utc": recent}))
        self.assertTrue(self.check_due(60, dispatch={"queued_utc": (self.now - timedelta(hours=7)).isoformat()}))

    def test_blocked_and_clock(self):
        self.assertFalse(self.check_due(60, blocked=self.now.isoformat()))
        self.assertFalse(self.check_due(-1))

    def test_missing_completion(self):
        self.assertTrue(due(self.now, {}, {}, {})[0])
        self.assertFalse(due(self.now, {"disabled": True}, {}, {})[0])


if __name__ == "__main__":
    unittest.main()
