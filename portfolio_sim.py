import sys
import io
import requests
import yfinance as yf
import pandas as pd
import pandas_ta as ta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def calculate_shoonya_charges(sell_turnover, buy_turnover):
    """
    Computes exact Shoonya statutory & regulatory charges for an Intraday Equity Trade.
    Shoonya Pricing:
      - Brokerage: 0.03% or ₹5.00 per executed order (whichever is lower)
      - STT: 0.025% on Sell side only
      - Exchange Txn (NSE): 0.00297% on Total Turnover
      - SEBI Turnover Fee: ₹10 / Crore (0.0001%)
      - Stamp Duty: 0.003% on Buy side
      - GST: 18% on (Brokerage + Exchange Txn + SEBI Fees)
    """
    entry_brokerage = min(sell_turnover * 0.0003, 5.00)
    exit_brokerage = min(buy_turnover * 0.0003, 5.00)
    total_brokerage = entry_brokerage + exit_brokerage

    total_turnover = sell_turnover + buy_turnover
    stt = sell_turnover * 0.00025
    exchange_txn = total_turnover * 0.0000297
    sebi_charges = total_turnover * 0.000001
    stamp_duty = buy_turnover * 0.00003
    gst = (total_brokerage + exchange_txn + sebi_charges) * 0.18

    total_charges = total_brokerage + stt + exchange_txn + sebi_charges + stamp_duty + gst
    return total_charges


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


def calculate_indicators_and_signals(df, nifty_pct_map):
    """
    Computes Stoch RSI, ADX, VWAP, Relative Weakness against Nifty, and Strategy Signals.
    Returns the enriched DataFrame, or None if indicator requirements are not met.
    """
    if df.empty or len(df) < 50:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    stoch = ta.stochrsi(df['Close'], length=14, rsi_length=14, k=3, d=3)
    adx_df = ta.adx(df['High'], df['Low'], df['Close'], length=14)
    vwap = ta.vwap(df['High'], df['Low'], df['Close'], df['Volume'])

    if stoch is None or adx_df is None or vwap is None:
        return None

    df['Stoch_K'] = stoch['STOCHRSIk_14_14_3_3']
    df['ADX'] = adx_df['ADX_14']
    df['VWAP'] = vwap
    df['Stoch_K_prev'] = df['Stoch_K'].shift(1)

    # Calculate Stock % Change from Day Open
    df['Date'] = df.index.date
    stock_daily_open = df.groupby('Date')['Open'].transform('first')
    df['Stock_Pct'] = (df['Close'] - stock_daily_open) / stock_daily_open

    # Map Relative Weakness filter (Stock performing worse than Nifty 50)
    if not nifty_pct_map.empty:
        df['Nifty_Pct'] = nifty_pct_map.reindex(df.index).ffill()
        df['Rel_Weakness'] = df['Stock_Pct'] < df['Nifty_Pct']
    else:
        df['Rel_Weakness'] = True

    # Time Filter: 10:00 AM to 1:30 PM
    time_filter = (
        (df.index.hour >= 10) & 
        ((df.index.hour < 13) | ((df.index.hour == 13) & (df.index.minute <= 30)))
    )

    df['Signal'] = (
        time_filter &
        df['Rel_Weakness'] &
        (df['Stoch_K_prev'] >= 80) & 
        (df['Stoch_K'] < 80) & 
        (df['ADX'] > 25) & 
        (df['Close'] < df['VWAP'])
    )
    return df


def simulate_single_trade(df, entry_idx, ticker):
    """
    Simulates the forward lifecycle of a single short position from entry_idx.
    Checks:
      1. Initial Stop Loss vs +1R Trailed Stop Loss (Breakeven).
      2. 1:2 Risk-to-Reward Target.
      3. 3:00 PM Intraday Auto-Squareoff.
    Returns a trade dictionary or None if no exit was reached.
    """
    entry_t = df.index[entry_idx]
    entry_p = df.iloc[entry_idx]['Close']
    swing_high = df.iloc[entry_idx - 3 : entry_idx]['High'].max()
    sl = max(swing_high * 1.0005, entry_p * 1.002)
    risk = sl - entry_p
    risk_pct = risk / entry_p
    tp = entry_p - (2 * risk)

    exit_t, pnl_pct, result = None, 0.0, ''
    curr_sl = sl
    trailed = False

    for j in range(entry_idx + 1, len(df)):
        bar = df.iloc[j]
        t_bar = df.index[j]

        # 1. Check if current SL is hit
        if bar['High'] >= curr_sl:
            if trailed:
                exit_t, pnl_pct, result = t_bar, 0.0, 'TRAIL SL (BE) 🛡️'
            else:
                exit_t, pnl_pct, result = t_bar, -risk_pct, 'SL HIT ❌'
            break

        # 2. Check if 1:2 Target is hit
        elif bar['Low'] <= tp:
            exit_t, pnl_pct, result = t_bar, (2 * risk_pct), 'TARGET HIT ✅'
            break

        # 3. Check if +1R profit threshold is reached to trail SL to Breakeven
        if not trailed and bar['Low'] <= (entry_p - risk):
            curr_sl = entry_p
            trailed = True

        # 4. Check 3:00 PM Square-Off
        if (t_bar.hour == 15 and t_bar.minute >= 0) or (t_bar.hour > 15):
            exit_t, pnl_pct, result = t_bar, (entry_p - bar['Close']) / entry_p, '3PM EXIT ⏱️'
            break

    if exit_t:
        return {
            'Symbol': ticker,
            'Entry Time': entry_t,
            'Exit Time': exit_t,
            'Entry': entry_p,
            'PnL %': pnl_pct,
            'Result': result
        }
    return None


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
            df = calculate_indicators_and_signals(raw_df, nifty_pct_map)
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

    print("\n=======================================================")
    print("      ₹10,000 CAPITAL SIMULATION (MAX 2 CONCURRENT)   ")
    print("=======================================================")
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
    print(f"60-Day Net Return      : {net_return_pct:.2f}%")
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