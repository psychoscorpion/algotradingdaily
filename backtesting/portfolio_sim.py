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
import pandas as pd

# Ensure workspace root is in sys.path for direct script execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from core.charges import calculate_shoonya_charges
from core.config import CONFIG, TradingConfig
from data_pipeline import get_nifty50_symbols, fetch_nifty_benchmark, fetch_stock_candles
from strategies.vwap_stoch_breakdown import (
    STRATEGY_NAME,
    evaluate_signals,
    simulate_single_trade,
)


def scan_universe_signals(symbols, nifty_pct_map, config: TradingConfig = CONFIG):
    """
    Scans all stock symbols in the universe and compiles all candidate trade signals.
    Returns a DataFrame of all detected signals sorted chronologically by Entry Time.
    """
    all_signals = []
    print("[2/3] Scanning Nifty 50 constituents with RELATIVE WEAKNESS filter...")

    for ticker in symbols:
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
                        all_signals.append(trade)
        except Exception:
            continue

    if not all_signals:
        return pd.DataFrame()

    return pd.DataFrame(all_signals).sort_values(by='Entry Time').reset_index(drop=True)


def simulate_portfolio_execution(signals_df: pd.DataFrame, config: TradingConfig = CONFIG):
    """
    Executes candidate signals chronologically, enforcing max concurrent position slots
    and computing exact Shoonya regulatory and statutory fee deductions per trade.
    """
    print("[3/3] Running chronological portfolio execution simulation...")
    capital = config.INITIAL_CAPITAL
    per_trade_margin = config.per_trade_margin
    trade_exposure = config.per_trade_exposure

    active_trades = []
    executed_trades = []
    total_charges_paid = 0.0

    if not signals_df.empty:
        for _, sig in signals_df.iterrows():
            # Release slots that closed before this entry
            active_trades = [t for t in active_trades if t['Exit Time'] > sig['Entry Time']]

            if len(active_trades) < config.MAX_CONCURRENT_POSITIONS:
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


def print_simulation_report(tdf: pd.DataFrame, ending_capital: float, total_charges: float, config: TradingConfig = CONFIG):
    """Prints a formatted summary dashboard of the portfolio simulation performance."""
    if tdf.empty:
        print("\n⚠️ No trades were executed during this simulation period.")
        return

    initial_capital = config.INITIAL_CAPITAL
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
    print(f"      ₹{initial_capital:,.0f} CAPITAL SIMULATION (MAX {config.MAX_CONCURRENT_POSITIONS} CONCURRENT)   ")
    print("=======================================================")
    print(f"Simulation Period      : {start_date} to {end_date} ({trading_days} Trading Days)")
    print(f"Initial Capital        : ₹{initial_capital:,.2f}")
    print(f"Per-Trade Exposure     : ₹{config.per_trade_exposure:,.2f} (₹{config.per_trade_margin:,.0f} x {config.LEVERAGE_MIS} MIS)")
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


def run_portfolio_simulation(config: TradingConfig = CONFIG):
    """Main orchestrator for the portfolio simulation."""
    symbols = get_nifty50_symbols()
    nifty_pct_map = fetch_nifty_benchmark(period=config.BACKTEST_PERIOD, interval=config.TIMEFRAME)
    signals_df = scan_universe_signals(symbols, nifty_pct_map, config=config)

    tdf, ending_capital, total_charges, _, _ = simulate_portfolio_execution(
        signals_df=signals_df,
        config=config
    )

    print_simulation_report(
        tdf=tdf,
        ending_capital=ending_capital,
        total_charges=total_charges,
        config=config
    )


if __name__ == "__main__":
    run_portfolio_simulation()
