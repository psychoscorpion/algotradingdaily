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

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from config import CONFIG, TradingConfig
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

    def is_market_open(self, now: Optional[datetime.datetime] = None) -> bool:
        """Checks if current time is within official NSE trading session (09:15 to 15:30 IST on weekdays)."""
        now = now or datetime.datetime.now()
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        t = now.time()
        market_open = datetime.time(9, 15)
        market_close = datetime.time(15, 30)
        return market_open <= t <= market_close

    def is_market_closed(self, now: Optional[datetime.datetime] = None) -> bool:
        """Checks if today's session has completely concluded (past 15:30 IST or weekend)."""
        now = now or datetime.datetime.now()
        if now.weekday() >= 5:
            return True
        return now.time() >= datetime.time(15, 30)

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

    def get_seconds_until_next_candle(self, interval_mins: int = 15, now: Optional[datetime.datetime] = None) -> int:
        """
        Calculates exact seconds remaining until the next 15-minute candle boundary (:00, :15, :30, :45).
        Adds a small 3-second buffer to guarantee the candle bar has officially closed.
        """
        now = now or datetime.datetime.now()
        current_minute = now.minute
        current_second = now.second
        
        minutes_into_interval = current_minute % interval_mins
        minutes_remaining = interval_mins - minutes_into_interval - 1
        seconds_remaining = (minutes_remaining * 60) + (60 - current_second) + 3
        return max(seconds_remaining, 5)

    def get_trading_universe(self) -> List[str]:
        """Returns symbols formatted for Shoonya NSE cash trading (e.g. INFY-EQ)."""
        symbols = get_nifty50_symbols()
        return [f"{s.replace('.NS', '')}-EQ" for s in symbols]

    def sync_active_positions_from_db(self, mode: Optional[str] = None) -> int:
        """Restores open trade state from SQLite database on engine startup/recovery and logs sanity diagnostics."""
        from core.trade_db import get_active_positions, get_stale_positions, get_db_path
        
        target_mode = (mode or self.config.TRADING_MODE).lower()
        db_path = get_db_path(target_mode)
        
        # 1. Startup Sanity Diagnostics: Detect unclosed trades from previous calendar sessions
        stale_positions = get_stale_positions(mode=target_mode)
        if stale_positions:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ⚠️ WARNING: Detected {len(stale_positions)} stale/orphan position(s) from past session(s) in {db_path}:")
            for sp in stale_positions:
                sym = sp.get('symbol', 'UNKNOWN')
                ent = sp.get('entry_time', '')
                qty = sp.get('quantity', 0)
                ep = sp.get('entry_price', 0.0)
                age = sp.get('age_str', 'N/A')
                print(f"    • {sym:<12} | Entry: {ent} | Qty: {qty:>3} | Entry Price: ₹{ep:>8,.2f} | Age: {age}")
            print(f"    ℹ️  Note: Stale positions are retained for audit and will be resolved in pre-market reconciliation.")
        else:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ Database Sanity Check: 0 stale positions detected in {db_path}.")

        # 2. Restore active positions into in-memory state
        saved = get_active_positions(mode=target_mode)
        for pos in saved:
            self.active_positions[pos['symbol']] = pos
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🔄 State synchronized: {len(self.active_positions)} active position(s) loaded from DB.")
        return len(self.active_positions)
