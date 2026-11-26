from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'automation'))
from ols_precision import standardized_residuals, unit_leverage_rows
from revision_scenarios import scenario


def classification(score, cutoff):
    q, p = score
    strength = min(abs(q), abs(p))
    if strength <= cutoff:
        return 'amb'
    side = 'dem' if (q > 0) == (p > 0) else 'sup'
    return side + ('HH' if strength > .30 else 'H' if strength > .15 else 'L')


class PrecisionTests(unittest.TestCase):
    def test_exact_fit_is_zero_and_rebasing_preserves_the_projection(self):
        n = 40
        x = np.column_stack([np.linspace(-1, 1, n), np.r_[np.zeros(n - 1), 1.]])
        y = np.random.default_rng(42).normal(size=(n, 2))
        score, unit = standardized_residuals(x, y)
        self.assertTrue(unit[-1])
        np.testing.assert_array_equal(score, [0, 0])
        np.testing.assert_array_equal(unit, unit_leverage_rows(x * [3.4, .7] + [17, -2]))

    def test_small_real_residuals_and_near_unit_observations_are_retained(self):
        n = 40
        x = np.column_stack([np.linspace(-1, 1, n), np.r_[np.zeros(n - 2), .01, 1.]])
        self.assertFalse(unit_leverage_rows(x)[-1])
        y = np.random.default_rng(43).normal(size=(n, 2))
        y[-1, 0] = y[:-1, 0].mean() + 1e-12
        score, unit = standardized_residuals(np.ones((n, 1)), y)
        self.assertFalse(unit[-1])
        self.assertGreater(score[0], 0)
        self.assertLess(score[0], 1e-10)

    def test_independent_stata_reference_on_original_revised_and_rebased_inputs(self):
        fixture = Path(__file__).parent / 'fixtures'
        original = pd.read_csv(fixture / 'bea_2026_10.csv.gz', index_col='time_month')
        categories = list(pd.read_csv(ROOT / 'automation/categories.csv').haver_code)
        reference = pd.read_csv(fixture / 'stata_revision_reference.csv.gz')
        self.assertEqual(len(reference), 9360)
        checked, revised_normal = 0, 0
        for name, scenario_rows in reference.groupby('scenario'):
            revised = scenario(original, categories, name)
            for frequency, rows in scenario_rows.groupby('freq'):
                data = revised.groupby(revised.index // 3).mean() if frequency == 'Q' else revised
                lag, window = (4, 40) if frequency == 'Q' else (12, 120)
                plog = np.log(data[categories].to_numpy()).astype('float32').astype(float)
                qlog = np.log(data[[c + '_quant' for c in categories]].to_numpy())
                targets = np.stack([qlog, plog], axis=2)
                lags = np.full((len(data), len(categories), 2 * lag), np.nan)
                for j in range(1, lag + 1):
                    lags[j:, :, j - 1], lags[j:, :, lag + j - 1] = qlog[:-j], plog[:-j]
                for row in rows.itertuples():
                    t, c = data.index.get_loc(row.time), categories.index(row.category)
                    x, y = lags[max(0, t - window):t + 1, c], targets[max(0, t - window):t + 1, c]
                    valid = np.isfinite(x).all(axis=1) & np.isfinite(y).all(axis=1)
                    score, unit = standardized_residuals(x[valid], y[valid])
                    expected = np.array([row.q, row.p])
                    expected[np.isnan(expected)] = np.inf  # Stata missing compares above positive cutoffs.
                    self.assertEqual(bool(unit[-1]), bool(row.unitq))
                    self.assertEqual(bool(row.unitq), bool(row.unitp))
                    for cutoff in (0, .10):
                        self.assertEqual(classification(score, cutoff), classification(expected, cutoff),
                                         f'{name} {frequency} {row.time} {row.category}')
                        checked += 1
                    if name == 'historical_revision' and row.category == 'drgim' and row.time < 150 and not unit[-1]:
                        revised_normal += 1
        self.assertEqual(checked, 18720)
        self.assertGreater(revised_normal, 0)
