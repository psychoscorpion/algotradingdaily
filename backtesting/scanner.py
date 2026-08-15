"""
Standalone Single-Stock Technical Indicator Scanner.

Scans the NIFTY 50 universe unconstrained (assuming unlimited capital slots)
using the VWAP-Stoch Breakdown strategy from the strategies package.
"""

import os
import sys
import io
import time
import requests
import yfinance as yf
import pandas as pd

# Ensure workspace root is in sys.path for direct script execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from strategies.vwap_stoch_breakdown import (
    STRATEGY_NAME,
    STRATEGY_VERSION,
    evaluate_signals,
    simulate_single_trade,
)


def get_nifty50_symbols():
    url = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            df = pd.read_csv(io.StringIO(res.text))
            return [f"{sym}.NS" for sym in df['Symbol'].tolist()]
    except Exception:
        pass
    return ["GRASIM.NS", "DIXON.NS", "TATAMOTORS.NS", "INFY.NS", "RELIANCE.NS"]


def fetch_nifty_benchmark(period="60d", interval="15m"):
    """
    Downloads NIFTY 50 Benchmark (^NSEI) and computes intraday % return from Day Open.
    """
    print("\n[1/2] Fetching NIFTY 50 Benchmark (^NSEI) for Relative Weakness calculation...")
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


def run_strategy_scan():
    symbols = get_nifty50_symbols()
    all_trades = []
    start_time = time.time()
    processed_count = 0

    print("\n=======================================================")
    print(f"  SCANNER: {STRATEGY_NAME.upper()} (v{STRATEGY_VERSION})")
    print("  NIFTY 50 (10:00 AM - 1:30 PM | 3-Bar Swing High SL)  ")
    print("=======================================================\n")

    nifty_pct_map = fetch_nifty_benchmark()
    print("[2/2] Running 60-day 15m scan on Nifty 50 constituents...")

    for idx, ticker in enumerate(symbols, 1):
        try:
            raw_df = yf.download(ticker, period="60d", interval="15m", progress=False)
            df = evaluate_signals(raw_df, nifty_pct_map)
            if df is None:
                continue

            for i in range(3, len(df)):
                if df.iloc[i]['Signal']:
                    trade = simulate_single_trade(df, i, ticker)
                    if trade:
                        trade_entry = trade.copy()
                        trade_entry['PnL %'] = trade_entry['PnL %'] * 100
                        all_trades.append(trade_entry)

            processed_count += 1
            if idx % 10 == 0 or idx == len(symbols):
                print(f"Progress: [{idx}/{len(symbols)}] stocks processed...")

        except Exception:
            continue

    elapsed = time.time() - start_time
    tdf = pd.DataFrame(all_trades)

    if tdf.empty:
        print("No trades triggered with these rules.")
        return

    total = len(tdf)
    wins = len(tdf[tdf['PnL %'] > 0])
    losses = total - wins
    win_rate = (wins / total) * 100
    net_pnl = tdf['PnL %'].sum()
    avg_trade_pnl = tdf['PnL %'].mean()

    start_date = pd.to_datetime(tdf['Entry Time']).min().strftime('%Y-%m-%d')
    end_date = pd.to_datetime(tdf['Exit Time']).max().strftime('%Y-%m-%d')

    print("\n=======================================================")
    print(f"      {STRATEGY_NAME.upper()} SCANNER RESULTS          ")
    print("=======================================================")
    print(f"Scan Period            : {start_date} to {end_date}")
    print(f"Total Universe Scanned : {processed_count} Stocks")
    print(f"Execution Time         : {elapsed:.1f} seconds")
    print(f"Total Trades Generated : {total}")
    print(f"Winning Trades         : {wins}")
    print(f"Losing Trades          : {losses}")
    print(f"Win Rate               : {win_rate:.2f}%")
    print(f"Avg Return / Trade     : {avg_trade_pnl:.3f}%")
    print(f"Cumulative Return      : {net_pnl:.2f}% (Unleveraged, Unconstrained)")
    print("=======================================================\n")
    print("Outcome Distribution:")
    print(tdf['Result'].value_counts())


if __name__ == "__main__":
    run_strategy_scan()
