"""
Live Trading Paper Execution Engine.

Executes real-time strategy signals in virtual paper trading mode:
  - Fills orders virtually at prevailing market prices (zero real capital risk)
  - Tracks live position lifecycles (SL hit, 1:2 Target hit, +1R trailing SL to BE, 3:00 PM Exit)
  - Emits real-time trade logs and updates virtual PnL
"""

import os
import sys
import datetime
from typing import Dict, Any, Optional

# Ensure workspace root is in sys.path for direct script execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from core.config import CONFIG, TradingConfig
from live_trading.base_engine import BaseTradingEngine
from strategies.vwap_stoch_breakdown import STRATEGY_NAME


class PaperTradingEngine(BaseTradingEngine):
    """
    Simulates real-time market execution without placing orders on exchange.
    Used for live forward validation of strategy signals.
    """
    def __init__(self, config: TradingConfig = CONFIG):
        super().__init__(config=config)
        self.virtual_balance = config.INITIAL_CAPITAL
        self.paper_trades = []

    def execute_virtual_entry(self, symbol: str, entry_price: float, sl_price: float, tp_price: float):
        """Simulates virtual entry and establishes stop loss / target."""
        if len(self.active_positions) >= self.config.MAX_CONCURRENT_POSITIONS:
            return

        qty = max(int(self.config.per_trade_exposure // entry_price), 1)
        risk = sl_price - entry_price

        self.active_positions[symbol] = {
            'symbol': symbol,
            'entry_price': entry_price,
            'entry_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'qty': qty,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'risk': risk,
            'trailed': False
        }
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 📝 [PAPER ENTRY] Short {qty}x {symbol} @ ₹{entry_price:.2f} | SL: ₹{sl_price:.2f} | TP: ₹{tp_price:.2f}")

    def update_position(self, symbol: str, current_ltp: float, high: float, low: float) -> Optional[Dict[str, Any]]:
        """Updates virtual position tracking against live market ticks."""
        if symbol not in self.active_positions:
            return None

        pos = self.active_positions[symbol]
        entry_p = pos['entry_price']
        curr_sl = pos['sl_price']
        tp = pos['tp_price']
        risk = pos['risk']

        # 1. Stop Loss Trigger
        if high >= curr_sl:
            result = 'TRAIL SL (BE) 🛡️' if pos['trailed'] else 'SL HIT ❌'
            exit_price = curr_sl
            return self._close_position(symbol, exit_price, result)

        # 2. Target Trigger
        if low <= tp:
            result = 'TARGET HIT ✅'
            exit_price = tp
            return self._close_position(symbol, exit_price, result)

        # 3. Trail to Breakeven at +1R
        if not pos['trailed'] and low <= (entry_p - risk):
            pos['sl_price'] = entry_p
            pos['trailed'] = True
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🛡️ [PAPER TRAIL] {symbol} reached +1R profit! SL moved to Breakeven (₹{entry_p:.2f}).")

        # 4. Mandatory Squareoff
        if self.is_squareoff_time():
            return self._close_position(symbol, current_ltp, '3PM EXIT ⏱️')

        return None

    def _close_position(self, symbol: str, exit_price: float, result: str) -> Dict[str, Any]:
        """Closes virtual position and logs result."""
        pos = self.active_positions.pop(symbol)
        raw_pnl = (pos['entry_price'] - exit_price) * pos['qty']
        pnl_pct = (pos['entry_price'] - exit_price) / pos['entry_price'] * 100

        trade_record = {
            'symbol': symbol,
            'entry_time': pos['entry_time'],
            'exit_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'entry_price': pos['entry_price'],
            'exit_price': exit_price,
            'qty': pos['qty'],
            'pnl': raw_pnl,
            'pnl_pct': pnl_pct,
            'result': result
        }
        self.paper_trades.append(trade_record)
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🏁 [PAPER EXIT] {symbol} @ ₹{exit_price:.2f} | PnL: ₹{raw_pnl:+.2f} ({pnl_pct:+.2f}%) | {result}")
        return trade_record


if __name__ == "__main__":
    print(f"\n=======================================================")
    print(f"       PAPER TRADING ENGINE: {STRATEGY_NAME}")
    print(f"       Capital: ₹{CONFIG.INITIAL_CAPITAL:,.0f} | Max Slots: {CONFIG.MAX_CONCURRENT_POSITIONS}")
    print(f"=======================================================\n")
    engine = PaperTradingEngine()
    engine.authenticate()
