"""
Telegram Notification Channel Implementation.
"""

import os
import requests
import datetime
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
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        # Format for HTML delivery (HTML parse mode avoids Telegram markdown underscore / dash collision errors)
        html_text = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("*", "<b>", 1)
            .replace("*", "</b>", 1)
            .replace("`", "<code>", 1)
            .replace("`", "</code>", 1)
        )
        payload["text"] = text

        try:
            # First try sending as Markdown
            payload["parse_mode"] = "Markdown"
            res = requests.post(url, json=payload, timeout=8)
            
            if res.status_code == 200:
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 📱 [TELEGRAM] Alert delivered successfully to {self.chat_id}.")
                return True
            else:
                # Fallback: send as raw plain text if Telegram rejected markdown tags
                payload.pop("parse_mode", None)
                fallback_res = requests.post(url, json=payload, timeout=8)
                if fallback_res.status_code == 200:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 📱 [TELEGRAM] Alert delivered via plain-text fallback.")
                    return True
                else:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ⚠️ [TELEGRAM ERROR] Status {fallback_res.status_code}: {fallback_res.text}")
                    return False
        except Exception as e:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ⚠️ [TELEGRAM EXCEPTION] {e}")
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
            f"📊 *[{mode.upper()} EOD REPORT]*\n\n"
            f"{report_text}"
        )
        return self.send_message(msg)
