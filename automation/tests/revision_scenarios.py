"""Deterministic public-data revisions for independent Stata parity checks."""
import numpy as np


def scenario(panel, categories, name):
    result = panel.copy()
    if name in ('rebase', 'benchmark_revision'):
        for i, c in enumerate(categories):
            result[c] *= 1.2 + (i % 7) * .03
            result[c + '_quant'] *= .7 + (i % 5) * .08
    if name in ('historical_revision', 'benchmark_revision'):
        # Give previously rounded-flat quantities genuine historical variation.
        history = result.index <= 150
        t = result.index[history].to_numpy()
        result.loc[history, 'drgim_quant'] *= 1 + .02 * np.sin(t * 1.731)
        result.loc[history, 'drgim'] *= 1 + .001 * np.cos(t * .921)
    if name == 'benchmark_revision':
        recent = result.index >= result.index.max() - 24
        t = np.arange(int(recent.sum()))
        for i, c in enumerate(categories):
            result.loc[recent, c] *= 1 + .0005 * np.sin(t + i)
            result.loc[recent, c + '_quant'] *= 1 + .0008 * np.cos(t * .7 + i)
    if name not in ('original', 'rebase', 'historical_revision', 'benchmark_revision'):
        raise ValueError(name)
    return result
