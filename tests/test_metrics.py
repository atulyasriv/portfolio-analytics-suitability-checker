import numpy as np
import pandas as pd
from metrics import annualised_return, annualised_volatility, daily_portfolio_returns, maximum_drawdown, beta_vs_benchmark, sharpe_geometric
from profiles import check_suitability


def test_constant_daily_return_closed_form_and_zero_volatility():
    r = pd.Series([0.01] * 252)
    assert np.isclose(annualised_return(r), 1.01**252 - 1)
    assert np.isclose(annualised_volatility(r), 0.0)
    assert np.isnan(sharpe_geometric(r, 0.06))


def test_known_up_down_max_drawdown():
    # Portfolio value: 100 -> 120 -> 90 -> 110; peak-to-trough loss is 30/120 = 25%.
    values = pd.Series([100.0, 120.0, 90.0, 110.0])
    daily_returns = daily_portfolio_returns(values)
    assert np.isclose(maximum_drawdown(daily_returns), -0.25)


def test_beta_of_benchmark_against_itself_is_one():
    b = pd.Series([.01, -.02, .03, 0, .02])
    assert np.isclose(beta_vs_benchmark(b, b), 1.0)


def test_buy_and_hold_return_reconciles_to_product_of_daily_returns():
    value = pd.Series([100., 110., 99., 108.9])
    r = daily_portfolio_returns(value)
    assert np.isclose(value.iloc[-1]/value.iloc[0]-1, (1+r).prod()-1)


def make_snapshot(equities, bond=0, cash=0, gold=0):
    rows=[{"name":n,"asset_class":"Equity","sector":s,"current_value":v} for n,v,s in equities]
    rows += [
        {"name":"Bond","asset_class":"Bond","sector":"Fixed Income","current_value":bond},
        {"name":"Cash","asset_class":"Cash","sector":"Cash","current_value":cash},
        {"name":"Gold","asset_class":"Commodity","sector":"Gold","current_value":gold},
    ]
    return pd.DataFrame(rows)


def test_conservative_flags_90pct_equity_and_accepts_within_range():
    too_equity=make_snapshot([("Stock A",90,"Technology")],bond=10)
    result=check_suitability(too_equity,"A — Conservative",.05)
    assert result["status"]=="Review"
    assert "Equity allocation" in " ".join(result["reasons"])
    within=make_snapshot([("Stock A",8,"Tech"),("Stock B",8,"Health")],bond=55,cash=25)
    assert check_suitability(within,"A — Conservative",.05)["status"]=="OK"


def test_bond_is_not_counted_in_equity_concentration():
    snapshot=make_snapshot([("Stock A",20,"Tech"),("Stock B",10,"Health")],bond=70)
    result=check_suitability(snapshot,"B — Moderate",.05)
    actual=result["table"].set_index("Rule").loc["Largest equity holding","Actual"]
    assert actual=="20.0%"


def test_partial_prices_force_review_with_partial_message():
    snapshot=make_snapshot([("Stock A",20,"Tech")],bond=50,cash=30)
    result=check_suitability(snapshot,"B — Moderate",.10,partial=True)
    assert result["status"]=="Review"
    assert "Partial data" in result["reasons"][0]
