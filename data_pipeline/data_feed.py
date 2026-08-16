"""
Market Data Ingestion & Gateway Layer.

Unified data gateway for the project:
  - Dynamic NSE NIFTY 50 constituent retrieval with fallback
  - NIFTY 50 benchmark downloader with local archiving & intraday % return
  - Smart stock candle loader with local CSV archiving, freshness checks & force refresh
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


def _archive_path(symbol: str, interval: str) -> str:
    """
    Returns the local archive CSV path for a ticker.
    Naming convention: market_data/{SYMBOL}_{interval}.csv
      e.g. RELIANCE.NS  -> market_data/RELIANCE_15m.csv
           ^NSEI        -> market_data/NIFTY50_15m.csv
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    clean = symbol.replace(".NS", "").replace("^NSEI", "NIFTY50").replace(".", "_")
    return os.path.join(CACHE_DIR, f"{clean}_{interval}.csv")


def _is_cache_fresh(df: pd.DataFrame, max_stale_days: int = 2) -> bool:
    """
    A local archive is considered fresh if its last candle is within
    max_stale_days calendar days of today (weekend-safe).
    """
    if df is None or df.empty:
        return False
    last_ts = df.index[-1]
    if getattr(last_ts, "tzinfo", None) is not None:
        last_ts = last_ts.tz_localize(None)
    gap_days = (pd.Timestamp.now().normalize() - pd.Timestamp(last_ts).normalize()).days
    return 0 <= gap_days <= max_stale_days


def load_candle_data(
    symbol: str,
    period: str = "60d",
    interval: str = "15m",
    force_refresh: bool = False,
) -> Optional[pd.DataFrame]:
    """
    Smart candle loader with local archiving:
      1. If a fresh local archive exists (market_data/{SYMBOL}_{interval}.csv),
         loads instantly from disk.
      2. Otherwise downloads {period} {interval} candles via yfinance,
         archives them to market_data/ and returns the DataFrame.
    """
    cache_path = _archive_path(symbol, interval)

    if not force_refresh and os.path.exists(cache_path):
        try:
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            if len(df) >= 50 and _is_cache_fresh(df):
                print(f"  📂 {symbol}: loaded from archive ({os.path.basename(cache_path)})")
                return df
        except Exception:
            pass

    try:
        raw_df = yf.download(symbol, period=period, interval=interval, progress=False)
        if raw_df is None or raw_df.empty or len(raw_df) < 50:
            return None

        if isinstance(raw_df.columns, pd.MultiIndex):
            raw_df.columns = raw_df.columns.get_level_values(0)

        raw_df.index.name = "Datetime"
        raw_df.to_csv(cache_path)
        print(f"  ⬇️  {symbol}: downloaded {len(raw_df)} candles -> archived ({os.path.basename(cache_path)})")
        return raw_df
    except Exception:
        return None


def fetch_nifty_benchmark(
    period: str = "60d",
    interval: str = "15m",
    force_refresh: bool = False,
) -> pd.Series:
    """
    Retrieves NIFTY 50 Benchmark (^NSEI) from local archive or yfinance
    and computes intraday % return from Day Open.
    Returns a Series indexed by timestamp for fast reindexing against stock candles.
    """
    print("\n[1/3] Fetching NIFTY 50 Benchmark (^NSEI) for Relative Weakness calculation...")
    nifty_raw = load_candle_data("^NSEI", period=period, interval=interval, force_refresh=force_refresh)
    if nifty_raw is None or nifty_raw.empty:
        print("⚠️ Warning: Could not fetch Nifty index data.")
        return pd.Series()

    nifty_raw = nifty_raw.copy()
    nifty_raw['Date'] = nifty_raw.index.date
    daily_opens = nifty_raw.groupby('Date')['Open'].transform('first')
    nifty_raw['Nifty_Pct'] = (nifty_raw['Close'] - daily_opens) / daily_opens
    return nifty_raw['Nifty_Pct']


def fetch_stock_candles(
    ticker: str,
    period: str = "60d",
    interval: str = "15m",
    use_cache: bool = False,
    force_refresh: bool = False,
) -> Optional[pd.DataFrame]:
    """
    Backward-compatible alias for load_candle_data.
    use_cache=True attempts the local archive first (legacy behaviour);
    use_cache=False forces a fresh download (legacy default).
    """
    return load_candle_data(
        ticker,
        period=period,
        interval=interval,
        force_refresh=force_refresh or (not use_cache),
    )