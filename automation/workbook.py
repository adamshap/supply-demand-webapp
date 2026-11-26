"""Export the six existing Excel sheets while retaining labels and cell formats."""
from copy import copy
from pathlib import Path
import re

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from exports import FILES


def month_number(value: str) -> int:
    year, month = value.split('m')
    return (int(year) - 1960) * 12 + int(month) - 1


def quarter_number(value: str) -> int:
    year, quarter = value.split('q')
    return (int(year) - 1960) * 4 + int(quarter) - 1


def dates(values, quarterly=False):
    output = []
    for value in values:
        year, period = re.split('[mq]', value)
        output.append(pd.Timestamp(int(year), (int(period) - 1) * 3 + 1 if quarterly else int(period), 1))
    return output


def read_frames(path: Path, schema: dict) -> dict:
    frames = {}
    with pd.ExcelFile(path) as book:
        if set(book.sheet_names) != set(FILES.values()):
            raise ValueError('Unexpected Excel sheet set')
        for file, sheet in FILES.items():
            frame = book.parse(sheet)
            if len(frame.columns) != len(schema[file]):
                raise ValueError('Excel columns do not match the dashboard schema')
            frame.columns = schema[file]
            dt = pd.to_datetime(frame.date)
            if sheet == 'Quarterly':
                frame['date'] = [f'{d.year}q{d.quarter}' for d in dt]
            else:
                frame['date'] = [f'{d.year}m{d.month}' for d in dt]
            frames[file] = frame
    return frames


def write_frames(frames: dict, template: Path, destination: Path) -> None:
    book = load_workbook(template)
    for file, sheet in FILES.items():
        ws = book[sheet]
        styles = [copy(cell._style) for cell in ws[2]]
        frame = frames[file].copy()
        frame['date'] = dates(frame.date, sheet == 'Quarterly')
        ws.delete_rows(2, ws.max_row - 1)
        for row in frame.itertuples(index=False, name=None):
            ws.append([None if pd.isna(value) else value.to_pydatetime() if isinstance(value, pd.Timestamp) else float(value) if isinstance(value, np.number) else value for value in row])
        for row in ws.iter_rows(min_row=2):
            for cell, style in zip(row, styles):
                cell._style = copy(style)
        ws.freeze_panes = 'B2'
    book.save(destination)
    # Reopen the actual output and check every sheet's dates and numerical values.
    schema = {name: list(frame.columns) for name, frame in frames.items()}
    check = read_frames(destination, schema)
    for file, frame in frames.items():
        actual = check[file]
        if list(actual.date) != list(frame.date) or not np.allclose(actual.drop(columns='date'), frame.drop(columns='date'), atol=1e-10, rtol=1e-12, equal_nan=True):
            raise ValueError(f'Excel round-trip verification failed for {file}')
