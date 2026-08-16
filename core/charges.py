"""
Universal Indian Equity Intraday Statutory & Multi-Broker Fee Engine.

Models complete Indian equity intraday (MIS) transaction costs:
  - Universal Statutory Taxes (SEBI / Govt / NSE mandated):
      * STT: 0.025% on Sell side only
      * Exchange Txn Fee (NSE): 0.00297% on total turnover
      * SEBI Turnover Fee: ₹10 / Crore (0.0001%) on total turnover
      * Stamp Duty: 0.003% on Buy side
      * GST: 18% on (Brokerage + Exchange Txn + SEBI Fees)
  - Declarative Multi-Broker Fee Schedules:
      * Shoonya (Finvasia): min(0.03%, ₹5.00) per order
      * Zerodha: min(0.03%, ₹20.00) per order
      * Dhan: min(0.03%, ₹20.00) per order
      * Fyers: min(0.03%, ₹20.00) per order
      * Groww: min(0.05%, ₹20.00) per order
      * Angel One: min(0.10%, ₹20.00) per order
      * Upstox: min(0.05%, ₹20.00) per order
      * Zero: ₹0.00 baseline
"""

import os
from typing import Dict, Any, Optional

# Declarative Brokerage Schedules for Major Indian Brokers
BROKER_CHARGES_CONFIG: Dict[str, Dict[str, Any]] = {
    "zero": {
        "name": "Zero-Brokerage Baseline",
        "brokerage_pct": 0.0,
        "max_brokerage_per_order": 0.0,
    },
    "shoonya": {
        "name": "Shoonya (Finvasia)",
        "brokerage_pct": 0.0003,      # 0.03%
        "max_brokerage_per_order": 5.00,
    },
    "zerodha": {
        "name": "Zerodha",
        "brokerage_pct": 0.0003,      # 0.03%
        "max_brokerage_per_order": 20.00,
    },
    "dhan": {
        "name": "Dhan",
        "brokerage_pct": 0.0003,      # 0.03%
        "max_brokerage_per_order": 20.00,
    },
    "fyers": {
        "name": "Fyers",
        "brokerage_pct": 0.0003,      # 0.03%
        "max_brokerage_per_order": 20.00,
    },
    "groww": {
        "name": "Groww",
        "brokerage_pct": 0.0005,      # 0.05%
        "max_brokerage_per_order": 20.00,
    },
    "angelone": {
        "name": "Angel One",
        "brokerage_pct": 0.0010,      # 0.10%
        "max_brokerage_per_order": 20.00,
    },
    "upstox": {
        "name": "Upstox",
        "brokerage_pct": 0.0005,      # 0.05%
        "max_brokerage_per_order": 20.00,
    },
}

# Universal Indian Regulatory & Statutory Rates
STATUTORY_RATES = {
    "stt_sell": 0.00025,          # 0.025% on sell side
    "exchange_txn": 0.0000297,    # 0.00297% on total turnover
    "sebi_turnover": 0.000001,    # ₹10 per crore (0.0001%)
    "stamp_duty_buy": 0.00003,    # 0.003% on buy side
    "gst": 0.18,                  # 18% on (Brokerage + Txn + SEBI)
}


def calculate_charges(
    sell_turnover: float,
    buy_turnover: float,
    broker: Optional[str] = None
) -> float:
    """
    Calculates total round-trip statutory taxes and brokerage charges for an intraday equity trade.
    
    Args:
        sell_turnover: Total value of sell side (price * qty)
        buy_turnover: Total value of buy side (price * qty)
        broker: Optional broker key. If None, dynamically resolves from ACTIVE_BROKER env or core.config.
        
    Returns:
        float: Total friction in INR (brokerage + STT + exchange + SEBI + stamp duty + GST)
    """
    active_broker = (broker or os.getenv("ACTIVE_BROKER", "shoonya")).lower()
    rates = BROKER_CHARGES_CONFIG.get(active_broker, BROKER_CHARGES_CONFIG["shoonya"])

    entry_brokerage = min(sell_turnover * rates["brokerage_pct"], rates["max_brokerage_per_order"])
    exit_brokerage = min(buy_turnover * rates["brokerage_pct"], rates["max_brokerage_per_order"])
    total_brokerage = entry_brokerage + exit_brokerage

    total_turnover = sell_turnover + buy_turnover
    stt = sell_turnover * STATUTORY_RATES["stt_sell"]
    exchange_txn = total_turnover * STATUTORY_RATES["exchange_txn"]
    sebi_charges = total_turnover * STATUTORY_RATES["sebi_turnover"]
    stamp_duty = buy_turnover * STATUTORY_RATES["stamp_duty_buy"]
    gst = (total_brokerage + exchange_txn + sebi_charges) * STATUTORY_RATES["gst"]

    return total_brokerage + stt + exchange_txn + sebi_charges + stamp_duty + gst


def get_charge_breakdown(
    sell_turnover: float,
    buy_turnover: float,
    broker: Optional[str] = None
) -> Dict[str, Any]:
    """
    Provides an itemized breakdown dictionary of all individual statutory and brokerage components.
    Useful for trade logging, audit reporting, and detailed trade journals.
    """
    active_broker = (broker or os.getenv("ACTIVE_BROKER", "shoonya")).lower()
    rates = BROKER_CHARGES_CONFIG.get(active_broker, BROKER_CHARGES_CONFIG["shoonya"])

    entry_brokerage = min(sell_turnover * rates["brokerage_pct"], rates["max_brokerage_per_order"])
    exit_brokerage = min(buy_turnover * rates["brokerage_pct"], rates["max_brokerage_per_order"])
    total_brokerage = entry_brokerage + exit_brokerage

    total_turnover = sell_turnover + buy_turnover
    stt = sell_turnover * STATUTORY_RATES["stt_sell"]
    exchange_txn = total_turnover * STATUTORY_RATES["exchange_txn"]
    sebi_charges = total_turnover * STATUTORY_RATES["sebi_turnover"]
    stamp_duty = buy_turnover * STATUTORY_RATES["stamp_duty_buy"]
    gst = (total_brokerage + exchange_txn + sebi_charges) * STATUTORY_RATES["gst"]
    total_charges = total_brokerage + stt + exchange_txn + sebi_charges + stamp_duty + gst

    return {
        "broker": rates["name"],
        "brokerage": round(total_brokerage, 2),
        "stt": round(stt, 2),
        "exchange_txn": round(exchange_txn, 2),
        "sebi": round(sebi_charges, 2),
        "stamp_duty": round(stamp_duty, 2),
        "gst": round(gst, 2),
        "total_charges": round(total_charges, 2),
    }
