"""
Core Package: Pure mathematical indicators, statutory fee calculators, configuration, and trade models.
"""

from .charges import calculate_shoonya_charges, get_charge_breakdown
from .indicators import (
    add_stoch_rsi,
    add_adx,
    add_vwap,
    add_relative_weakness,
)
from .config import TradingConfig, CONFIG
from .trade_db import (
    init_db,
    save_active_position,
    update_trailing_sl,
    close_and_archive_position,
    get_active_positions,
    get_trade_journal,
)

__all__ = [
    "TradingConfig",
    "CONFIG",
    "calculate_shoonya_charges",
    "get_charge_breakdown",
    "add_stoch_rsi",
    "add_adx",
    "add_vwap",
    "add_relative_weakness",
    "init_db",
    "save_active_position",
    "update_trailing_sl",
    "close_and_archive_position",
    "get_active_positions",
    "get_trade_journal",
]
