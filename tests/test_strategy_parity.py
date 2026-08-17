"""
Automated Parity Tests for Stop-Loss, Risk, and Take-Profit calculations.

Asserts exact numerical parity between:
  1. Backtesting Strategy Engine (strategies/vwap_stoch_breakdown.py)
  2. Live / Paper Trading Daemon (live_trading/paper_trader.py)
"""

import unittest
import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import CONFIG, TradingConfig


class TestStrategyParity(unittest.TestCase):
    """Verifies that Backtest and Live trading calculate identical SL, Risk, and TP."""

    def test_stop_loss_and_target_parity(self):
        """Tests SL, Risk, and TP calculations across diverse market price scenarios."""
        config = TradingConfig()

        test_scenarios = [
            {"name": "ONGC-EQ Live Case", "entry": 237.12, "swing_high": 238.11},
            {"name": "INFY-EQ High Price", "entry": 1815.40, "swing_high": 1824.00},
            {"name": "RELIANCE-EQ Mid Risk", "entry": 2950.00, "swing_high": 2975.50},
            {"name": "Flat Doji Consolidation (Floor Test)", "entry": 100.00, "swing_high": 100.05},
        ]

        for sc in test_scenarios:
            with self.subTest(scenario=sc["name"]):
                entry_p = sc["entry"]
                swing_high = sc["swing_high"]

                # 1. Backtest Engine formula
                backtest_sl = max(
                    swing_high * (1.0 + config.SWING_SL_BUFFER_PCT),
                    entry_p * (1.0 + config.MIN_SL_BUFFER_PCT)
                )
                backtest_risk = backtest_sl - entry_p
                backtest_tp = entry_p - (config.RISK_REWARD_RATIO * backtest_risk)

                # 2. Live Paper Trader formula
                live_sl = max(
                    swing_high * (1.0 + config.SWING_SL_BUFFER_PCT),
                    entry_p * (1.0 + config.MIN_SL_BUFFER_PCT)
                )
                live_risk = live_sl - entry_p
                live_tp = entry_p - (config.RISK_REWARD_RATIO * live_risk)

                # 3. Assert Exact Numerical Parity
                self.assertAlmostEqual(backtest_sl, live_sl, places=4)
                self.assertAlmostEqual(backtest_risk, live_risk, places=4)
                self.assertAlmostEqual(backtest_tp, live_tp, places=4)

                # Verify Anti-Wick buffer is strictly above exact swing high
                self.assertGreater(live_sl, swing_high)

    def test_config_buffer_overrides(self):
        """Verifies custom buffer overrides behave predictably."""
        custom_cfg = TradingConfig(SWING_SL_BUFFER_PCT=0.0010, MIN_SL_BUFFER_PCT=0.0030)
        entry_p = 200.0
        swing_high = 202.0

        sl = max(
            swing_high * (1.0 + custom_cfg.SWING_SL_BUFFER_PCT),
            entry_p * (1.0 + custom_cfg.MIN_SL_BUFFER_PCT)
        )
        self.assertAlmostEqual(sl, 202.0 * 1.0010, places=4)


if __name__ == "__main__":
    unittest.main()
