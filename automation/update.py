"""Download BEA, reproduce seven Stata exports, validate, then publish together."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from bea import BeaClient, fingerprint
from data import inputs
from engine import calculate
from exports import build, FILES
from release_calendar import release_metadata
from workbook import month_number, quarter_number, read_frames, write_frames

ROOT = Path(__file__).resolve().parents[1]
MODEL_VERSION = '2026-11-bea-supply-demand-stata-v1'
PUBLIC_FILES = [*FILES, 'supply_demand_public.xlsx']


def file_hash(name, raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n') if name.endswith('.csv') else raw).hexdigest()


def rebuild_required(previous, latest, force=False):
    old, new = pd.Period(previous, 'M'), pd.Period(latest, 'M')
    if new < old:
        raise ValueError('Refusing to move the dashboard backward')
    return force or new.month == 9 or any(p.month == 9 for p in pd.period_range(old + 1, new, freq='M'))


def merge_frame(old, new, full, quarterly=False):
    if list(old.columns) != list(new.columns):
        raise ValueError('Export schema changed')
    number = quarter_number if quarterly else month_number
    if old.date.duplicated().any() or new.date.duplicated().any():
        raise ValueError('Duplicate export dates')
    if number(new.date.iloc[-1]) < number(old.date.iloc[-1]):
        raise ValueError('New export would roll back published data')
    if full:
        if old.date.iloc[0] != new.date.iloc[0]:
            raise ValueError('Benchmark would truncate the historical baseline')
        result = new.copy()
    else:
        # Stata merge, update replace: incoming missing annual values do not
        # erase stored history at the beginning of an incremental window.
        result = new.set_index('date').combine_first(old.set_index('date')).reset_index()[old.columns]
    result = result.sort_values('date', key=lambda dates: dates.map(number)).reset_index(drop=True)
    integers = result.date.map(number).to_numpy()
    if not np.all(np.diff(integers) == 1):
        raise ValueError('Missing export months or quarters')
    values = result.drop(columns='date').to_numpy(dtype=float)
    allowed = np.zeros(values.shape, dtype=bool)
    for j, name in enumerate(result.columns[1:]):
        if name.endswith('_yoy'):
            allowed[:3 if quarterly else 11, j] = True
    if np.isinf(values).any() or (np.isnan(values) & ~allowed).any() or (np.abs(values) > 100).any():
        raise ValueError('Invalid contributions or missing observations outside the annual startup period')
    return result


def candidates(panel, categories, schema, full):
    latest = int(panel.index.max())
    monthly = calculate(panel, categories, list(range(108 if full else latest - 24, latest + 1)))
    csvs, excels = build(monthly, schema)
    if not full:
        # Goods/services code updates 18 months; the aggregate code uses 25.
        gs_csvs, gs_excels = build(monthly.tail(18), schema)
        for file in FILES:
            if 'goods_services' in file:
                csvs[file], excels[file] = gs_csvs[file], gs_excels[file]
    last_q = latest // 3
    quarters = calculate(panel, categories, list(range(36 if full else last_q - 24, last_q + 1)), True)
    qcsv, qexcel = build(quarters, schema, True)
    return csvs | qcsv, excels | qexcel


def run(root, mode, full_history, cached_inputs, output, expected_month=None, release_utc=None):
    mapping = pd.read_csv(root / 'automation/categories.csv')
    schema = json.loads((root / 'automation/schema.json').read_text())
    before = {name: (root / name).read_bytes() for name in PUBLIC_FILES}
    hashes = {name: file_hash(name, raw) for name, raw in before.items()}
    previous = {name: pd.read_csv(BytesIO(before[name])) for name in FILES}
    previous_excel = read_frames(root / 'supply_demand_public.xlsx', schema)
    latest_number = month_number(previous['supply_demand_baseline.csv'].date.iloc[-1])
    previous_month = str(pd.Period('1960-01', 'M') + latest_number)
    state_path = root / 'automation/state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    baseline_changed = hashes != state.get('published_files_sha256')
    now = datetime.now(timezone.utc)
    probe_hash = None
    if cached_inputs:
        if mode != 'validate':
            raise ValueError('Cached inputs are only allowed for read-only validation')
        panel = pd.read_csv(cached_inputs, index_col='time_month')
    else:
        client = BeaClient(os.environ.get('BEA_API_KEY', ''))
        years = f'{now.year - 1},{now.year}'
        def download(years):
            return inputs(client.table('U20404', years), client.table('U20405', years),
                          client.table('U20403', years), mapping)
        try:
            probe = download(years)
        except RuntimeError:
            if now.month != 1:
                raise
            years = str(now.year - 1)
            probe = download(years)
        available = str(pd.Period('1960-01', 'M') + int(probe.index.max()))
        if expected_month and available < expected_month:
            return dict(status='waiting_for_release', latest_month=previous_month, available_month=available,
                        expected_month=expected_month, changed=False, data_changed=False)
        if available < previous_month:
            raise ValueError('BEA is serving an older release; no files were changed')
        probe_hash = fingerprint(probe)
        if (mode == 'update' and not full_history and not baseline_changed
                and state.get('model_version') == MODEL_VERSION
                and probe_hash == state.get('probe_sha256') and available == previous_month):
            return dict(status='unchanged', latest_month=previous_month, changed=False, data_changed=False)
        print('Downloading current-vintage BEA price, expenditure and quantity histories', flush=True)
        panel = download('ALL')
        confirmation = download(years)
        if fingerprint(panel.reindex(confirmation.index)) != fingerprint(confirmation):
            raise ValueError('BEA release changed during download; retrying at the next scheduled check')
        probe_hash = fingerprint(panel.loc[panel.index >= (now.year - 1 - 1960) * 12])
    latest = str(pd.Period('1960-01', 'M') + int(panel.index.max()))
    full = rebuild_required(previous_month, latest, full_history or mode == 'benchmark'
                            or baseline_changed or state.get('model_version') != MODEL_VERSION)
    print(f'Calculating {"full benchmark" if full else "incremental update"}; latest {latest}', flush=True)
    new_csvs, new_excels = candidates(panel, list(mapping.haver_code), schema, full)
    csvs, excels, comparisons = {}, {}, []
    data_changed = False
    for file in FILES:
        quarter = 'quarterly' in file
        csvs[file] = merge_frame(previous[file], new_csvs[file], full, quarter)
        excels[file] = merge_frame(previous_excel[file], new_excels[file], full, quarter)
        old, new = previous[file], csvs[file]
        same_dates = list(old.date) == list(new.date)
        same_values = same_dates and np.allclose(old.drop(columns='date'), new.drop(columns='date'),
                                                atol=1e-7, rtol=1e-8, equal_nan=True)
        data_changed |= not same_values
        old_excel, new_excel = previous_excel[file], excels[file]
        same_excel = (list(old_excel.date) == list(new_excel.date)
                      and np.allclose(old_excel.drop(columns='date'), new_excel.drop(columns='date'),
                                      atol=1e-7, rtol=1e-8, equal_nan=True))
        data_changed |= not same_excel
        overlap = old.set_index('date').join(new.set_index('date'), lsuffix='_old', rsuffix='_new', how='inner')
        differences = sum(int((abs(overlap[c + '_old'] - overlap[c + '_new']) > 1e-6).sum()) for c in old.columns[1:])
        comparisons.append(dict(file=file, rows=len(new), overlap_cells=len(overlap) * (len(old.columns) - 1),
                                differences_over_1e_6=differences))
    report = dict(status='validated' if mode == 'validate' else 'updated', latest_month=latest,
                  source='BEA NIUnderlyingDetail U20404, U20405 and U20403', full_history=full,
                  comparisons=comparisons, inputs_sha256=fingerprint(panel), model_version=MODEL_VERSION,
                  changed=False, data_changed=bool(data_changed))
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.sd-export-', dir=root) as folder:
        temp = Path(folder)
        for name, frame in csvs.items():
            frame.to_csv(temp / name, index=False, float_format='%.8g', lineterminator='\n')
        write_frames(excels, root / 'supply_demand_public.xlsx', temp / 'supply_demand_public.xlsx')
        names = list(PUBLIC_FILES)
        if mode != 'validate' and data_changed:
            metadata = release_metadata(latest, datetime.now(timezone.utc), release_utc if latest == expected_month else None)
            (temp / 'data-update.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
            names.append('data-update.json')
        for name in names:
            (output / name).write_bytes((temp / name).read_bytes())
        if mode != 'validate':
            if any((root / name).read_bytes() != raw for name, raw in before.items()):
                raise ValueError('Published files changed during calculation; refusing to overwrite concurrent edits')
            if data_changed:
                for name in names:
                    (temp / name).replace(root / name)
                hashes = {name: file_hash(name, (root / name).read_bytes()) for name in PUBLIC_FILES}
            updated_state = dict(latest_month=latest, model_version=MODEL_VERSION, probe_sha256=probe_hash,
                                 inputs_sha256=fingerprint(panel), published_files_sha256=hashes,
                                 last_full_rebuild_data_month=latest if full else state.get('last_full_rebuild_data_month'),
                                 last_successful_change_utc=datetime.now(timezone.utc).isoformat())
            state_path.write_text(json.dumps(updated_state, indent=2) + '\n', encoding='utf-8')
            report['changed'] = True
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--mode', choices=['validate', 'update', 'benchmark'], default='validate')
    parser.add_argument('--full-history', action='store_true')
    parser.add_argument('--cached-inputs', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'update-artifacts')
    parser.add_argument('--expected-month')
    parser.add_argument('--release-utc')
    args = parser.parse_args()
    report = run(args.root, args.mode, args.full_history, args.cached_inputs, args.output,
                 args.expected_month, args.release_utc)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            for key in ('changed', 'data_changed', 'latest_month'):
                stream.write(f'{key}={str(report[key]).lower()}\n')


if __name__ == '__main__':
    main()
