"""Download a real three-year adjusted-price snapshot for offline demo fallback."""
from pathlib import Path
import pandas as pd
import yfinance as yf

TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS",
    "NIFTYBEES.NS", "GOLDBEES.NS", "^NSEI",
]
OUTPUT = Path(__file__).resolve().parent / "data" / "prices_snapshot.csv"


def main():
    frames = []
    for ticker in TICKERS:
        raw = yf.download(
            ticker, period="3y", interval="1d", auto_adjust=True,
            progress=False, threads=False,
        )
        if raw.empty or "Close" not in raw:
            raise RuntimeError(f"No adjusted close data returned for {ticker}")
        close = raw["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        frame = close.rename("adjusted_close").to_frame()
        frame["ticker"] = ticker
        frame = frame.rename_axis("date").reset_index()
        frames.append(frame)
    result = pd.concat(frames, ignore_index=True)
    result = result[["date", "ticker", "adjusted_close"]].dropna()
    if result.empty:
        raise RuntimeError("No prices were downloaded; snapshot was not written.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT, index=False)
    print(f"Saved {len(result)} price observations to {OUTPUT}")
    print(f"Snapshot as-of date: {pd.to_datetime(result['date']).max().date()}")


if __name__ == "__main__":
    main()
