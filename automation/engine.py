"""Supply/demand decomposition matching the specified JMCB Stata programs."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
import json
import hashlib

FOOD_ENERGY = set('nlgom nlglm nofum noflm nfofm nfonm nfoldm nfolem nfolbm nfefm slem slgm'.split())
PARTS = ('demHH', 'demH', 'demL', 'supHH', 'supH', 'supL', 'amb')


def calculate(panel: pd.DataFrame, categories: list[str], dates: list[int], quarterly: bool = False) -> pd.DataFrame:
    if quarterly:
        panel = panel.groupby(panel.index // 3).mean()
    panel = panel.sort_index()
    panel.index.name = 'time_month'
    if panel.index.has_duplicates or not np.all(np.diff(panel.index) == 1):
        raise ValueError('Input calendar must be unique and consecutive')
    lag, window = (4, 40) if quarterly else (12, 120)
    p = panel[categories].to_numpy(dtype=float)
    q = panel[[c + '_quant' for c in categories]].to_numpy(dtype=float)
    expense = panel[[c + '_spend' for c in categories]].to_numpy(dtype=float)
    with np.errstate(invalid='ignore', divide='ignore'):
        plog = np.log(p).astype('float32').astype(float)
        qlog = np.log(q)
        inflation = ((p[1:] - p[:-1]) / p[:-1]).astype('float32').astype(float)
    inflation = np.vstack([np.full((1, len(categories)), np.nan), inflation])
    current = np.stack([qlog, plog], axis=2)
    x = np.full((len(panel), len(categories), 2 * lag), np.nan)
    for j in range(1, lag + 1):
        x[j:, :, j - 1] = qlog[:-j]
        x[j:, :, lag + j - 1] = plog[:-j]
    group_indices = {
        'all': list(range(len(categories))),
        'goods': list(range(categories.index('nrpm') + 1)),
        'services': list(range(categories.index('sbom'), len(categories))),
        'hous': [categories.index(c) for c in 'shrm shtm srdm shom'.split()],
    }
    results = []
    legacy = json.loads(Path(__file__).with_name('historical-zero-ties.json').read_text())['records']
    ties = {}
    for record in legacy:
        if record['frequency'] == ('quarterly' if quarterly else 'monthly'):
            ties.setdefault(record['time'], []).append(record)
    for date in dates:
        t = panel.index.get_loc(date)
        start = max(0, t - window)
        scores = np.empty((len(categories), 2))
        for c in range(len(categories)):
            xx, yy = x[start:t + 1, c], current[start:t + 1, c]
            valid = np.isfinite(xx).all(axis=1) & np.isfinite(yy).all(axis=1)
            if not valid[-1] or valid.sum() <= 2 * lag + 1:
                raise ValueError(f'Insufficient model data for {categories[c]} at {date}')
            xx, yy = xx[valid], yy[valid]
            xc, yc = xx - xx.mean(axis=0), yy - yy.mean(axis=0)
            beta = np.linalg.lstsq(xc, yc, rcond=None)[0]
            errors = (yc - xc @ beta).astype('float32').astype(float)
            sd = errors.std(axis=0, ddof=1)
            if not np.isfinite(sd).all():
                raise ValueError(f'Invalid residual dispersion for {categories[c]} at {date}')
            with np.errstate(divide='ignore', invalid='ignore'):
                score = (errors[-1] / sd).astype('float32')
            # Rounded historical quantity indexes can be constant (e.g. early
            # computer quantities). Stata's resulting missing t-score compares
            # greater than finite positive thresholds. Preserve that convention.
            score[(np.ptp(yy, axis=0) == 0) | ~np.isfinite(score)] = np.inf
            scores[c] = score
        same = (scores[:, 0] > 0) == (scores[:, 1] > 0)
        strength = np.min(np.abs(scores), axis=1)
        for record in ties.get(date, []):
            c = record['category']
            frame = panel.loc[date - window - lag:date, [c, c + '_quant']]
            signature = hashlib.sha256(frame.to_csv(float_format='%.12g', lineterminator='\n').encode()).hexdigest()
            if signature != record['input_sha256'] or strength[categories.index(c)] >= 1e-4:
                raise ValueError(f'Historical numerical-tie inputs changed for {c} at {date}; review required')
        row = {'time': date}
        for aggregate, denominator in [('hdln', 'pce_spend'), ('core', 'core_spend')]:
            members = set(categories) if aggregate == 'hdln' else set(categories) - FOOD_ENERGY
            if not np.isfinite(panel.at[panel.index[t - 1], denominator]) or panel.at[panel.index[t - 1], denominator] <= 0:
                raise ValueError('Invalid aggregate spending')
            contribution = ((expense[t - 1] / panel.at[panel.index[t - 1], denominator]) * inflation[t]).astype('float32')
            if not np.isfinite(contribution).all():
                raise ValueError('Missing category inflation or expenditures')
            for variant, cutoff in [('base', 0.0), ('amb', 0.10)]:
                masks = {
                    'demHH': same & (strength > .30),
                    'demH': same & (strength > .15) & (strength <= .30),
                    'demL': same & (strength > cutoff) & (strength <= .15),
                    'supHH': ~same & (strength > .30),
                    'supH': ~same & (strength > .15) & (strength <= .30),
                    'supL': ~same & (strength > cutoff) & (strength <= .15),
                    'amb': strength <= cutoff,
                }
                if variant == 'base':
                    for record in ties.get(date, []):
                        index = categories.index(record['category'])
                        for part, mask in masks.items():
                            mask[index] = part == record['classification']
                for group, indices in group_indices.items():
                    idx = [i for i in indices if categories[i] in members]
                    for part, mask in masks.items():
                        row[f'{variant}_{aggregate}_{group}_{part}'] = float(np.cumsum(contribution[idx] * mask[idx], dtype='float32')[-1])
                for part in PARTS:
                    row[f'{variant}_{aggregate}_serv_ex_hous_{part}'] = float(np.float32(
                        row[f'{variant}_{aggregate}_services_{part}'] - row[f'{variant}_{aggregate}_hous_{part}']))
        results.append(row)
    return pd.DataFrame(results).set_index('time')


def annual_parts(raw: pd.DataFrame, periods: int) -> pd.DataFrame:
    product = np.ones(raw.shape, dtype='float32')
    values = raw.to_numpy(dtype=float)
    for lag in range(periods):
        shifted = np.full_like(values, np.nan)
        if lag:
            shifted[lag:] = values[:-lag]
        else:
            shifted = values
        product = ((1 + shifted) * product.astype(float)).astype('float32')
    return pd.DataFrame((product.astype(float) - 1).astype('float32'), index=raw.index, columns=raw.columns)
