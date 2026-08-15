"""
Shoonya Statutory & Regulatory Charges Calculator.

Models complete Indian equity intraday (MIS) transaction costs for Shoonya (Finvasia):
  - Brokerage: min(0.03%, ₹5.00) per executed order
  - STT: 0.025% on Sell side only
  - Exchange Txn Fee (NSE): 0.00297% on total turnover
  - SEBI Turnover Fee: ₹10 / Crore (0.0001%)
  - Stamp Duty: 0.003% on Buy side
  - GST: 18% on (Brokerage + Exchange Txn + SEBI Fees)
"""


def calculate_shoonya_charges(sell_turnover: float, buy_turnover: float) -> float:
    """
    Calculates total round-trip statutory and brokerage charges for an intraday equity trade.
    
    Args:
        sell_turnover: Total value of sell side (price * qty)
        buy_turnover: Total value of buy side (price * qty)
        
    Returns:
        float: Total friction in INR (brokerage + STT + exchange + SEBI + stamp duty + GST)
    """
    entry_brokerage = min(sell_turnover * 0.0003, 5.00)
    exit_brokerage = min(buy_turnover * 0.0003, 5.00)
    total_brokerage = entry_brokerage + exit_brokerage

    total_turnover = sell_turnover + buy_turnover
    stt = sell_turnover * 0.00025
    exchange_txn = total_turnover * 0.0000297
    sebi_charges = total_turnover * 0.000001
    stamp_duty = buy_turnover * 0.00003
    gst = (total_brokerage + exchange_txn + sebi_charges) * 0.18

    total_charges = total_brokerage + stt + exchange_txn + sebi_charges + stamp_duty + gst
    return total_charges


def get_charge_breakdown(sell_turnover: float, buy_turnover: float) -> dict:
    """
    Provides an itemized breakdown dictionary of all individual statutory components.
    Useful for trade logging, audit reporting, and detailed trade journals.
    """
    entry_brokerage = min(sell_turnover * 0.0003, 5.00)
    exit_brokerage = min(buy_turnover * 0.0003, 5.00)
    total_brokerage = entry_brokerage + exit_brokerage

    total_turnover = sell_turnover + buy_turnover
    stt = sell_turnover * 0.00025
    exchange_txn = total_turnover * 0.0000297
    sebi_charges = total_turnover * 0.000001
    stamp_duty = buy_turnover * 0.00003
    gst = (total_brokerage + exchange_txn + sebi_charges) * 0.18
    total_charges = total_brokerage + stt + exchange_txn + sebi_charges + stamp_duty + gst

    return {
        "brokerage": round(total_brokerage, 2),
        "stt": round(stt, 2),
        "exchange_txn": round(exchange_txn, 2),
        "sebi": round(sebi_charges, 2),
        "stamp_duty": round(stamp_duty, 2),
        "gst": round(gst, 2),
        "total_charges": round(total_charges, 2),
    }
