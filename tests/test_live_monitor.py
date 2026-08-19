"""
Unit tests for high-frequency position guardian, instant triggers, and precise 3:00 PM squareoff.
"""

import os
import sys
import datetime
import unittest
from unittest.mock import patch, MagicMock

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import TradingConfig
from live_trading.paper_trader import PaperTradingEngine


class TestLivePositionGuardian(unittest.TestCase):
    def setUp(self):
        # Configure test config with zero alert channels so unit tests do not spam real Telegram
        self.config = TradingConfig(ALERT_CHANNELS=())
        self.engine = PaperTradingEngine(config=self.config)
        self.engine.active_positions.clear()

    def test_instant_stop_loss_trigger(self):
        """Verifies that high-frequency tick above Stop-Loss triggers instant SL exit."""
        from core.trade_db import TradeExitReason
        self.engine.active_positions["NESTLEIND-EQ"] = {
            'symbol': 'NESTLEIND-EQ',
            'entry_price': 1471.10,
            'entry_time': '2026-08-18 10:30:00',
            'qty': 16,
            'sl_price': 1476.14,
            'tp_price': 1461.02,
            'risk': 5.04,
            'trailed': False,
            'order_id': 'ORD_1',
            'sl_order_id': 'SL_1'
        }

        # Simulated tick spikes to 1477.00 (above SL of 1476.14)
        trade = self.engine.update_position(symbol="NESTLEIND-EQ", current_ltp=1476.50, high=1477.00, low=1475.00)
        self.assertIsNotNone(trade)
        self.assertEqual(trade['result'], TradeExitReason.SL_HIT)
        self.assertEqual(trade['exit_price'], 1476.14)
        self.assertNotIn("NESTLEIND-EQ", self.engine.active_positions)

    def test_instant_target_trigger(self):
        """Verifies that high-frequency tick at or below Target (1:2 R:R) triggers instant TP exit."""
        from core.trade_db import TradeExitReason
        self.engine.active_positions["HINDUNILVR-EQ"] = {
            'symbol': 'HINDUNILVR-EQ',
            'entry_price': 2039.90,
            'entry_time': '2026-08-18 13:00:00',
            'qty': 12,
            'sl_price': 2046.02,
            'tp_price': 2027.66,
            'risk': 6.12,
            'trailed': False,
            'order_id': 'ORD_2',
            'sl_order_id': 'SL_2'
        }

        # Simulated tick dips to 2025.00 (below TP of 2027.66)
        trade = self.engine.update_position(symbol="HINDUNILVR-EQ", current_ltp=2026.00, high=2035.00, low=2025.00)
        self.assertIsNotNone(trade)
        self.assertEqual(trade['result'], TradeExitReason.TARGET_HIT)
        self.assertEqual(trade['exit_price'], 2027.66)
        self.assertNotIn("HINDUNILVR-EQ", self.engine.active_positions)

    def test_instant_trailing_sl_activation(self):
        """Verifies that when price touches +1R profit, SL is immediately moved to Breakeven."""
        self.engine.active_positions["ONGC-EQ"] = {
            'symbol': 'ONGC-EQ',
            'entry_price': 286.50,
            'entry_time': '2026-08-18 11:00:00',
            'qty': 87,
            'sl_price': 288.10,
            'tp_price': 283.30,
            'risk': 1.60,
            'trailed': False,
            'order_id': 'ORD_3',
            'sl_order_id': 'SL_3'
        }

        # Price dips to 284.90 (exactly entry - risk = +1R) during active trading hours (11:15 AM)
        simulated_now = datetime.datetime(2026, 8, 18, 11, 15, 0)
        trade = self.engine.update_position(symbol="ONGC-EQ", current_ltp=285.00, high=286.00, low=284.80, now=simulated_now)
        self.assertIsNone(trade)  # Position remains open
        self.assertTrue(self.engine.active_positions["ONGC-EQ"]['trailed'])
        self.assertEqual(self.engine.active_positions["ONGC-EQ"]['sl_price'], 286.50)  # Moved to BE

    @patch("live_trading.paper_trader.fetch_latest_tick_price")
    def test_precise_3pm_squareoff_price_resolution(self, mock_tick):
        """Verifies that 3:00 PM square-off uses live market tick price rather than falling back to entry price."""
        from core.trade_db import TradeExitReason
        mock_tick.return_value = {'ltp': 1465.50, 'high': 1466.00, 'low': 1464.00}

        self.engine.active_positions["NESTLEIND-EQ"] = {
            'symbol': 'NESTLEIND-EQ',
            'entry_price': 1471.10,
            'entry_time': '2026-08-18 10:30:00',
            'qty': 16,
            'sl_price': 1476.14,
            'tp_price': 1461.02,
            'risk': 5.04,
            'trailed': False,
            'order_id': 'ORD_4',
            'sl_order_id': 'SL_4'
        }

        # Trigger mandatory 3PM squareoff
        self.engine.squareoff_all_positions()

        # Position should be closed and archived at the mock tick price of 1465.50
        self.assertNotIn("NESTLEIND-EQ", self.engine.active_positions)
        self.assertEqual(len(self.engine.paper_trades), 1)
        closed_trade = self.engine.paper_trades[0]
        self.assertEqual(closed_trade['exit_price'], 1465.50)
        self.assertEqual(closed_trade['result'], TradeExitReason.ALGO_SQUAREOFF_DAY_END)
        self.assertGreater(closed_trade['net_pnl'], 0)  # Profitable short exit!


if __name__ == "__main__":
    unittest.main()
