# -*- coding: utf-8 -*-

"""Stdlib unit tests for the modified_ago filter (run locally; not in CI)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load_modified_ago():
    filter_path = (
        Path(__file__).resolve().parents[4] / "plugins" / "filter" / "modified_ago.py"
    )
    spec = importlib.util.spec_from_file_location("modified_ago", filter_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_mod = _load_modified_ago()
modified_ago = _mod.modified_ago
_SHEETS_EPOCH = _mod._SHEETS_EPOCH
_EM_DASH = _mod._EM_DASH


class TestModifiedAgo(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)

    def test_blank_returns_em_dash(self):
        self.assertEqual(modified_ago("", now=self.now), _EM_DASH)
        self.assertEqual(modified_ago(None, now=self.now), _EM_DASH)
        self.assertEqual(modified_ago("   ", now=self.now), _EM_DASH)

    def test_unparseable_returns_em_dash(self):
        self.assertEqual(modified_ago("not-a-date", now=self.now), _EM_DASH)

    def test_zero_and_singular_days(self):
        self.assertEqual(
            modified_ago(self.now.isoformat().replace("+00:00", "Z"), now=self.now),
            "0 days ago",
        )
        one_day_ago = self.now - timedelta(days=1)
        self.assertEqual(
            modified_ago(one_day_ago.strftime("%Y-%m-%dT%H:%M:%SZ"), now=self.now),
            "1 day ago",
        )

    def test_days_boundary_at_thirty(self):
        stamp = self.now - timedelta(days=30)
        self.assertEqual(
            modified_ago(stamp.strftime("%Y-%m-%dT%H:%M:%S.000Z"), now=self.now),
            "30 days ago",
        )

    def test_weeks_after_thirty_days(self):
        stamp = self.now - timedelta(days=31)
        self.assertEqual(
            modified_ago(stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), now=self.now),
            "4 weeks ago",
        )

    def test_weeks_boundary_at_ninety(self):
        stamp = self.now - timedelta(days=90)
        self.assertEqual(
            modified_ago(stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), now=self.now),
            "12 weeks ago",
        )

    def test_months_after_ninety_days(self):
        stamp = self.now - timedelta(days=91)
        self.assertEqual(
            modified_ago(stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), now=self.now),
            "3 months ago",
        )

    def test_iso_with_offset(self):
        stamp = self.now - timedelta(days=5)
        self.assertEqual(
            modified_ago(stamp.isoformat(), now=self.now),
            "5 days ago",
        )

    def test_sheets_serial_number(self):
        stamp = self.now - timedelta(days=10)
        serial = (stamp - _SHEETS_EPOCH).total_seconds() / 86400.0
        self.assertEqual(modified_ago(serial, now=self.now), "10 days ago")
        self.assertEqual(modified_ago(str(serial), now=self.now), "10 days ago")

    def test_future_timestamp_is_zero_days(self):
        future = self.now + timedelta(days=3)
        self.assertEqual(
            modified_ago(future.strftime("%Y-%m-%dT%H:%M:%SZ"), now=self.now),
            "0 days ago",
        )


if __name__ == "__main__":
    unittest.main()
