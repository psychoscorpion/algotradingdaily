import io
import time
import requests
import yfinance as yf
import pandas as pd
import pandas_ta as ta

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

def run_10am_swing_high_scan():
    symbols = get_nifty50_symbols()
    all_trades = []
    
    print("\n=======================================================")
    print("  NIFTY 50 (10:00 AM - 1:30 PM | 3-Bar Swing High SL)  ")
    print("=======================================================\n")
    
    print("\n[1/2] Fetching NIFTY 50 Benchmark (^NSEI) for Relative Weakness calculation...")
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

    print("[2/2] Running 60-day 15m scan on Nifty 50 constituents...")

    for idx, ticker in enumerate(symbols, 1):
        try:
            df = yf.download(ticker, period="60d", interval="15m", progress=False)
            if df.empty or len(df) < 50:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # 1. Technical Indicators
            stoch = ta.stochrsi(df['Close'], length=14, rsi_length=14, k=3, d=3)
            adx_df = ta.adx(df['High'], df['Low'], df['Close'], length=14)
            vwap = ta.vwap(df['High'], df['Low'], df['Close'], df['Volume'])

            if stoch is None or adx_df is None or vwap is None:
                continue

            df['Stoch_K'] = stoch['STOCHRSIk_14_14_3_3']
            df['ADX'] = adx_df['ADX_14']
            df['VWAP'] = vwap
            df['Stoch_K_prev'] = df['Stoch_K'].shift(1)

            # 2. Relative Weakness Filter
            df['Date'] = df.index.date
            stock_daily_open = df.groupby('Date')['Open'].transform('first')
            df['Stock_Pct'] = (df['Close'] - stock_daily_open) / stock_daily_open
            if not nifty_pct_map.empty:
                df['Nifty_Pct'] = nifty_pct_map.reindex(df.index).ffill()
                df['Rel_Weakness'] = df['Stock_Pct'] < df['Nifty_Pct']
            else:
                df['Rel_Weakness'] = True

            # 3. Refined Time Filter: 10:00 AM to 1:30 PM only
            time_filter = (
                (df.index.hour >= 10) & 
                ((df.index.hour < 13) | ((df.index.hour == 13) & (df.index.minute <= 30)))
            )

            # 4. Strategy Entry Rule
            df['Signal'] = (
                time_filter &
                df['Rel_Weakness'] &
                (df['Stoch_K_prev'] >= 80) & 
                (df['Stoch_K'] < 80) & 
                (df['ADX'] > 25) & 
                (df['Close'] < df['VWAP'])
            )

            # 5. Simulation Engine
            in_pos, entry_p, sl, tp, entry_t, risk_pct = False, 0, 0, 0, None, 0
            curr_sl, trailed = 0, False

            for i in range(3, len(df)):
                row = df.iloc[i]
                t = df.index[i]
                
                if in_pos:
                    # Stop Loss Hit
                    if row['High'] >= curr_sl:
                        res_name = 'TRAIL SL (BE) 🛡️' if trailed else 'SL HIT ❌'
                        pnl_val = 0.0 if trailed else (-risk_pct * 100)
                        all_trades.append({
                            'Symbol': ticker, 'Entry Time': entry_t, 'Exit Time': t,
                            'PnL %': pnl_val, 'Result': res_name
                        })
                        in_pos = False
                    # Target Hit
                    elif row['Low'] <= tp:
                        all_trades.append({
                            'Symbol': ticker, 'Entry Time': entry_t, 'Exit Time': t,
                            'PnL %': (2 * risk_pct) * 100, 'Result': 'TARGET HIT ✅'
                        })
                        in_pos = False
                    else:
                        # Trail SL to Breakeven at +1R
                        if not trailed and row['Low'] <= (entry_p - risk):
                            curr_sl = entry_p
                            trailed = True

                        # 3:00 PM Square-Off
                        if (t.hour == 15 and t.minute >= 0) or (t.hour > 15):
                            pnl_pct = (entry_p - row['Close']) / entry_p
                            all_trades.append({
                                'Symbol': ticker, 'Entry Time': entry_t, 'Exit Time': t,
                                'PnL %': pnl_pct * 100, 'Result': '3PM EXIT ⏱️'
                            })
                            in_pos = False

                if not in_pos and row['Signal']:
                    entry_p = row['Close']
                    recent_3_highs = df.iloc[i-3:i]['High']
                    swing_high = recent_3_highs.max()
                    sl = max(swing_high * 1.0005, entry_p * 1.002)
                    risk = sl - entry_p
                    risk_pct = risk / entry_p
                    tp = entry_p - (2 * risk)
                    curr_sl = sl
                    trailed = False
                    entry_t = t
                    in_pos = True
            
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

    print("\n=======================================================")
    print("      10:00 AM - 1:30 PM (3-BAR SL + 1:2 RR) RESULTS   ")
    print("=======================================================")
    print(f"Total Universe Scanned : {processed_count} Stocks")
    print(f"Execution Time         : {elapsed:.1f} seconds")
    print(f"Total Trades Generated : {total}")
    print(f"Winning Trades         : {wins}")
    print(f"Losing Trades          : {losses}")
    print(f"Win Rate               : {win_rate:.2f}%")
    print(f"Avg Return / Trade     : {avg_trade_pnl:.3f}%")
    print(f"Cumulative Return      : {net_pnl:.2f}% (Unleveraged)")
    print("=======================================================\n")
    print("Outcome Distribution:")
    print(tdf['Result'].value_counts())

if __name__ == "__main__":
    run_10am_swing_high_scan()