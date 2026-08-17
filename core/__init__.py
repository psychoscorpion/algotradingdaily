"""
Core Package: Pure mathematical indicators, statutory fee calculators, and trade models.
"""

from .charges import (
    calculate_charges,
    get_charge_breakdown,
    BROKER_CHARGES_CONFIG,
)
from .indicators import (
    add_stoch_rsi,
    add_adx,
    add_vwap,
    add_relative_weakness,
)
from .trade_db import (
    init_db,
    save_active_position,
    update_trailing_sl,
    close_and_archive_position,
    get_active_positions,
    get_trade_journal,
    get_stale_positions,
)

__all__ = [
    "TradingConfig",
    "CONFIG",
    "calculate_charges",
    "get_charge_breakdown",
    "BROKER_CHARGES_CONFIG",
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
    "get_stale_positions",
]
