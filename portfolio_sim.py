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

def run_portfolio_simulation(initial_capital=10000.0, max_concurrent=2, leverage=5):
    symbols = get_nifty50_symbols()
    all_signals = []
    
    print("\n[1/3] Fetching NIFTY 50 Benchmark (^NSEI) for Relative Weakness calculation...")
    try:
        nifty_raw = yf.download("^NSEI", period="60d", interval="15m", progress=False)
        if isinstance(nifty_raw.columns, pd.MultiIndex):
            nifty_raw.columns = nifty_raw.columns.get_level_values(0)
        nifty_raw['Date'] = nifty_raw.index.date
        daily_opens = nifty_raw.groupby('Date')['Open'].transform('first')
        nifty_raw['Nifty_Pct'] = (nifty_raw['Close'] - daily_opens) / daily_opens
        nifty_pct_map = nifty_raw['Nifty_Pct']
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch Nifty index: {e}")
        nifty_pct_map = pd.Series()

    print("[2/3] Scanning Nifty 50 constituents with RELATIVE WEAKNESS filter...")
    
    for ticker in symbols:
        try:
            df = yf.download(ticker, period="60d", interval="15m", progress=False)
            if df.empty or len(df) < 50:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            stoch = ta.stochrsi(df['Close'], length=14, rsi_length=14, k=3, d=3)
            adx_df = ta.adx(df['High'], df['Low'], df['Close'], length=14)
            vwap = ta.vwap(df['High'], df['Low'], df['Close'], df['Volume'])

            if stoch is None or adx_df is None or vwap is None:
                continue

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

            for i in range(3, len(df)):
                if df.iloc[i]['Signal']:
                    entry_t = df.index[i]
                    entry_p = df.iloc[i]['Close']
                    swing_high = df.iloc[i-3:i]['High'].max()
                    sl = max(swing_high * 1.0005, entry_p * 1.002)
                    risk = sl - entry_p
                    risk_pct = risk / entry_p
                    tp = entry_p - (2 * risk)
                    
                    exit_t, pnl_pct, result = None, 0, ''
                    curr_sl = sl
                    trailed = False

                    for j in range(i+1, len(df)):
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
                        all_signals.append({
                            'Symbol': ticker, 'Entry Time': entry_t, 'Exit Time': exit_t,
                            'Entry': entry_p, 'PnL %': pnl_pct, 'Result': result
                        })
        except Exception:
            continue

    print("[3/3] Running chronological portfolio execution simulation...")
    signals_df = pd.DataFrame(all_signals).sort_values(by='Entry Time').reset_index(drop=True)
    
    capital = initial_capital
    per_trade_margin = capital / max_concurrent       # ₹5,000 margin
    trade_exposure = per_trade_margin * leverage     # ₹25,000 position
    
    active_trades = []
    executed_trades = []
    total_charges_paid = 0.0

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
    
    print("\n=======================================================")
    print("      ₹10,000 CAPITAL SIMULATION (MAX 2 CONCURRENT)   ")
    print("=======================================================")
    print(f"Initial Capital        : ₹{initial_capital:,.2f}")
    print(f"Per-Trade Exposure     : ₹{trade_exposure:,.2f} (₹{per_trade_margin:,.0f} x {leverage} MIS)")
    print(f"Total Trades Taken     : {len(tdf)}")
    print(f"Winning Trades         : {len(tdf[tdf['Net PnL (₹)'] > 0])}")
    print(f"Losing Trades          : {len(tdf[tdf['Net PnL (₹)'] <= 0])}")
    print(f"Win Rate               : {(len(tdf[tdf['Net PnL (₹)'] > 0]) / len(tdf)) * 100:.2f}%")
    print(f"Total Taxes & Fees     : ₹{total_charges_paid:,.2f}")
    print(f"Total Net Profit       : ₹{capital - initial_capital:,.2f} (Post-All Charges)")
    print(f"Ending Capital Balance : ₹{capital:,.2f}")
    print(f"60-Day Net Return      : {((capital - initial_capital) / initial_capital) * 100:.2f}%")
    print("=======================================================\n")
    print("Outcome Distribution:")
    print(tdf['Result'].value_counts())

if __name__ == "__main__":
    run_portfolio_simulation()