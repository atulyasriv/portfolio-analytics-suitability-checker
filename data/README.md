# Market-price snapshot

`prices_snapshot.csv` is a long-format fallback snapshot with columns `date,ticker,adjusted_close`. It contains 5,923 rows across 8 tickers, covering 2023-11-06 to 2026-11-05. The source workflow is `download_snapshot.py` (Yahoo Finance via yfinance, adjusted close). Refresh and validate the file before external presentation; it is not a real-time feed.
