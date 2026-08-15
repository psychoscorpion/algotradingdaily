"""
Strategies Package: Modular trading strategy definitions and signal generators.
"""

from .vwap_stoch_breakdown import (
    STRATEGY_NAME,
    STRATEGY_VERSION,
    evaluate_signals,
    simulate_single_trade,
)

__all__ = [
    "STRATEGY_NAME",
    "STRATEGY_VERSION",
    "evaluate_signals",
    "simulate_single_trade",
]
