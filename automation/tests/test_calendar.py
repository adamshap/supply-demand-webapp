from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_calendar import parse_calendar, decide, release_metadata

CALENDAR = """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Personal Income and Outlays\\, October and November 2025
DTSTART:20260122T150000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:Personal Income and Outlays\\, July 2026
DTSTART:20260826T123000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:Personal Income and Outlays\\, September 2026
DTSTART:20261029T123000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:Personal Income and Outlays\\, October 20
 26
DTSTART:20261125T133000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:Personal Income and Outlays\\, November 2026
DTSTART:20261223T133000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:Personal Income and Outlays\\, December 2026
DTSTART:20270128T133000Z
END:VEVENT
END:VCALENDAR
"""

def utc(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)

class CalendarTests(unittest.TestCase):
    def setUp(self): self.releases = parse_calendar(CALENDAR)

    def test_actual_release_times_and_combined_periods(self):
        self.assertEqual(self.releases[0].month,'2025-11')
        self.assertEqual(self.releases[1].at.hour,12)
        self.assertEqual(self.releases[3].at.hour,13)
        self.assertEqual(self.releases[3].month,'2026-10')

    def test_wait_until_after_release_then_retry_until_published(self):
        self.assertFalse(decide(self.releases,'2026-09',utc('2026-11-25T13:30:59'))['run_update'])
        result=decide(self.releases,'2026-09',utc('2026-11-25T13:31'))
        self.assertTrue(result['run_update']); self.assertEqual(result['expected_month'],'2026-10')
        self.assertTrue(decide(self.releases,'2026-09',utc('2026-11-28T21:47'))['run_update'])
        self.assertFalse(decide(self.releases,'2026-10',utc('2026-11-28T21:47'))['run_update'])

    def test_first_minute_after_summer_release(self):
        self.assertFalse(decide(self.releases,'2026-06',utc('2026-08-26T12:30:59'))['run_update'])
        result=decide(self.releases,'2026-06',utc('2026-08-26T12:31'))
        self.assertTrue(result['run_update'])
        self.assertEqual(result['expected_month'],'2026-07')
        self.assertFalse(decide(self.releases,'2026-07',utc('2026-08-26T12:41'))['run_update'])

    def test_rescheduled_release_and_year_rollover(self):
        moved=parse_calendar(CALENDAR.replace('20261125T133000Z','20261127T150000Z'))
        self.assertFalse(decide(moved,'2026-09',utc('2026-11-26T21:47'))['run_update'])
        self.assertTrue(decide(moved,'2026-09',utc('2026-11-27T17:47'))['run_update'])
        self.assertEqual(decide(self.releases,'2026-11',utc('2027-01-28T13:47'))['expected_month'],'2026-12')

    def test_invalid_or_stale_calendar_fails_closed(self):
        with self.assertRaises(ValueError): parse_calendar('BEGIN:VCALENDAR')
        with self.assertRaises(ValueError): decide(self.releases,'2027-01',utc('2027-06-01T13:47'))

    def test_metadata_uses_release_date_not_check_or_export_date(self):
        now=utc('2026-11-26T03:30')
        with patch('release_calendar.download_calendar',return_value=CALENDAR):
            metadata=release_metadata('2026-10',now)
        self.assertEqual(metadata['bea_release_date'],'2026-11-25')
        self.assertEqual(metadata['data_through'],'2026-10')
        self.assertEqual(metadata['dashboard_updated_at'],now.isoformat())
        with self.assertRaises(ValueError): release_metadata('2026-10',now,'2026-12-23T13:30:00+00:00')

if __name__ == '__main__': unittest.main()
