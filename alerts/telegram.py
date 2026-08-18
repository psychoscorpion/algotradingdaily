"""
Telegram Notification Channel Implementation.
"""

import os
import requests
from typing import Optional
from alerts.base import BaseAlertChannel


class TelegramAlertChannel(BaseAlertChannel):
    """Dispatches formatted Markdown trade alerts to Telegram."""

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send_message(self, text: str) -> bool:
        if not self.is_configured:
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        try:
            res = requests.post(url, json=payload, timeout=5)
            return res.status_code == 200
        except Exception:
            return False

    def send_trade_entry(self, symbol: str, price: float, sl: float, tp: float, qty: int, mode: str = "paper") -> bool:
        msg = (
            f"🔔 *[{mode.upper()} ENTRY]* `{symbol}`\n"
            f"• *Side:* SHORT (Sell)\n"
            f"• *Price:* ₹{price:,.2f}\n"
            f"• *Quantity:* {qty}\n"
            f"• *Stop-Loss:* ₹{sl:,.2f}\n"
            f"• *Target:* ₹{tp:,.2f} (1:2 R:R)"
        )
        return self.send_message(msg)

    def send_trailing_sl(self, symbol: str, be_price: float, mode: str = "paper") -> bool:
        msg = (
            f"🛡️ *[{mode.upper()} TRAILING SL]* `{symbol}`\n"
            f"Reached +1R profit! Stop-Loss moved to Breakeven @ ₹{be_price:,.2f}."
        )
        return self.send_message(msg)

    def send_trade_exit(self, symbol: str, price: float, net_pnl: float, pnl_pct: float, reason: str, mode: str = "paper") -> bool:
        icon = "✅" if net_pnl > 0 else "❌"
        msg = (
            f"{icon} *[{mode.upper()} EXIT]* `{symbol}`\n"
            f"• *Exit Price:* ₹{price:,.2f}\n"
            f"• *Net PnL:* ₹{net_pnl:+,.2f} ({pnl_pct:+.2f}%)\n"
            f"• *Result:* {reason}"
        )
        return self.send_message(msg)

    def send_eod_summary(self, report_text: str, mode: str = "paper") -> bool:
        msg = (
            f"📊 *[{mode.upper()} EOD REPORT]*\n"
            f"```\n{report_text}\n```"
        )
        return self.send_message(msg)
