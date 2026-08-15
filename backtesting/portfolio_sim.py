"""
Multi-Stock Chronological Portfolio Execution Simulator.

Simulates real-world account execution under realistic trading constraints:
  - Fixed baseline capital (default: ₹10,000)
  - Strict max concurrent position slots (default: 2 slots)
  - Intraday equity MIS leverage (default: 5x)
  - Exact Shoonya statutory taxes and brokerage deductions per trade
  - Chronological slot allocation (first valid breakdown fills open slot)
"""

import os
import sys
import io
import requests
import yfinance as yf
import pandas as pd

# Ensure workspace root is in sys.path for direct script execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from core.charges import calculate_shoonya_charges
from strategies.vwap_stoch_breakdown import (
    STRATEGY_NAME,
    evaluate_signals,
    simulate_single_trade,
)


def get_nifty50_symbols():
    url = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            df = pd.read_csv(io.StringIO(res.text))
            return [f"{sym}.NS" for sym in df['Symbol'].tolist()]
    except Exception:
        pass
    return ["GRASIM.NS", "DIXON.NS", "TATAMOTORS.NS", "INFY.NS", "RELIANCE.NS"]


def fetch_nifty_benchmark(period="60d", interval="15m"):
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


def scan_universe_signals(symbols, nifty_pct_map):
    """
    Scans all stock symbols in the universe and compiles all candidate trade signals.
    Returns a DataFrame of all detected signals sorted chronologically by Entry Time.
    """
    all_signals = []
    print("[2/3] Scanning Nifty 50 constituents with RELATIVE WEAKNESS filter...")

    for ticker in symbols:
        try:
            raw_df = yf.download(ticker, period="60d", interval="15m", progress=False)
            df = evaluate_signals(raw_df, nifty_pct_map)
            if df is None:
                continue

            for i in range(3, len(df)):
                if df.iloc[i]['Signal']:
                    trade = simulate_single_trade(df, i, ticker)
                    if trade:
                        all_signals.append(trade)
        except Exception:
            continue

    if not all_signals:
        return pd.DataFrame()

    return pd.DataFrame(all_signals).sort_values(by='Entry Time').reset_index(drop=True)


def simulate_portfolio_execution(signals_df, initial_capital=10000.0, max_concurrent=2, leverage=5):
    """
    Executes candidate signals chronologically, enforcing max concurrent position slots
    and computing exact Shoonya regulatory and statutory fee deductions per trade.
    """
    print("[3/3] Running chronological portfolio execution simulation...")
    capital = initial_capital
    per_trade_margin = capital / max_concurrent       # ₹5,000 margin
    trade_exposure = per_trade_margin * leverage     # ₹25,000 position

    active_trades = []
    executed_trades = []
    total_charges_paid = 0.0

    if not signals_df.empty:
        for _, sig in signals_df.iterrows():
            # Release slots that closed before this entry
            active_trades = [t for t in active_trades if t['Exit Time'] > sig['Entry Time']]

            if len(active_trades) < max_concurrent:
                sell_turnover = trade_exposure
                buy_turnover = trade_exposure * (1.0 - sig['PnL %'])

                trade_cost = calculate_shoonya_charges(sell_turnover, buy_turnover)
                total_charges_paid += trade_cost

                raw_pnl = trade_exposure * sig['PnL %']
                net_pnl = raw_pnl - trade_cost
                capital += net_pnl

                executed_trades.append({
                    'Symbol': sig['Symbol'], 'Entry Time': sig['Entry Time'],
                    'Exit Time': sig['Exit Time'], 'PnL %': sig['PnL %'] * 100,
                    'Net PnL (₹)': net_pnl, 'Capital': capital, 'Result': sig['Result']
                })
                active_trades.append(sig)

    tdf = pd.DataFrame(executed_trades)
    return tdf, capital, total_charges_paid, trade_exposure, per_trade_margin


def print_simulation_report(tdf, initial_capital, ending_capital, total_charges, trade_exposure, per_trade_margin, leverage):
    """Prints a formatted summary dashboard of the portfolio simulation performance."""
    if tdf.empty:
        print("\n⚠️ No trades were executed during this simulation period.")
        return

    win_count = len(tdf[tdf['Net PnL (₹)'] > 0])
    loss_count = len(tdf[tdf['Net PnL (₹)'] <= 0])
    total_trades = len(tdf)
    win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0
    net_profit = ending_capital - initial_capital
    net_return_pct = (net_profit / initial_capital) * 100
    gross_profit = net_profit + total_charges
    gross_return_pct = (gross_profit / initial_capital) * 100

    start_date = pd.to_datetime(tdf['Entry Time']).min().strftime('%Y-%m-%d')
    end_date = pd.to_datetime(tdf['Exit Time']).max().strftime('%Y-%m-%d')
    trading_days = len(pd.to_datetime(tdf['Entry Time']).dt.date.unique())

    print("\n=======================================================")
    print(f"      STRATEGY: {STRATEGY_NAME.upper()}")
    print("      ₹10,000 CAPITAL SIMULATION (MAX 2 CONCURRENT)   ")
    print("=======================================================")
    print(f"Simulation Period      : {start_date} to {end_date} ({trading_days} Trading Days)")
    print(f"Initial Capital        : ₹{initial_capital:,.2f}")
    print(f"Per-Trade Exposure     : ₹{trade_exposure:,.2f} (₹{per_trade_margin:,.0f} x {leverage} MIS)")
    print(f"Total Trades Taken     : {total_trades}")
    print(f"Winning Trades         : {win_count}")
    print(f"Losing Trades          : {loss_count}")
    print(f"Win Rate               : {win_rate:.2f}%")
    print("-------------------------------------------------------")
    print(f"Gross Profit (Pre-Tax) : ₹{gross_profit:,.2f} (+{gross_return_pct:.2f}%)")
    print(f"Total Taxes & Fees     : ₹{total_charges:,.2f}")
    print(f"Total Net Profit       : ₹{net_profit:,.2f} (Post-All Charges)")
    print(f"Ending Capital Balance : ₹{ending_capital:,.2f}")
    print(f"Net Return             : {net_return_pct:.2f}%")
    print("=======================================================\n")
    print("Outcome Distribution:")
    print(tdf['Result'].value_counts())


def run_portfolio_simulation(initial_capital=10000.0, max_concurrent=2, leverage=5):
    """Main orchestrator for the portfolio simulation."""
    symbols = get_nifty50_symbols()
    nifty_pct_map = fetch_nifty_benchmark()
    signals_df = scan_universe_signals(symbols, nifty_pct_map)

    tdf, ending_capital, total_charges, trade_exposure, per_trade_margin = simulate_portfolio_execution(
        signals_df=signals_df,
        initial_capital=initial_capital,
        max_concurrent=max_concurrent,
        leverage=leverage
    )

    print_simulation_report(
        tdf=tdf,
        initial_capital=initial_capital,
        ending_capital=ending_capital,
        total_charges=total_charges,
        trade_exposure=trade_exposure,
        per_trade_margin=per_trade_margin,
        leverage=leverage
    )


if __name__ == "__main__":
    run_portfolio_simulation()
