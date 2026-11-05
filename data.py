"""Portfolio inputs and market-data access. CONFIG contains all assumptions."""
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

BASE_DIR = Path(__file__).resolve().parent
SNAPSHOT_PATH = BASE_DIR / "data" / "prices_snapshot.csv"

# CONFIG — assumptions requiring review before external presentation.
CONFIG = {
    "lookback_years": 3,
    "trading_days": 252,
    "bond_yield": 0.07,  # Illustrative annual compound yield; not a quoted market yield.
    "risk_free_rate": 0.072449,  # CCIL Tenorwise Indicative Yields: 9Y–10Y bucket, 6.94% GS 2036 YTM 7.2449%, dated 04-Nov-2026. Indicative tenor proxy; refresh from CCIL/FBIL/RBI on final submission date.
    "benchmark_ticker": "^NSEI",
    "price_source": "Yahoo Finance (yfinance, auto_adjust=True)",
    "snapshot_file": SNAPSHOT_PATH.name,
    "snapshot_as_of": "2026-11-05",  # Verified maximum date in data/prices_snapshot.csv.
}


def get_portfolio():
    """Return fictional quantities; market-priced holdings have no hardcoded buy price."""
    rows = [
        ("Reliance Industries", "RELIANCE.NS", "Equity", "Energy", 10, None, np.nan),
        ("Tata Consultancy Services", "TCS.NS", "Equity", "IT", 8, None, np.nan),
        ("HDFC Bank", "HDFCBANK.NS", "Equity", "Banking", 15, None, np.nan),
        ("Infosys", "INFY.NS", "Equity", "IT", 12, None, np.nan),
        ("ITC", "ITC.NS", "Equity", "FMCG", 30, None, np.nan),
        ("Nifty 50 ETF", "NIFTYBEES.NS", "Equity ETF", "Index", 25, None, np.nan),
        ("Gold ETF", "GOLDBEES.NS", "Commodity", "Gold", 20, None, np.nan),
        ("Government Bond (illustrative)", "BOND_FIXED", "Bond", "Fixed Income", 1, None, 50000.0),
        ("Cash Reserve", "CASH_FIXED", "Cash", "Cash", 1, None, 20000.0),
    ]
    return pd.DataFrame(rows, columns=[
        "name", "ticker", "asset_class", "sector", "quantity", "purchase_date", "buy_price"
    ])


def _extract_close(raw, ticker):
    """Extract adjusted Close from flat or MultiIndex yfinance output."""
    if raw is None or raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        for level in range(raw.columns.nlevels):
            if "Close" in raw.columns.get_level_values(level):
                frame = raw.xs("Close", axis=1, level=level)
                if isinstance(frame, pd.Series):
                    return frame.rename(ticker)
                if ticker in frame.columns:
                    return frame[ticker].rename(ticker)
                if frame.shape[1] == 1:
                    return frame.iloc[:, 0].rename(ticker)
        return None
    if "Close" not in raw.columns:
        return None
    close = raw["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close.rename(ticker)


@st.cache_data(ttl=3600, show_spinner=False)
def download_market_prices(tickers: tuple, period: str):
    """Download daily adjusted close prices and cache the result for one hour."""
    columns = []
    for ticker in tickers:
        try:
            raw = yf.download(
                ticker, period=period, interval="1d", auto_adjust=True,
                progress=False, threads=False,
            )
            close = _extract_close(raw, ticker)
            if close is not None and close.notna().any():
                columns.append(pd.to_numeric(close, errors="coerce").rename(ticker))
        except Exception:
            continue
    if not columns:
        return pd.DataFrame()
    result = pd.concat(columns, axis=1)
    result.index = pd.to_datetime(result.index).tz_localize(None)
    return result.sort_index().replace([np.inf, -np.inf], np.nan).ffill()


def load_snapshot_prices(path=SNAPSHOT_PATH):
    """Load long-format verified snapshot rows; return empty if file is header-only."""
    if not Path(path).exists():
        return pd.DataFrame(), None
    try:
        frame = pd.read_csv(path, comment="#", parse_dates=["date"])
        if not {"date", "ticker", "adjusted_close"}.issubset(frame.columns) or frame.empty:
            return pd.DataFrame(), None
        frame["adjusted_close"] = pd.to_numeric(frame["adjusted_close"], errors="coerce")
        frame = frame.dropna(subset=["date", "ticker", "adjusted_close"])
        if frame.empty:
            return pd.DataFrame(), None
        prices = frame.pivot_table(
            index="date", columns="ticker", values="adjusted_close", aggfunc="last"
        ).sort_index().ffill()
        return prices, str(frame["date"].max().date())
    except Exception:
        return pd.DataFrame(), None


def load_prices(portfolio):
    """Try Yahoo first, then the committed snapshot; report all unavailable tickers."""
    tickers = tuple(portfolio.loc[
        portfolio["asset_class"].isin(["Equity", "Equity ETF", "Commodity"]), "ticker"
    ].tolist() + [CONFIG["benchmark_ticker"]])
    live = download_market_prices(tickers, period=f"{CONFIG['lookback_years']}y")
    missing = [t for t in tickers if t not in live.columns or live[t].dropna().empty]
    if not missing:
        return live, [], "Yahoo Finance"
    snapshot, as_of = load_snapshot_prices()
    if not snapshot.empty:
        missing_snapshot = [t for t in tickers if t not in snapshot.columns or snapshot[t].dropna().empty]
        return snapshot, missing_snapshot, f"Stored snapshot as of {as_of}"
    return live, missing, "Yahoo Finance (partial)"


def prepare_purchase_basis(portfolio, prices):
    """Set all market holdings to the first common trading date and its adjusted close."""
    result = portfolio.copy()
    market_tickers = result.loc[
        result["asset_class"].isin(["Equity", "Equity ETF", "Commodity"]), "ticker"
    ].tolist()
    available = [ticker for ticker in market_tickers if ticker in prices.columns]
    common = prices.dropna(subset=available) if available else pd.DataFrame()
    if common.empty:
        return result
    purchase_date = common.index[0]
    for idx, row in result.iterrows():
        if row["asset_class"] in ("Equity", "Equity ETF", "Commodity") and row["ticker"] in common:
            result.at[idx, "purchase_date"] = purchase_date.date().isoformat()
            result.at[idx, "buy_price"] = float(common.loc[purchase_date, row["ticker"]])
    return result


def build_portfolio_value_series(portfolio, prices):
    """Sum quantity × market price, accrued bond value, and fixed cash each day."""
    if prices.empty:
        return pd.Series(dtype=float, name="Portfolio value")
    market = portfolio[portfolio["asset_class"].isin(["Equity", "Equity ETF", "Commodity"])]
    # A complete portfolio needs a common start date with a price for every market holding.
    usable = prices.dropna(subset=[t for t in market["ticker"] if t in prices.columns])
    if usable.empty:
        return pd.Series(dtype=float, name="Portfolio value")
    values = pd.Series(0.0, index=usable.index, name="Portfolio value")
    start = usable.index[0]
    for row in portfolio.itertuples(index=False):
        if row.asset_class in ("Equity", "Equity ETF", "Commodity"):
            if row.ticker in usable:
                values += usable[row.ticker] * float(row.quantity)
        elif row.asset_class == "Bond":
            years = (usable.index - start).days / 365.25
            values += float(row.quantity) * float(row.buy_price) * (1 + CONFIG["bond_yield"]) ** years
        elif row.asset_class == "Cash":
            values += float(row.quantity) * float(row.buy_price)
    return values.rename("Portfolio value")


def get_price_status(portfolio, prices, failed):
    """Check completeness against the selected final source (live data or fallback snapshot).

    A ticker that failed live download is not missing if the fallback snapshot supplies it.
    """
    rows = portfolio[portfolio["asset_class"].isin(["Equity", "Equity ETF", "Commodity"])]
    missing = sorted({
        r.ticker for r in rows.itertuples()
        if r.ticker not in prices.columns or prices[r.ticker].dropna().empty
    })
    return not missing, missing
