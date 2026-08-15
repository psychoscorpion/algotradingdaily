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
# pyrefly: ignore [missing-import]
import yfinance as yf
import pandas as pd

# Ensure workspace root is in sys.path for direct script execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from core.config import CONFIG, TradingConfig
from data_pipeline import get_nifty50_symbols, fetch_nifty_benchmark, fetch_stock_candles
from strategies.vwap_stoch_breakdown import (
    STRATEGY_NAME,
    STRATEGY_VERSION,
    evaluate_signals,
    simulate_single_trade,
)


def run_strategy_scan(config: TradingConfig = CONFIG):
    symbols = get_nifty50_symbols()
    all_trades = []
    start_time = time.time()
    processed_count = 0

    print("\n=======================================================")
    print(f"  SCANNER: {STRATEGY_NAME.upper()} (v{STRATEGY_VERSION})")
    print(f"  NIFTY 50 ({config.ENTRY_START_HOUR}:00 AM - {config.ENTRY_END_HOUR}:{config.ENTRY_END_MINUTE} | {config.SWING_HIGH_BARS}-Bar Swing High SL)  ")
    print("=======================================================")

    nifty_pct_map = fetch_nifty_benchmark(period=config.BACKTEST_PERIOD, interval=config.TIMEFRAME)
    print(f"[2/2] Running {config.BACKTEST_PERIOD} {config.TIMEFRAME} scan on Nifty 50 constituents...")

    for idx, ticker in enumerate(symbols, 1):
        try:
            raw_df = fetch_stock_candles(ticker, period=config.BACKTEST_PERIOD, interval=config.TIMEFRAME)
            if raw_df is None:
                continue

            df = evaluate_signals(raw_df, nifty_pct_map, config=config)
            if df is None:
                continue

            for i in range(config.SWING_HIGH_BARS, len(df)):
                if df.iloc[i]['Signal']:
                    trade = simulate_single_trade(df, i, ticker, config=config)
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
