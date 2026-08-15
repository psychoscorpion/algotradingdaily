"""
Base Live Trading Execution Daemon & Order Management Framework.

Provides shared runtime capabilities:
  - Automated TOTP authentication for Shoonya API
  - Synchronized market clock & 15-minute candle interval scheduler
  - Position lifecycle & trailing stop-loss state machine (+1R -> Breakeven)
  - 15:00 IST auto-squareoff enforcement
"""

import os
import sys
import datetime
# pyrefly: ignore [missing-import]
import pyotp
from typing import Dict, Any, List, Optional
# pyrefly: ignore [missing-import]
from NorenRestApiPy.NorenApi import NorenApi

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import CONFIG, TradingConfig
from data_pipeline import get_nifty50_symbols


class BaseTradingEngine(NorenApi):
    """
    Base trading engine containing shared authentication, market clock,
    position tracking, and risk management logic.
    """
    def __init__(self, config: TradingConfig = CONFIG):
        super().__init__(
            host='https://api.shoonya.com/NorenWSTScript/', 
            websocket='wss://api.shoonya.com/NorenWSTScript/'
        )
        self.config = config
        self.active_positions: Dict[str, Dict[str, Any]] = {}
        self.user = os.getenv("SHOONYA_USER")
        self.pwd = os.getenv("SHOONYA_PWD")
        self.api_key = os.getenv("SHOONYA_API_KEY")
        self.vendor_code = os.getenv("SHOONYA_VENDOR_CODE")
        self.totp_key = os.getenv("SHOONYA_TOTP_KEY")
        self.imei = os.getenv("SHOONYA_IMEI", "shoonya_algo_desktop")

    def authenticate(self) -> bool:
        """Performs automated TOTP authentication with Shoonya or falls back to virtual mode."""
        is_placeholder = (
            not self.user or not self.totp_key or 
            "your_" in (self.user or "").lower() or 
            "your_" in (self.totp_key or "").lower()
        )
        if is_placeholder:
            print("⚠️ Shoonya credentials not configured. Running in Offline Virtual Mode (yfinance feed).")
            return False

        try:
            totp = pyotp.TOTP(self.totp_key).now()
            res = self.login(
                userid=self.user, password=self.pwd, twoFA=totp,
                vendor_code=self.vendor_code, api_secret=self.api_key, imei=self.imei
            )
            if res and res.get('stat') == 'Ok':
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ Authenticated to Shoonya API.")
                return True
            print("❌ Authentication Failed:", res)
            return False
        except Exception as e:
            print(f"⚠️ Shoonya Auth Exception ({e}). Running in Offline Virtual Mode.")
            return False

    def is_entry_window_active(self, now: Optional[datetime.datetime] = None) -> bool:
        """Checks if current time is within allowed entry window (10:00 AM to 1:30 PM)."""
        now = now or datetime.datetime.now()
        t = now.time()
        start = datetime.time(self.config.ENTRY_START_HOUR, 0)
        end = datetime.time(self.config.ENTRY_END_HOUR, self.config.ENTRY_END_MINUTE)
        return start <= t <= end

    def is_squareoff_time(self, now: Optional[datetime.datetime] = None) -> bool:
        """Checks if current time is past mandatory square-off time (3:00 PM)."""
        now = now or datetime.datetime.now()
        t = now.time()
        sq_time = datetime.time(self.config.SQUAREOFF_HOUR, self.config.SQUAREOFF_MINUTE)
        return t >= sq_time

    def get_trading_universe(self) -> List[str]:
        """Returns symbols formatted for Shoonya NSE cash trading (e.g. INFY-EQ)."""
        symbols = get_nifty50_symbols()
        return [f"{s.replace('.NS', '')}-EQ" for s in symbols]

    def sync_active_positions_from_db(self, mode: Optional[str] = None) -> int:
        """Restores open trade state from SQLite database on engine startup/recovery."""
        from core.trade_db import get_active_positions
        saved = get_active_positions(mode=mode)
        for pos in saved:
            self.active_positions[pos['symbol']] = pos
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🔄 State synchronized: {len(self.active_positions)} active position(s) loaded from DB.")
        return len(self.active_positions)
