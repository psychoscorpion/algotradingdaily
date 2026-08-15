"""
Strategy: VWAP-Stoch Breakdown (15m Intraday Short)

Strategy Rules:
  - Direction: Intraday Short Breakdown (MIS)
  - Timeframe: 15-Minute Candles
  - Entry Window: 10:00 AM – 01:30 PM IST
  - Relative Weakness: Stock Intraday % < NIFTY 50 Intraday %
  - Technical Triggers:
      1. Stoch RSI %K crosses below 80 from overbought (Stoch_K_prev >= 80 and Stoch_K < 80)
      2. ADX > 25 (Trend strength filter)
      3. Close < VWAP (Bearish intraday bias)
  - Risk Management:
      1. Initial Stop Loss: 3-bar swing high (min 0.2% buffer)
      2. Profit Target: Dynamic 1:2 Risk-to-Reward (2R)
      3. Trailing Stop Loss: Move SL to Breakeven when trade reaches +1R profit
      4. Auto-Squareoff: Hard exit at 15:00 IST (3:00 PM)
"""

import pandas as pd
from typing import Optional, Dict, Any
from core.indicators import add_stoch_rsi, add_adx, add_vwap, add_relative_weakness

STRATEGY_NAME = "VWAP-Stoch Breakdown"
STRATEGY_VERSION = "1.0.0"


def evaluate_signals(df: pd.DataFrame, nifty_pct_map: Optional[pd.Series] = None) -> Optional[pd.DataFrame]:
    """
    Evaluates the VWAP-Stoch Breakdown strategy criteria on 15m candle DataFrames.
    Returns enriched DataFrame with boolean 'Signal' column, or None if data is insufficient.
    """
    if df.empty or len(df) < 50:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 1. Compute Required Indicators
    df = add_stoch_rsi(df)
    df = add_adx(df)
    df = add_vwap(df)

    if 'Stoch_K' not in df.columns or 'ADX' not in df.columns or 'VWAP' not in df.columns:
        return None

    # 2. Add Relative Weakness Filter
    df = add_relative_weakness(df, nifty_pct_map)

    # 3. Time Filter: 10:00 AM to 1:30 PM IST
    time_filter = (
        (df.index.hour >= 10) & 
        ((df.index.hour < 13) | ((df.index.hour == 13) & (df.index.minute <= 30)))
    )

    # 4. Generate Strategy Entry Signals
    df['Signal'] = (
        time_filter &
        df['Rel_Weakness'] &
        (df['Stoch_K_prev'] >= 80) & 
        (df['Stoch_K'] < 80) & 
        (df['ADX'] > 25) & 
        (df['Close'] < df['VWAP'])
    )

    return df


def simulate_single_trade(df: pd.DataFrame, entry_idx: int, ticker: str) -> Optional[Dict[str, Any]]:
    """
    Simulates the forward lifecycle of a single VWAP-Stoch Breakdown short position from entry_idx.
    Enforces:
      1. Initial Stop Loss vs +1R Trailed Stop Loss (Breakeven).
      2. Dynamic 1:2 Risk-to-Reward Target.
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
            'Entry Price': entry_p,
            'Exit Time': exit_t,
            'PnL %': pnl_pct,
            'Result': result
        }
    return None
