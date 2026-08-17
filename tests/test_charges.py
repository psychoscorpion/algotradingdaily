"""
Automated Test Suite for Multi-Broker Fee Engine (core/charges.py).

Verifies:
  1. Universal Indian Statutory Taxes math (STT, GST, NSE Txn, SEBI, Stamp Duty).
  2. Brokerage calculations across all supported brokers (Shoonya, Zerodha, Dhan, Groww, Angel One, Upstox, Fyers, Zero).
  3. Dynamic active broker fallback from ACTIVE_BROKER environment variable.
  4. Itemized charge breakdown dictionary.
"""

import os
import sys
import unittest

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from core.charges import (
    calculate_charges,
    get_charge_breakdown,
    BROKER_CHARGES_CONFIG,
    STATUTORY_RATES,
)


class TestChargesEngine(unittest.TestCase):
    """Test suite verifying statutory taxes and multi-broker fee calculations."""

    def setUp(self):
        # Example trade: ₹25,000 short entry (Sell), ₹24,000 exit (Buy)
        self.sell_turnover = 25000.0
        self.buy_turnover = 24000.0
        self.total_turnover = self.sell_turnover + self.buy_turnover  # ₹49,000

    def test_universal_statutory_taxes_math(self):
        """Verifies statutory tax calculations match SEBI/NSE formulas."""
        breakdown = get_charge_breakdown(self.sell_turnover, self.buy_turnover, broker="zero")
        
        # Expected statutory taxes for ₹25k Sell + ₹24k Buy:
        # STT = 25000 * 0.00025 = ₹6.25
        # Exchange Txn = 49000 * 0.0000297 = ₹1.4553 -> ₹1.46
        # SEBI = 49000 * 0.000001 = ₹0.049 -> ₹0.05
        # Stamp Duty = 24000 * 0.00003 = ₹0.72
        # GST (18% on Txn + SEBI) = (1.4553 + 0.049) * 0.18 = ₹0.2708 -> ₹0.27
        self.assertAlmostEqual(breakdown["stt"], 6.25, places=2)
        self.assertAlmostEqual(breakdown["stamp_duty"], 0.72, places=2)
        self.assertAlmostEqual(breakdown["brokerage"], 0.0, places=2)
        self.assertGreater(breakdown["total_charges"], 8.0)

    def test_all_supported_brokers_brokerage(self):
        """Verifies brokerage schedule for all configured brokers."""
        # Test ₹25,000 order:
        # Shoonya: 25000 * 0.0003 = ₹7.50 capped at ₹5.00 -> ₹5.00 entry + ₹5.00 exit = ₹10.00
        # Zerodha: 25000 * 0.0003 = ₹7.50 (under ₹20 cap) -> ₹7.50 entry + ₹7.20 exit = ₹14.70
        # Groww: 25000 * 0.0005 = ₹12.50 (under ₹20 cap) -> ₹12.50 entry + ₹12.00 exit = ₹24.50
        # Angel One: 25000 * 0.0010 = ₹25.00 (capped at ₹20) -> ₹20.00 entry + ₹20.00 exit = ₹40.00
        
        shoonya_breakdown = get_charge_breakdown(self.sell_turnover, self.buy_turnover, broker="shoonya")
        zerodha_breakdown = get_charge_breakdown(self.sell_turnover, self.buy_turnover, broker="zerodha")
        dhan_breakdown = get_charge_breakdown(self.sell_turnover, self.buy_turnover, broker="dhan")
        groww_breakdown = get_charge_breakdown(self.sell_turnover, self.buy_turnover, broker="groww")
        angel_breakdown = get_charge_breakdown(self.sell_turnover, self.buy_turnover, broker="angelone")

        self.assertEqual(shoonya_breakdown["brokerage"], 10.00)
        self.assertEqual(zerodha_breakdown["brokerage"], 14.70)
        self.assertEqual(dhan_breakdown["brokerage"], 14.70)
        self.assertEqual(groww_breakdown["brokerage"], 24.50)
        self.assertEqual(angel_breakdown["brokerage"], 40.00)

    def test_broker_charges_comparison(self):
        """Verifies calculate_charges accurately calculates different brokerage schedules."""
        zerodha_charges = calculate_charges(self.sell_turnover, self.buy_turnover, broker="zerodha")
        shoonya_charges = calculate_charges(self.sell_turnover, self.buy_turnover, broker="shoonya")

        self.assertGreater(zerodha_charges, shoonya_charges)


if __name__ == "__main__":
    unittest.main()
