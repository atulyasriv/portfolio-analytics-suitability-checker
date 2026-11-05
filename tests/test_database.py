import numpy as np
import pandas as pd

from database import (
    refresh_database, query_current_holdings, query_allocation,
    query_sector_concentration, query_daily_analytics, query_profile_rules,
)
from profiles import PROFILES


def _sample_inputs(include_fixed_values=True):
    dates = pd.date_range("2024-01-01", periods=4, freq="B")
    prices = pd.DataFrame({
        "AAA": [50.0, 60.0, 45.0, 55.0],
        "BBB": [10.0, 10.0, 10.0, 10.0],
    }, index=dates)
    bond_principal = 20000.0 if include_fixed_values else 0.0
    cash_principal = 10000.0 if include_fixed_values else 0.0
    portfolio = pd.DataFrame([
        {"name":"Alpha Ltd","ticker":"AAA","asset_class":"Equity","sector":"Technology",
         "quantity":2.0,"purchase_date":None,"buy_price":np.nan},
        {"name":"Beta Ltd","ticker":"BBB","asset_class":"Equity","sector":"Healthcare",
         "quantity":0.0,"purchase_date":None,"buy_price":np.nan},
        {"name":"Illustrative bond","ticker":"BOND_FIXED","asset_class":"Bond","sector":"Fixed Income",
         "quantity":1.0,"purchase_date":None,"buy_price":bond_principal},
        {"name":"Cash","ticker":"CASH_FIXED","asset_class":"Cash","sector":"Cash",
         "quantity":1.0,"purchase_date":None,"buy_price":cash_principal},
    ])
    return portfolio, prices


def test_sql_current_values_allocation_and_sector_weights(tmp_path):
    portfolio, prices = _sample_inputs()
    db = tmp_path / "portfolio.db"
    refresh_database(portfolio, prices, PROFILES, db, 0.07)

    holdings = query_current_holdings(db, 0.07)
    alpha = holdings.set_index("ticker").loc["AAA"]
    assert np.isclose(alpha["current_value"], 110.0)
    assert np.isclose(holdings["weight"].sum(), 1.0)
    bond_value = holdings.set_index("ticker").loc["BOND_FIXED", "current_value"]
    expected_bond = 20000.0 * (1.07 ** ((prices.index[-1] - prices.index[0]).days / 365.25))
    assert np.isclose(bond_value, expected_bond)

    allocation = query_allocation(db, 0.07)
    assert np.isclose(allocation["weight"].sum(), 1.0)
    assert set(allocation["asset_class"]) == {"Equity", "Bond", "Cash"}

    sectors = query_sector_concentration(db, 0.07)
    assert set(sectors["sector"]) == {"Technology", "Healthcare"}
    total_portfolio = holdings["current_value"].sum()
    equity_total = holdings.loc[holdings.asset_class.isin(["Equity", "Equity ETF"]), "current_value"].sum()
    assert np.isclose(sectors["weight"].sum(), equity_total / total_portfolio)
    assert np.isclose(
        sectors.set_index("sector").loc["Technology", "weight"],
        holdings.set_index("ticker").loc["AAA", "current_value"] / total_portfolio,
    )


def test_sql_lag_returns_and_running_peak_drawdown(tmp_path):
    portfolio, prices = _sample_inputs(include_fixed_values=False)
    db = tmp_path / "portfolio.db"
    refresh_database(portfolio, prices, PROFILES, db, 0.07)

    daily = query_daily_analytics(db, 0.07)
    assert len(daily) == 4
    assert np.isnan(daily["daily_return"].iloc[0])
    assert np.isclose(daily["daily_return"].iloc[1], 0.20)
    assert np.isclose(daily["daily_return"].iloc[2], -0.25)
    assert np.isclose(daily["drawdown"].min(), -0.25)


def test_sql_profile_rules_are_persisted(tmp_path):
    portfolio, prices = _sample_inputs()
    db = tmp_path / "portfolio.db"
    refresh_database(portfolio, prices, PROFILES, db, 0.07)
    rules = query_profile_rules(db, "B — Moderate")
    assert rules["equity_max_pct"] == 65.0
    assert rules["max_volatility"] == 0.18



def test_missing_market_ticker_is_null_safe_across_all_sql_queries(tmp_path):
    """A missing ticker leaves no common date; SQL must return partial rows, not crash."""
    portfolio, prices = _sample_inputs()
    prices = prices.drop(columns=["BBB"])
    db = tmp_path / "partial_portfolio.db"
    refresh_database(portfolio, prices, PROFILES, db, 0.07)

    holdings = query_current_holdings(db, 0.07)
    allocation = query_allocation(db, 0.07)
    sectors = query_sector_concentration(db, 0.07)
    daily = query_daily_analytics(db, 0.07)

    # The unpriced market holding remains visible as NULL/NaN, while fixed holdings
    # are still returned with unavailable bond accrual where dates cannot be inferred.
    assert set(holdings["ticker"]) == set(portfolio["ticker"])
    assert pd.isna(holdings.set_index("ticker").loc["AAA", "current_value"])
    assert pd.isna(holdings.set_index("ticker").loc["BBB", "current_value"])
    assert not allocation.empty
    assert not sectors.empty
    assert daily.empty
