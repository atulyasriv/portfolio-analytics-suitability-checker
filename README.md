# Portfolio Analytics & Suitability Checker

A Python and Streamlit portfolio research application for an illustrative Indian-market portfolio. It combines adjusted-price history, a SQLite analytics layer, historical risk measures, Nifty 50 comparison, scenario analysis, and transparent checks against fictional investor mandates.

> **Important:** This is an educational portfolio analytics project, not investment advice, a suitability engine approved by a regulator, or a Morgan Stanley product. Holdings, quantities, and investor profiles are illustrative. Market data is sourced from Yahoo Finance through `yfinance`; verify all inputs before relying on any output.

## What it does

- Values seven market-priced holdings and illustrative bond/cash positions.
- Uses a three-year adjusted-close history for Reliance, TCS, HDFC Bank, Infosys, ITC, NIFTYBEES, GOLDBEES, and the Nifty 50 benchmark (`^NSEI`).
- Compares portfolio performance with the Nifty 50 over aligned observations.
- Calculates annualised return and volatility, geometric and standard Sharpe ratios, maximum drawdown, beta, historical VaR, rolling volatility, tracking error, information ratio, and best/worst day.
- Shows asset allocation, sector concentration, holding correlations, and hypothetical stress scenarios.
- Checks the portfolio against Conservative, Moderate, and Aggressive **fictional** mandate thresholds and explains each result.
- Allows session-only quantity edits and refreshes the session's SQLite database from the selected inputs.

## Technology

| Layer | Tools |
|---|---|
| UI | Streamlit |
| Analytics | Python, pandas, NumPy |
| Visualisation | Plotly |
| Data | yfinance, CSV snapshot fallback |
| Database | SQLite via Python `sqlite3` |
| Testing | pytest |

## Project structure

```text
portfolio_analytics_suitability_v2/
├── app.py
├── data.py
├── database.py
├── metrics.py
├── profiles.py
├── explain.py
├── styles.py
├── download_snapshot.py
├── requirements.txt
├── pytest.ini
├── README.md
├── .gitignore
├── .streamlit/
│   └── config.toml
├── data/
│   └── prices_snapshot.csv
├── docs/
│   └── requirements.md
└── tests/
    ├── test_metrics.py
    └── test_database.py
```

## Run locally

Python 3.11 is recommended. From the project root:

```bash
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bat
:: Windows Command Prompt
.venv\Scripts\activate.bat
```

Install dependencies and launch the app:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit (usually `http://localhost:8501`).

## Market-data handling

The application first attempts to download three years of daily adjusted-close prices from Yahoo Finance. If the live download is incomplete, it falls back to `data/prices_snapshot.csv`. The committed snapshot is long-format CSV with columns `date,ticker,adjusted_close`. The supplied snapshot was checked locally and contains **5,923 observations**, **8 tickers**, from **2023-11-06 through 2026-11-05**. Counts by ticker range from 739 to 741 observations.

To refresh the snapshot manually when network access is available:

```bash
python download_snapshot.py
```

The download script writes the CSV only after it has collected valid observations. After refreshing, inspect its date range and ticker coverage before committing it. The snapshot is a dated fallback, not a real-time feed.

## SQLite analytics design

The application uses the standard-library `sqlite3` module; no external database server or ORM is required. It creates three tables:

| Table | Purpose |
|---|---|
| `holdings` | Portfolio tickers, asset classes, sectors, quantities, and basis inputs |
| `prices` | Daily adjusted prices, keyed by date and ticker |
| `profile_rules` | Numeric limits for the illustrative investor profiles |

The SQL layer demonstrates:

1. CTEs and joins to calculate holding values at the latest common market date.
2. `SUM() OVER()` to calculate portfolio weights without collapsing holding-level rows.
3. `GROUP BY` for asset-class allocation and sector concentration.
4. `LAG()` to calculate daily portfolio returns.
5. `FIRST_VALUE()` and a running `MAX() OVER()` window to calculate cumulative wealth peaks and drawdowns.
6. Explicit NULL-safe `POWER()` registration for illustrative bond accrual.

Each Streamlit session receives a distinct SQLite database file in the operating system's temporary directory. This isolates quantity edits and database refreshes between active sessions. The database is rebuilt from the selected price source and current session quantities on reruns; it is not a permanent customer database.

Advanced risk measures such as volatility, Sharpe ratios, beta, VaR, tracking error, and information ratio are calculated in Python using pandas/NumPy. The project therefore uses a **hybrid SQL + Python analytics design**; it does not claim that every metric is computed in SQL.

## Methodology and assumptions

| Item | Treatment |
|---|---|
| Lookback | Three years of daily observations |
| Annualisation | 252 trading days |
| Market prices | Yahoo Finance adjusted close (`auto_adjust=True`) with CSV fallback |
| Portfolio | Buy-and-hold; no rebalancing or external cash flows |
| Market-holding basis | First common trading date across the market-priced holdings |
| Bond | Illustrative 7% annual compound yield; not a live bond valuation |
| Cash | Fixed principal with 0% assumed return |
| Risk-free rate | 7.2449% annual proxy, based on the CCIL tenor-wise indicative 9Y–10Y yield reference dated 4 Nov 2026; refresh before external use |
| Benchmark | Nifty 50 (`^NSEI`) |
| Investor profiles | Fictional thresholds for demonstration only |

The bond model does not use a bond's market price, coupon schedule, duration, credit spread, accrued-interest convention, or yield-to-maturity curve. Cash earns no interest. Taxes, transaction costs, fees, dividends beyond the adjusted-price treatment, deposits, withdrawals, and rebalancing are not modelled. These simplifications can materially affect results.

The risk-free rate is a dated proxy, not a guaranteed or universally appropriate risk-free rate for every horizon. Update it from a reliable current source and document the chosen tenor before presenting results.

## Tests

Run the offline test suite:

```bash
python -m pytest -q
```

The suite contains 11 tests covering metric formulas, return reconciliation, suitability checks, SQL valuations, allocation, sector weights, window-function analytics, profile-rule persistence, and missing-market-data handling. Tests use synthetic fixtures and do not require a live Yahoo Finance connection. The current local run reported **11 passed**. Run the command again after any code changes.

## Limitations and responsible use

- A historical return is not a forecast and does not guarantee future performance.
- The snapshot can become stale; check the displayed source/as-of date.
- Full-portfolio metrics and suitability checks are withheld when required market prices are incomplete.
- The sample holdings and profiles are illustrative, not actual client data or approved suitability rules.
- The output is for learning and demonstration; it must not be used to recommend trades or make client investment decisions.

## Future improvements

- Add a reproducible data-quality report and explicit price-source provenance.
- Add corporate-action and dividend treatment validation.
- Add a configurable bond instrument model and cash-yield input.
- Add integration tests for deployment and multi-session behaviour.
- Capture real application screenshots and add them to a `docs/images/` folder.

## Author

Built as a portfolio analytics and financial-data engineering project for learning and internship portfolio demonstration.
