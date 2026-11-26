"""Prepare public BEA stress-test inputs for the native Stata reference scripts."""
from pathlib import Path
import argparse
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'automation/tests'))
from revision_scenarios import scenario

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(ROOT / 'automation/tests/fixtures/bea_2026_10.csv.gz', index_col='time_month')
    categories = list(pd.read_csv(ROOT / 'automation/categories.csv').haver_code)
    for name in ('original', 'rebase', 'historical_revision', 'benchmark_revision'):
        revised = scenario(panel, categories, name)
        revised.reset_index().to_stata(args.output / f'{name}.dta', write_index=False, version=118)
