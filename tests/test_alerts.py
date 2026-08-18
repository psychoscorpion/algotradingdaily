"""
Unit tests for alerts/ notification channels and multi-channel dispatcher.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from dataclasses import replace

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import CONFIG
from alerts.base import BaseAlertChannel
from alerts.telegram import TelegramAlertChannel
from alerts import (
    get_active_channels,
    notify_trade_entry,
    notify_trailing_sl,
    notify_trade_exit,
    notify_eod_summary,
)


class TestAlertsPackage(unittest.TestCase):
    def setUp(self):
        self.original_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.original_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    def tearDown(self):
        if self.original_token is not None:
            os.environ["TELEGRAM_BOT_TOKEN"] = self.original_token
        else:
            os.environ.pop("TELEGRAM_BOT_TOKEN", None)

        if self.original_chat_id is not None:
            os.environ["TELEGRAM_CHAT_ID"] = self.original_chat_id
        else:
            os.environ.pop("TELEGRAM_CHAT_ID", None)

    def test_channel_selection_none(self):
        """Verifies that setting ALERT_CHANNELS = () yields 0 active channels."""
        cfg = replace(CONFIG, ALERT_CHANNELS=())
        channels = get_active_channels(config=cfg)
        self.assertEqual(len(channels), 0)

    def test_channel_selection_tuple(self):
        """Verifies that setting ALERT_CHANNELS = ('telegram',) activates Telegram channel."""
        cfg = replace(CONFIG, ALERT_CHANNELS=("telegram",))
        channels = get_active_channels(config=cfg)
        self.assertEqual(len(channels), 1)
        self.assertIsInstance(channels[0], TelegramAlertChannel)

    def test_channel_selection_string_graceful(self):
        """Verifies that accidental string input ('telegram') without comma is gracefully handled."""
        cfg = replace(CONFIG, ALERT_CHANNELS=("telegram"))  # Single string!
        channels = get_active_channels(config=cfg)
        self.assertEqual(len(channels), 1)
        self.assertIsInstance(channels[0], TelegramAlertChannel)

    def test_telegram_unconfigured_fails_silently(self):
        """Verifies that if Telegram credentials are not set, alerts fail silently."""
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("TELEGRAM_CHAT_ID", None)

        channel = TelegramAlertChannel()
        self.assertFalse(channel.is_configured)
        self.assertFalse(channel.send_message("Test"))

    @patch("requests.post")
    def test_telegram_configured_sends_payload(self, mock_post):
        """Verifies that with valid credentials, TelegramAlertChannel posts markdown payload."""
        os.environ["TELEGRAM_BOT_TOKEN"] = "test_bot_123"
        os.environ["TELEGRAM_CHAT_ID"] = "987654321"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        channel = TelegramAlertChannel(token="bot12345", chat_id="chat999")
        self.assertTrue(channel.is_configured)
        success = channel.send_trade_entry(symbol="ONGC-EQ", price=286.50, sl=288.10, tp=283.30, qty=87, mode="paper")
        
        self.assertTrue(success)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("bot12345", args[0])
        self.assertEqual(kwargs["json"]["chat_id"], "chat999")
        self.assertIn("[PAPER ENTRY]", kwargs["json"]["text"])
        self.assertIn("ONGC-EQ", kwargs["json"]["text"])

    @patch.object(TelegramAlertChannel, "send_trailing_sl")
    def test_notify_trailing_sl_broadcast(self, mock_trail):
        """Verifies dispatcher broadcasts trailing SL alerts."""
        notify_trailing_sl(symbol="RELIANCE-EQ", be_price=1315.00, mode="paper")
        mock_trail.assert_called_once_with(symbol="RELIANCE-EQ", be_price=1315.00, mode="paper")

    @patch.object(TelegramAlertChannel, "send_trade_exit")
    def test_notify_trade_exit_broadcast(self, mock_exit):
        """Verifies dispatcher broadcasts trade exit alerts."""
        notify_trade_exit(symbol="INFY-EQ", price=1450.00, net_pnl=232.50, pnl_pct=1.85, reason="TARGET HIT ✅", mode="paper")
        mock_exit.assert_called_once_with(symbol="INFY-EQ", price=1450.00, net_pnl=232.50, pnl_pct=1.85, reason="TARGET HIT ✅", mode="paper")


if __name__ == "__main__":
    unittest.main()
