"""Financial metrics. Each function documents its formula in plain English."""
import numpy as np
import pandas as pd


def daily_portfolio_returns(portfolio_values):
    """Daily return = today's total buy-and-hold value / yesterday's total value − 1.

    Value includes quantity × adjusted price for every market holding, accrued bond value,
    and fixed cash. It assumes buy-and-hold, no rebalancing, and no cash flows.
    """
    return portfolio_values.astype(float).pct_change().replace([np.inf, -np.inf], np.nan).dropna()


def annualised_return(daily_returns, trading_days=252):
    """Geometric annual return = product of (1 + each daily return) raised to 252 / days, minus 1."""
    r = daily_returns.dropna()
    if r.empty or (1 + r).prod() <= 0:
        return float("nan")
    return float((1 + r).prod() ** (trading_days / len(r)) - 1)


def annualised_volatility(daily_returns, trading_days=252):
    """Annual volatility = sample standard deviation of daily returns × square root of 252."""
    r = daily_returns.dropna()
    return float(r.std(ddof=1) * np.sqrt(trading_days)) if len(r) >= 2 else float("nan")


def sharpe_geometric(daily_returns, risk_free_rate, trading_days=252):
    """Geometric Sharpe = (geometric annual return − annual risk-free rate) / annual volatility."""
    if risk_free_rate is None:
        return float("nan")
    ret, vol = annualised_return(daily_returns, trading_days), annualised_volatility(daily_returns, trading_days)
    return float((ret - risk_free_rate) / vol) if np.isfinite(ret) and np.isfinite(vol) and vol else float("nan")


def sharpe_standard(daily_returns, risk_free_rate, trading_days=252):
    """Standard Sharpe = mean daily excess return × 252 / (daily standard deviation × square root of 252)."""
    r = daily_returns.dropna()
    if risk_free_rate is None or len(r) < 2:
        return float("nan")
    daily_rf = (1 + risk_free_rate) ** (1 / trading_days) - 1
    excess, sd = r - daily_rf, r.std(ddof=1)
    return float(excess.mean() * trading_days / (sd * np.sqrt(trading_days))) if sd else float("nan")


def drawdown_series(daily_returns):
    """Daily drawdown = cumulative wealth / highest previous cumulative wealth − 1."""
    r = daily_returns.dropna()
    if r.empty:
        return pd.Series(dtype=float, name="Drawdown")
    wealth = (1 + r).cumprod()
    return (wealth / wealth.cummax() - 1).rename("Drawdown")


def maximum_drawdown(daily_returns):
    """Maximum drawdown = the most negative value in the daily peak-to-trough drawdown series."""
    dd = drawdown_series(daily_returns)
    return float(dd.min()) if not dd.empty else float("nan")


def maximum_drawdown_date(daily_returns):
    """Return the date and depth of the lowest point in the peak-to-trough drawdown series."""
    dd = drawdown_series(daily_returns)
    return (dd.idxmin(), float(dd.min())) if not dd.empty else (None, float("nan"))


def correlation_matrix(holding_values):
    """Correlation = covariance of two holding return series divided by their standard deviations."""
    return holding_values.pct_change().replace([np.inf, -np.inf], np.nan).corr() if not holding_values.empty else pd.DataFrame()


def beta_vs_benchmark(portfolio_returns, benchmark_returns):
    """Beta = covariance(portfolio daily returns, benchmark daily returns) / benchmark return variance."""
    pair = pd.concat([portfolio_returns.rename("p"), benchmark_returns.rename("b")], axis=1).dropna()
    if len(pair) < 2 or pair["b"].var(ddof=1) == 0:
        return float("nan")
    return float(pair["p"].cov(pair["b"]) / pair["b"].var(ddof=1))


def cumulative_growth(daily_returns, label):
    """Growth of ₹1 = multiply (1 + each daily return) cumulatively through time."""
    return (1 + daily_returns.dropna()).cumprod().rename(label)


def historical_var(daily_returns, confidence=0.95):
    """One-day historical VaR = negative empirical 5th percentile of daily returns at 95% confidence."""
    r = daily_returns.dropna()
    return float(-r.quantile(1 - confidence)) if len(r) else float("nan")


def historical_var_10d(daily_returns, confidence=0.95):
    """Ten-day historical VaR = negative 5th percentile of overlapping compounded 10-day returns."""
    r = daily_returns.dropna()
    if len(r) < 10:
        return float("nan")
    ten_day = (1 + r).rolling(10).apply(np.prod, raw=True) - 1
    return float(-ten_day.dropna().quantile(1 - confidence))


def rolling_volatility(daily_returns, window=60, trading_days=252):
    """Rolling annual volatility = rolling daily sample standard deviation × square root of 252."""
    return daily_returns.rolling(window).std(ddof=1) * np.sqrt(trading_days)


def tracking_error(portfolio_returns, benchmark_returns, trading_days=252):
    """Tracking error = standard deviation of daily active returns × square root of 252."""
    pair = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
    if len(pair) < 2:
        return float("nan")
    return float((pair.iloc[:, 0] - pair.iloc[:, 1]).std(ddof=1) * np.sqrt(trading_days))


def information_ratio(portfolio_returns, benchmark_returns, trading_days=252):
    """Information ratio = mean daily active return × 252 / annualised tracking error."""
    pair = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
    if len(pair) < 2:
        return float("nan")
    active = pair.iloc[:, 0] - pair.iloc[:, 1]
    te = active.std(ddof=1) * np.sqrt(trading_days)
    return float(active.mean() * trading_days / te) if te else float("nan")


def best_worst_day(daily_returns):
    """Return the maximum and minimum observed one-day portfolio returns."""
    r = daily_returns.dropna()
    return (float(r.max()), float(r.min())) if len(r) else (float("nan"), float("nan"))


def portfolio_snapshot(portfolio, prices, bond_yield):
    """Create current values and since-basis returns using a shared common inception date."""
    rows = []
    market_tickers = portfolio.loc[
        portfolio["asset_class"].isin(["Equity", "Equity ETF", "Commodity"]), "ticker"
    ].tolist()
    available = [ticker for ticker in market_tickers if ticker in prices.columns]
    common = prices.dropna(subset=available) if available and not prices.empty else pd.DataFrame()
    first_date = common.index[0] if not common.empty else None
    last_date = common.index[-1] if not common.empty else None
    for row in portfolio.itertuples(index=False):
        if row.asset_class in ("Equity", "Equity ETF", "Commodity"):
            if first_date is None or row.ticker not in common.columns:
                cost = current = np.nan
                purchase_date = None
            else:
                cost = float(common.loc[first_date, row.ticker] * row.quantity)
                current = float(common.loc[last_date, row.ticker] * row.quantity)
                purchase_date = first_date.date().isoformat()
        elif row.asset_class == "Bond":
            cost = float(row.quantity * row.buy_price)
            years = max((last_date - first_date).days / 365.25, 0) if first_date is not None else 0
            current = cost * (1 + bond_yield) ** years
            purchase_date = first_date.date().isoformat() if first_date is not None else None
        else:
            cost = current = float(row.quantity * row.buy_price)
            purchase_date = None
        rows.append({
            "name": row.name, "ticker": row.ticker, "asset_class": row.asset_class,
            "sector": row.sector, "quantity": float(row.quantity),
            "purchase_date": purchase_date, "cost": cost, "current_value": current,
            "return_pct": (current / cost - 1) * 100
            if pd.notna(current) and pd.notna(cost) and cost else np.nan,
        })
    return pd.DataFrame(rows)


def stress_test(snapshot, scenarios):
    """Stress value change = sum of each holding's current value × assumed asset-class shock."""
    total = snapshot["current_value"].sum(min_count=1)
    class_key = {"Equity": "equity", "Equity ETF": "equity", "Commodity": "gold", "Bond": "bond", "Cash": "cash"}
    out = []
    for name, shocks in scenarios.items():
        change = sum(float(r.current_value) * shocks.get(class_key[r.asset_class], 0.0)
                     for r in snapshot.itertuples(index=False))
        out.append({"Scenario": name, "Change (₹)": change,
                    "Change (%)": change / total if total else np.nan,
                    "Stressed value (₹)": total + change})
    return pd.DataFrame(out)
