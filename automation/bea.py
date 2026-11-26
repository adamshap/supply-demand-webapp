"""BEA client: bounded retries, gzip, and no credentials in saved files or logs."""
from __future__ import annotations

import gzip
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd


class BeaClient:
    def __init__(self, key: str, attempts: int = 4, timeout: int = 90):
        if not key:
            raise ValueError('BEA_API_KEY is not configured')
        self.key, self.attempts, self.timeout = key, attempts, timeout
        self.last_request = 0.0
        self.received = []

    def table(self, name: str, years: str) -> pd.DataFrame:
        parameters = dict(UserID=self.key, method='GetData', datasetname='NIUnderlyingDetail',
                          TableName=name, Frequency='M', Year=years, ResultFormat='JSON')
        url = 'https://apps.bea.gov/api/data/?' + urllib.parse.urlencode(parameters)
        last_error = 'unknown error'
        retry_after = 0
        for attempt in range(self.attempts):
            if attempt:
                delay = max(retry_after, (5, 15, 60)[min(attempt - 1, 2)])
                print(f'{name}: retry {attempt + 1}/{self.attempts} after {last_error}; waiting {delay}s', flush=True)
                time.sleep(delay)
            # BEA limits uncompressed data volume to 100 MB/minute. A full
            # underlying-detail table is about 82 MB; avoid back-to-back tables.
            self.received = [(t, n) for t, n in self.received if time.monotonic() - t < 61]
            expected = 85_000_000 if years == 'ALL' else 5_000_000
            while self.received and sum(n for _, n in self.received) + expected > 95_000_000:
                time.sleep(max(0, 61 - (time.monotonic() - self.received[0][0])))
                self.received = [(t, n) for t, n in self.received if time.monotonic() - t < 61]
            time.sleep(max(0, 1.1 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                request = urllib.request.Request(url, headers={'Accept-Encoding': 'gzip', 'User-Agent': 'Supply-demand-BEA-updater/1.0'})
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = response.read()
                    if response.headers.get('Content-Encoding') == 'gzip':
                        body = gzip.decompress(body)
                self.received.append((time.monotonic(), len(body)))
                result = json.loads(body)['BEAAPI']['Results']
                if not isinstance(result, dict) or not result.get('Data'):
                    raise ValueError('BEA returned no data or an API error')
                return to_panel(result['Data'])
            except urllib.error.HTTPError as error:
                last_error = f'HTTP {error.code}'
                header = error.headers.get('Retry-After', '')
                retry_after = int(header) if header.isdigit() else 0
                if retry_after > 120:
                    break
                if error.code not in (408, 429, 500, 502, 503, 504):
                    break
            except (OSError, ValueError, KeyError, TypeError):
                last_error = 'temporary connection, response, or data error'
        # urllib exceptions can contain the request URL, including the API key.
        raise RuntimeError(f'BEA {name} download failed ({last_error}); published data were not changed') from None


def to_panel(rows: list[dict]) -> pd.DataFrame:
    raw = pd.DataFrame(rows)
    required = {'SeriesCode', 'TimePeriod', 'DataValue'}
    if not required.issubset(raw.columns):
        raise ValueError('BEA response schema is incomplete')
    raw = raw[raw.TimePeriod.str.fullmatch(r'\d{4}M\d{2}', na=False)].copy()
    raw['value'] = pd.to_numeric(raw.DataValue.str.replace(',', ''), errors='coerce')
    if (raw.groupby(['SeriesCode', 'TimePeriod']).value.nunique() > 1).any():
        raise ValueError('Conflicting BEA observations for the same series and month')
    raw['month'] = (raw.TimePeriod.str[:4].astype(int) - 1960) * 12 + raw.TimePeriod.str[5:].astype(int) - 1
    return raw.groupby(['month', 'SeriesCode']).value.first().unstack('SeriesCode').sort_index()


def fingerprint(panel: pd.DataFrame) -> str:
    return hashlib.sha256(panel.reindex(sorted(panel.columns), axis=1).to_csv(float_format='%.12g', lineterminator='\n').encode()).hexdigest()
