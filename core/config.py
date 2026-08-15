"""
Core Trading System Configuration.

Provides centralized, typed configuration parameters across backtesting,
data pipelines, strategy evaluation, and live trading execution.
Values can be overridden seamlessly via environment variables in .env.
"""

import os
from dataclasses import dataclass
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class TradingConfig:
    # Portfolio Capital & Allocation
    INITIAL_CAPITAL: float = float(os.getenv("INITIAL_CAPITAL", "10000.0"))
    MAX_CONCURRENT_POSITIONS: int = int(os.getenv("MAX_CONCURRENT_POSITIONS", "2"))
    LEVERAGE_MIS: int = int(os.getenv("LEVERAGE_MIS", "5"))

    # Market Data & Timeframe Settings
    TIMEFRAME: str = os.getenv("TIMEFRAME", "15m")
    BACKTEST_PERIOD: str = os.getenv("BACKTEST_PERIOD", "60d")

    # Strategy Entry Timing Windows (IST)
    ENTRY_START_HOUR: int = int(os.getenv("ENTRY_START_HOUR", "10"))
    ENTRY_END_HOUR: int = int(os.getenv("ENTRY_END_HOUR", "13"))
    ENTRY_END_MINUTE: int = int(os.getenv("ENTRY_END_MINUTE", "30"))

    # Intraday Auto-Squareoff Timing (IST)
    SQUAREOFF_HOUR: int = int(os.getenv("SQUAREOFF_HOUR", "15"))
    SQUAREOFF_MINUTE: int = int(os.getenv("SQUAREOFF_MINUTE", "0"))

    # Live Trading & Database Execution Mode (paper = Virtual Sandbox, live = Real Money OMS)
    TRADING_MODE: str = os.getenv("TRADING_MODE", "paper").lower()

    # Order Execution Mode (BO = Bracket Order with exchange protection, MIS = Standard Margin)
    ORDER_TYPE: str = os.getenv("ORDER_TYPE", "BO").upper()

    # Risk Management Settings
    MIN_SL_BUFFER_PCT: float = float(os.getenv("MIN_SL_BUFFER_PCT", "0.002"))  # 0.2% min SL buffer
    SWING_HIGH_BARS: int = int(os.getenv("SWING_HIGH_BARS", "3"))             # 3-bar swing high
    RISK_REWARD_RATIO: float = float(os.getenv("RISK_REWARD_RATIO", "2.0"))   # 1:2 R:R target

    # Computed Properties
    @property
    def per_trade_margin(self) -> float:
        """Cash margin allocated per open position slot."""
        return self.INITIAL_CAPITAL / self.MAX_CONCURRENT_POSITIONS

    @property
    def per_trade_exposure(self) -> float:
        """Total purchasing power / exposure per trade using intraday MIS leverage."""
        return self.per_trade_margin * self.LEVERAGE_MIS


# Global Default Singleton Instance
CONFIG = TradingConfig()
