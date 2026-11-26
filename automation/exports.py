"""Preserve the six CSV schemas, Stata rounding and Excel units."""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine import annual_parts

FILES = {
    'supply_demand_baseline.csv': 'Baseline',
    'supply_demand_ambiguous.csv': 'Ambiguous',
    'supply_demand_quarterly.csv': 'Quarterly',
    'supply_demand_goods_services.csv': 'Goods_Services',
    'supply_demand_goods_services_ambiguous.csv': 'Goods_Services_Ambiguous',
    'supply_demand_precision.csv': 'Precision',
}


def f32(values):
    return np.asarray(values).astype('float32').astype(float)


def stata_round(values, step):
    values = np.asarray(values, dtype=float)
    return np.floor(values / step + .5) * step


def string_round(values):
    """main_publicdata.do's string(), substring, then double cent rounding."""
    output = []
    for value in values:
        if not np.isfinite(value):
            output.append(np.nan)
            continue
        text = format(float(value), '.7g')
        if text.startswith('0.'):
            text = text[1:]
        elif text.startswith('-0.'):
            text = '-' + text[2:]
        text = text[:4 if value >= 1 else 5]
        output.append(float(stata_round(float(text), .01)))
    return np.array(output)


def build(raw: pd.DataFrame, schema: dict[str, list[str]], quarterly: bool = False):
    raw = raw.astype('float32').astype(float)
    years = annual_parts(raw, 4 if quarterly else 12)
    csvs, excels = {}, {}
    for file, columns in schema.items():
        if ('quarterly' in file) != quarterly:
            continue
        is_group = 'goods_services' in file
        precise = 'precision' in file
        ambiguous = precise or 'ambiguous' in file
        variant = 'amb' if ambiguous else 'base'
        fields = {}
        excel_fields = {}
        for name in columns:
            if name == 'date':
                continue
            tokens = name.split('_')
            side, aggregate, period = tokens[0], tokens[-2], tokens[-1]
            group = '_'.join(tokens[1:-2]) if is_group else 'all'
            part = side + tokens[1] if precise and side != 'amb' else side
            names = [part] if part not in ('dem', 'sup') else [part + k for k in ('HH', 'H', 'L')]
            source = years if period == 'yoy' else raw
            pieces = source[[f'{variant}_{aggregate}_{group}_{p}' for p in names]].to_numpy()
            # Aggregate years sum stored components before scaling; the GS
            # script scales the components before assigning the combined float.
            values = pieces.sum(axis=1)
            if period == 'yoy':
                values = f32(values * 100) if is_group else f32(f32(values) * 100)
            else:
                values = f32(values)
            if not is_group and not quarterly:
                values = f32(stata_round(values, .01)) if period == 'yoy' else f32(100 * stata_round(values, .00001))
                if not precise:
                    values = string_round(values)
            elif is_group and period == 'mom':
                values = f32(values * 100)
            excel_fields[name] = values
            # Quarterly Excel intentionally stores q/q fractions; the CSV
            # export multiplies them by 100 for the dashboard's percentage points.
            fields[name] = f32(values * 100) if quarterly and period == 'qoq' else values
        dates = [f'{1960 + int(t)//4}q{int(t)%4+1}' if quarterly else
                 f'{1960 + int(t)//12}m{int(t)%12+1}' for t in raw.index]
        csvs[file] = pd.DataFrame({'date': dates, **fields}, index=raw.index)[columns]
        excels[file] = pd.DataFrame({'date': dates, **excel_fields}, index=raw.index)[columns]
    return csvs, excels
