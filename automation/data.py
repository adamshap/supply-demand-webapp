"""Public BEA inputs for the 130-category supply/demand models."""
import pandas as pd


def inputs(prices: pd.DataFrame, spending: pd.DataFrame, quantities: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    if not (prices.index.max() == spending.index.max() == quantities.index.max()):
        raise ValueError('BEA price, spending and quantity tables are not on the same release yet')
    if len(mapping) != 130 or mapping.haver_code.duplicated().any():
        raise ValueError('Expected 130 unique category mappings')
    values = {'pce': prices.DPCERG, 'pce_spend': spending.DPCERC, 'core_spend': spending.DPCCRC}
    for row in mapping.itertuples():
        values[row.haver_code] = prices[row.bea_price]
        values[row.haver_code + '_spend'] = -spending[row.bea_spending] if row.subtract else spending[row.bea_spending]
        values[row.haver_code + '_quant'] = quantities[row.bea_price[:-2] + 'RA']
    panel = pd.DataFrame(values).sort_index()
    panel.index.name = 'time_month'
    if panel.empty or panel.iloc[-1].isna().any():
        raise ValueError('BEA release is incomplete for one or more required categories')
    return panel
