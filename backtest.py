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
    
    start_time = time.time()
    processed_count = 0

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

            # 2. Refined Time Filter: 10:00 AM to 1:30 PM only
            time_filter = (
                (df.index.hour >= 10) & 
                ((df.index.hour < 13) | ((df.index.hour == 13) & (df.index.minute <= 30)))
            )

            # 3. Strategy Entry Rule
            df['Signal'] = (
                time_filter &
                (df['Stoch_K_prev'] >= 80) & 
                (df['Stoch_K'] < 80) & 
                (df['ADX'] > 25) & 
                (df['Close'] < df['VWAP'])
            )

            # 4. Simulation Engine
            in_pos, entry_p, sl, tp, entry_t, risk_pct = False, 0, 0, 0, None, 0

            for i in range(3, len(df)):
                row = df.iloc[i]
                t = df.index[i]
                
                if in_pos:
                    # Stop Loss Hit
                    if row['High'] >= sl:
                        all_trades.append({
                            'Symbol': ticker, 'Entry Time': entry_t, 'Exit Time': t,
                            'PnL %': -risk_pct * 100, 'Result': 'SL HIT ❌'
                        })
                        in_pos = False
                    # Target Hit
                    elif row['Low'] <= tp:
                        all_trades.append({
                            'Symbol': ticker, 'Entry Time': entry_t, 'Exit Time': t,
                            'PnL %': (2 * risk_pct) * 100, 'Result': 'TARGET HIT ✅'
                        })
                        in_pos = False
                    # 3:00 PM Square-Off
                    elif (t.hour == 15 and t.minute >= 0) or (t.hour > 15):
                        pnl_pct = (entry_p - row['Close']) / entry_p
                        all_trades.append({
                            'Symbol': ticker, 'Entry Time': entry_t, 'Exit Time': t,
                            'PnL %': pnl_pct * 100, 'Result': '3PM EXIT ⏱️'
                        })
                        in_pos = False

                if not in_pos and row['Signal']:
                    entry_p = row['Close']
                    
                    # Clean 3-bar swing high (guaranteed all from today's session)
                    recent_3_highs = df.iloc[i-3:i]['High']
                    swing_high = recent_3_highs.max()
                    sl = max(swing_high * 1.0005, entry_p * 1.002)  # 0.05% buffer, min 0.2% SL
                    
                    risk = sl - entry_p
                    risk_pct = risk / entry_p
                    
                    # 1:2 Dynamic Target
                    tp = entry_p - (2 * risk)
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