"""SQLite persistence and SQL-first portfolio analytics.

SQLite is deliberately used through Python's standard-library sqlite3 module.
The database is rebuilt from the selected source inputs on each Streamlit rerun so
session-edited quantities and refreshed prices cannot leave stale analytics behind.
"""
from pathlib import Path
from contextlib import closing
import math
import sqlite3
import pandas as pd

MARKET_CLASSES = ("Equity", "Equity ETF", "Commodity")


def _power(base, exponent):
    """SQLite-compatible POWER that propagates SQL NULL instead of raising."""
    if base is None or exponent is None:
        return None
    return math.pow(base, exponent)


def connect_db(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Register POWER explicitly; preserve SQLite's NULL propagation semantics.
    conn.create_function("POWER", 2, _power, deterministic=True)
    return conn


def initialize_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS holdings (
        ticker TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        asset_class TEXT NOT NULL,
        sector TEXT NOT NULL,
        quantity REAL NOT NULL,
        buy_price REAL,
        purchase_date TEXT
    );
    CREATE TABLE IF NOT EXISTS prices (
        date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        adjusted_close REAL NOT NULL CHECK (adjusted_close > 0),
        PRIMARY KEY (date, ticker)
    );
    CREATE INDEX IF NOT EXISTS idx_prices_ticker_date ON prices(ticker, date);
    CREATE TABLE IF NOT EXISTS profile_rules (
        profile_name TEXT NOT NULL,
        rule_name TEXT NOT NULL,
        rule_value REAL NOT NULL,
        PRIMARY KEY (profile_name, rule_name)
    );
    """)


def _replace_holdings(conn, portfolio):
    rows = []
    for r in portfolio.itertuples(index=False):
        buy_price = None if pd.isna(r.buy_price) else float(r.buy_price)
        purchase_date = None if pd.isna(r.purchase_date) else str(r.purchase_date)
        rows.append((r.ticker, r.name, r.asset_class, r.sector,
                     float(r.quantity), buy_price, purchase_date))
    conn.execute("DELETE FROM holdings")
    conn.executemany(
        """INSERT INTO holdings
        (ticker,name,asset_class,sector,quantity,buy_price,purchase_date)
        VALUES (?,?,?,?,?,?,?)""", rows
    )


def _replace_prices(conn, prices):
    conn.execute("DELETE FROM prices")
    if prices is None or prices.empty:
        return
    rows = []
    for date, row in prices.iterrows():
        date_text = pd.Timestamp(date).date().isoformat()
        for ticker, value in row.items():
            if pd.notna(value) and float(value) > 0:
                rows.append((date_text, str(ticker), float(value)))
    conn.executemany(
        "INSERT OR REPLACE INTO prices(date,ticker,adjusted_close) VALUES (?,?,?)",
        rows
    )


def _replace_profile_rules(conn, profiles):
    rows = []
    for profile_name, rules in profiles.items():
        for rule_name, value in rules.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                rows.append((profile_name, rule_name, float(value)))
    conn.execute("DELETE FROM profile_rules")
    conn.executemany(
        "INSERT INTO profile_rules(profile_name,rule_name,rule_value) VALUES (?,?,?)",
        rows
    )


def refresh_database(portfolio, prices, profiles, path, bond_yield):
    """Create/refresh the SQLite source tables and return the database path."""
    with closing(connect_db(path)) as conn:
        initialize_schema(conn)
        _replace_holdings(conn, portfolio)
        _replace_prices(conn, prices)
        _replace_profile_rules(conn, profiles)
        conn.execute("INSERT OR REPLACE INTO profile_rules VALUES (?,?,?)",
                     ("__assumptions__", "bond_yield", float(bond_yield)))
        conn.commit()
    return Path(path)


def query_current_holdings(path, bond_yield):
    """Current values and portfolio weights, with total calculated by SUM() OVER ()."""
    sql = """
    WITH market_dates AS (
        SELECT p.date
        FROM prices p
        JOIN holdings h ON h.ticker = p.ticker
        WHERE h.asset_class IN ('Equity','Equity ETF','Commodity')
        GROUP BY p.date
        HAVING COUNT(DISTINCT p.ticker) = (
            SELECT COUNT(*) FROM holdings
            WHERE asset_class IN ('Equity','Equity ETF','Commodity')
        )
    ),
    bounds AS (
        SELECT MIN(date) AS first_date, MAX(date) AS last_date FROM market_dates
    ),
    market_values AS (
        SELECT h.ticker, h.name, h.asset_class, h.sector, h.quantity,
               h.quantity * p.adjusted_close AS current_value,
               h.quantity * p0.adjusted_close AS cost_basis,
               b.first_date AS purchase_date
        FROM holdings h
        CROSS JOIN bounds b
        LEFT JOIN prices p ON p.ticker = h.ticker AND p.date = b.last_date
        LEFT JOIN prices p0 ON p0.ticker = h.ticker AND p0.date = b.first_date
        WHERE h.asset_class IN ('Equity','Equity ETF','Commodity')
    ),
    fixed_values AS (
        SELECT h.ticker, h.name, h.asset_class, h.sector, h.quantity,
               CASE WHEN h.asset_class = 'Bond'
                    THEN h.quantity * COALESCE(h.buy_price,0) *
                         POWER(1.0 + ?, (julianday(b.last_date)-julianday(b.first_date))/365.25)
                    ELSE h.quantity * COALESCE(h.buy_price,0) END AS current_value,
               h.quantity * COALESCE(h.buy_price,0) AS cost_basis,
               CASE WHEN h.asset_class = 'Bond' THEN b.first_date ELSE NULL END AS purchase_date
        FROM holdings h CROSS JOIN bounds b
        WHERE h.asset_class IN ('Bond','Cash')
    ),
    combined AS (
        SELECT * FROM market_values
        UNION ALL
        SELECT * FROM fixed_values
    )
    SELECT ticker, name, asset_class, sector, quantity, purchase_date,
           cost_basis AS cost, current_value,
           CASE WHEN cost_basis > 0 THEN (current_value/cost_basis - 1.0)*100 END AS return_pct,
           current_value / NULLIF(SUM(current_value) OVER (),0) AS weight
    FROM combined
    ORDER BY asset_class, name
    """
    with closing(connect_db(path)) as conn:
        return pd.read_sql_query(sql, conn, params=(float(bond_yield),))


_CURRENT_VALUE_CTES = """
WITH market_dates AS (
    SELECT p.date
    FROM prices p JOIN holdings h ON h.ticker=p.ticker
    WHERE h.asset_class IN ('Equity','Equity ETF','Commodity')
    GROUP BY p.date
    HAVING COUNT(DISTINCT p.ticker) = (
        SELECT COUNT(*) FROM holdings
        WHERE asset_class IN ('Equity','Equity ETF','Commodity')
    )
),
bounds AS (SELECT MIN(date) first_date, MAX(date) last_date FROM market_dates),
market_values AS (
    SELECT h.ticker,h.name,h.asset_class,h.sector,h.quantity,
           h.quantity*p.adjusted_close AS current_value,
           h.quantity*p0.adjusted_close AS cost_basis,
           b.first_date AS purchase_date
    FROM holdings h CROSS JOIN bounds b
    LEFT JOIN prices p ON p.ticker=h.ticker AND p.date=b.last_date
    LEFT JOIN prices p0 ON p0.ticker=h.ticker AND p0.date=b.first_date
    WHERE h.asset_class IN ('Equity','Equity ETF','Commodity')
),
fixed_values AS (
    SELECT h.ticker,h.name,h.asset_class,h.sector,h.quantity,
           CASE WHEN h.asset_class='Bond' THEN h.quantity*COALESCE(h.buy_price,0)*
                POWER(1.0+?,(julianday(b.last_date)-julianday(b.first_date))/365.25)
                ELSE h.quantity*COALESCE(h.buy_price,0) END AS current_value,
           h.quantity*COALESCE(h.buy_price,0) AS cost_basis,
           CASE WHEN h.asset_class='Bond' THEN b.first_date ELSE NULL END AS purchase_date
    FROM holdings h CROSS JOIN bounds b WHERE h.asset_class IN ('Bond','Cash')
),
combined AS (
    SELECT * FROM market_values UNION ALL SELECT * FROM fixed_values
)
"""

def query_allocation(path, bond_yield):
    """Asset-class values and weights are aggregated entirely in SQL."""
    sql = _CURRENT_VALUE_CTES + """
    SELECT asset_class, SUM(current_value) AS current_value,
           SUM(current_value)/NULLIF(SUM(SUM(current_value)) OVER (),0) AS weight
    FROM combined GROUP BY asset_class ORDER BY current_value
    """
    with closing(connect_db(path)) as conn:
        return pd.read_sql_query(sql, conn, params=(float(bond_yield),))


def query_sector_concentration(path, bond_yield):
    """Equity sector values as a percentage of the entire portfolio value."""
    sql = _CURRENT_VALUE_CTES + """
    SELECT sector, SUM(current_value) AS current_value,
           SUM(current_value) / NULLIF(
               (SELECT SUM(current_value) FROM combined), 0
           ) AS weight
    FROM combined
    WHERE asset_class IN ('Equity','Equity ETF')
    GROUP BY sector ORDER BY current_value
    """
    with closing(connect_db(path)) as conn:
        return pd.read_sql_query(sql, conn, params=(float(bond_yield),))


def query_daily_analytics(path, bond_yield):
    """Daily total value, LAG-based returns and MAX-window running-peak drawdown."""
    sql = """
    WITH market_dates AS (
        SELECT p.date
        FROM prices p JOIN holdings h ON h.ticker=p.ticker
        WHERE h.asset_class IN ('Equity','Equity ETF','Commodity')
        GROUP BY p.date
        HAVING COUNT(DISTINCT p.ticker) = (
            SELECT COUNT(*) FROM holdings
            WHERE asset_class IN ('Equity','Equity ETF','Commodity')
        )
    ),
    first_day AS (SELECT MIN(date) AS first_date FROM market_dates),
    daily_market AS (
        SELECT p.date, SUM(h.quantity*p.adjusted_close) AS market_value
        FROM prices p JOIN holdings h ON h.ticker=p.ticker
        JOIN market_dates md ON md.date=p.date
        WHERE h.asset_class IN ('Equity','Equity ETF','Commodity')
        GROUP BY p.date
    ),
    daily_total AS (
        SELECT dm.date,
               dm.market_value
               + COALESCE((
                   SELECT SUM(h.quantity*h.buy_price *
                     POWER(1.0 + ?, (julianday(dm.date)-julianday(fd.first_date))/365.25))
                   FROM holdings h WHERE h.asset_class='Bond'
                 ),0)
               + COALESCE((
                   SELECT SUM(h.quantity*h.buy_price)
                   FROM holdings h WHERE h.asset_class='Cash'
                 ),0) AS portfolio_value
        FROM daily_market dm CROSS JOIN first_day fd
    ),
    returns AS (
        SELECT date, portfolio_value,
               LAG(portfolio_value) OVER (ORDER BY date) AS previous_value,
               portfolio_value / NULLIF(LAG(portfolio_value) OVER (ORDER BY date),0)-1 AS daily_return
        FROM daily_total
    ),
    wealth AS (
        SELECT date, portfolio_value, previous_value, daily_return,
               portfolio_value / NULLIF(
                   FIRST_VALUE(portfolio_value) OVER (ORDER BY date), 0
               ) AS cumulative_wealth
        FROM returns
    ),
    peaks AS (
        SELECT date, portfolio_value, previous_value, daily_return, cumulative_wealth,
               MAX(cumulative_wealth) OVER (
                   ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
               ) AS running_peak
        FROM wealth
    )
    SELECT date, portfolio_value, previous_value, daily_return,
           running_peak, cumulative_wealth / NULLIF(running_peak,0)-1 AS drawdown
    FROM peaks
    ORDER BY date
    """
    with closing(connect_db(path)) as conn:
        frame = pd.read_sql_query(sql, conn, params=(float(bond_yield),))
    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.set_index("date")
    return frame


def query_profile_rules(path, profile_name):
    sql = "SELECT rule_name, rule_value FROM profile_rules WHERE profile_name=?"
    with closing(connect_db(path)) as conn:
        return pd.read_sql_query(sql, conn, params=(profile_name,)).set_index("rule_name")["rule_value"].to_dict()
