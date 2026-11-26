"""Gate BEA data downloads on the official Personal Income and Outlays calendar."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import time
import urllib.request
from zoneinfo import ZoneInfo

CALENDAR_URL = 'https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics'
MONTHS = {name: index for index, name in enumerate(
    'January February March April May June July August September October November December'.split(), 1)}


@dataclass(frozen=True)
class Release:
    at: datetime
    month: str


def parse_calendar(raw: str) -> list[Release]:
    # Unfold iCalendar continuation lines, including BEA's doubled CR endings.
    text = raw.replace('\r\n', '\n').replace('\r', '')
    text = re.sub(r'\n[ \t]', '', text)
    releases = set()
    for event in text.split('BEGIN:VEVENT')[1:]:
        fields = {}
        for line in event.split('END:VEVENT', 1)[0].splitlines():
            if ':' in line:
                name, value = line.split(':', 1)
                fields[name] = value
        summary = fields.get('SUMMARY', '').replace('\\,', ',')
        if not summary.startswith('Personal Income and Outlays,') or fields.get('STATUS') == 'CANCELLED':
            continue
        matches = re.findall(r'(' + '|'.join(MONTHS) + r')\s+(\d{4})\b', summary)
        if not matches:
            raise ValueError('PCE calendar event is missing its reference month')
        # Also handles combined releases, e.g. "October and November 2025".
        month = max(f'{year}-{MONTHS[name]:02}' for name, year in matches)
        starts = [(name, value) for name, value in fields.items() if name.split(';')[0] == 'DTSTART']
        if len(starts) != 1:
            raise ValueError('PCE calendar event has an invalid release time')
        name, value = starts[0]
        if value.endswith('Z'):
            at = datetime.strptime(value, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        elif ';TZID=' in name:
            at = datetime.strptime(value, '%Y%m%dT%H%M%S').replace(
                tzinfo=ZoneInfo(name.split(';TZID=', 1)[1])).astimezone(timezone.utc)
        else:
            raise ValueError('PCE release time must specify a timezone')
        releases.add(Release(at, month))
    if not releases:
        raise ValueError('Official calendar contains no Personal Income and Outlays releases')
    return sorted(releases, key=lambda release: release.at)


def decide(releases: list[Release], latest: str, now: datetime) -> dict:
    if now.tzinfo is None:
        raise ValueError('Calendar checks require a timezone-aware time')
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', latest):
        raise ValueError('Invalid dashboard reference month')
    if releases[-1].at < now - timedelta(days=45):
        raise ValueError('BEA calendar is stale; refusing to guess the next release date')
    due = [release for release in releases if release.at + timedelta(minutes=1) <= now]
    if not due:
        return {'run_update': False, 'expected_month': '', 'reason': 'before_first_release'}
    # Using the maximum due reference month also handles delayed combined releases.
    release = max(due, key=lambda release: (release.month, release.at))
    pending = latest < release.month
    return {'run_update': pending, 'expected_month': release.month,
            'release_utc': release.at.isoformat(),
            'reason': 'release_due_or_retry' if pending else 'scheduled_release_already_published'}


def download_calendar() -> str:
    for attempt in range(3):
        try:
            request = urllib.request.Request(CALENDAR_URL, headers={'User-Agent': 'ISMI-release-calendar/1.0'})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode('utf-8-sig')
        except (OSError, UnicodeError):
            if attempt == 2:
                raise RuntimeError('Official BEA calendar unavailable; data downloads were not started') from None
            time.sleep(5 * (attempt + 1))
    raise AssertionError('Unreachable')


def release_metadata(month: str, updated_at: datetime, release_utc: str | None = None) -> dict:
    if release_utc:
        at = datetime.fromisoformat(release_utc)
        if at.tzinfo is None or at > updated_at:
            raise ValueError('Invalid BEA release timestamp')
    else:
        matching = [release for release in parse_calendar(download_calendar())
                    if release.month == month and release.at <= updated_at]
        if not matching:
            raise ValueError('No published BEA calendar release matches the dashboard month')
        at = max(release.at for release in matching)
    return {'data_through': month, 'bea_release_date': at.astimezone(ZoneInfo('America/New_York')).date().isoformat(),
            'bea_release_utc': at.isoformat(), 'dashboard_updated_at': updated_at.isoformat(),
            'source': CALENDAR_URL}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path(__file__).parent / 'state.json')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'update-artifacts')
    parser.add_argument('--bypass', action='store_true', help='Permit a manual run outside the calendar')
    args = parser.parse_args()
    if args.bypass:
        report = {'run_update': True, 'expected_month': '', 'reason': 'manual_run'}
    else:
        state = json.loads(args.state.read_text())
        report = decide(parse_calendar(download_calendar()), state['latest_month'], datetime.now(timezone.utc))
        report['calendar_url'] = CALENDAR_URL
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'calendar.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write(f'run_update={str(report["run_update"]).lower()}\n')
            output.write(f'expected_month={report["expected_month"]}\n')
            output.write(f'release_utc={report.get("release_utc", "")}\n')


if __name__ == '__main__':
    main()
