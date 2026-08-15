"""
Market Data Ingestion & Gateway Layer.

Provides unified data utilities:
  - Dynamic NSE NIFTY 50 constituent retrieval with fallback
  - NIFTY 50 benchmark downloader with intraday % return calculation
  - Stock historical candle downloader with optional local CSV caching
"""

import io
import os
import requests
# pyrefly: ignore [missing-import]
import yfinance as yf
import pandas as pd
from typing import List, Optional

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "market_data"))

DEFAULT_NIFTY50_FALLBACK = [
    "GRASIM.NS", "DIXON.NS", "TATAMOTORS.NS", "INFY.NS", "RELIANCE.NS",
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS",
    "TCS.NS", "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS", "HINDUNILVR.NS"
]


def get_nifty50_symbols() -> List[str]:
    """
    Fetches the live NIFTY 50 constituent list from NSE Archives.
    Falls back to a curated stock list if NSE request times out.
    """
    url = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            df = pd.read_csv(io.StringIO(res.text))
            return [f"{sym}.NS" for sym in df['Symbol'].tolist()]
    except Exception:
        pass
    return DEFAULT_NIFTY50_FALLBACK


def fetch_nifty_benchmark(period: str = "60d", interval: str = "15m") -> pd.Series:
    """
    Downloads NIFTY 50 Benchmark (^NSEI) and computes intraday % return from Day Open.
    Returns a Series indexed by timestamp for fast reindexing against stock candles.
    """
    print("\n[1/3] Fetching NIFTY 50 Benchmark (^NSEI) for Relative Weakness calculation...")
    try:
        nifty_raw = yf.download("^NSEI", period=period, interval=interval, progress=False)
        if isinstance(nifty_raw.columns, pd.MultiIndex):
            nifty_raw.columns = nifty_raw.columns.get_level_values(0)
        nifty_raw['Date'] = nifty_raw.index.date
        daily_opens = nifty_raw.groupby('Date')['Open'].transform('first')
        nifty_raw['Nifty_Pct'] = (nifty_raw['Close'] - daily_opens) / daily_opens
        return nifty_raw['Nifty_Pct']
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch Nifty index: {e}")
        return pd.Series()


def fetch_stock_candles(ticker: str, period: str = "60d", interval: str = "15m", use_cache: bool = False) -> Optional[pd.DataFrame]:
    """
    Downloads historical candle data for a given ticker with optional local caching.
    Flattens multi-index columns and returns clean DataFrame.
    """
    cache_path = os.path.join(CACHE_DIR, f"{ticker}_{period}_{interval}.csv")

    if use_cache and os.path.exists(cache_path):
        try:
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            if not df.empty:
                return df
        except Exception:
            pass

    try:
        raw_df = yf.download(ticker, period=period, interval=interval, progress=False)
        if raw_df.empty or len(raw_df) < 50:
            return None

        if isinstance(raw_df.columns, pd.MultiIndex):
            raw_df.columns = raw_df.columns.get_level_values(0)

        if use_cache and os.path.exists(CACHE_DIR):
            raw_df.to_csv(cache_path)

        return raw_df
    except Exception:
        return None
