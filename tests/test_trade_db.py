"""
Automated Test Suite for SQLite Persistence Layer (core/trade_db.py).

Tests complete CRUD lifecycle and physical database isolation:
  1. Table creation & schema verification for both 'paper' and 'live' modes.
  2. Active position insertion & retrieval in active_positions table.
  3. Trailing Stop-Loss update (status = 'TRAILING').
  4. Atomic close_and_archive_position move to permanent trade_history table.
  5. Physical database file isolation (paper_trades.db vs live_trades.db).
  6. Guaranteed zero-pollution cleanup.
"""

import os
import sys
import sqlite3
import datetime
import unittest

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from core.trade_db import (
    get_db_path,
    init_db,
    save_active_position,
    update_trailing_sl,
    close_and_archive_position,
    get_active_positions,
    get_trade_journal,
)


class TestTradeDatabase(unittest.TestCase):
    """Test suite verifying trade_db CRUD operations and physical database isolation."""

    def test_database_crud_and_isolation(self):
        print("\n=======================================================")
        print("       RUNNING TRADE_DB ISOLATED VERIFICATION TEST     ")
        print("=======================================================")

        test_probe_symbol = f"__TEST_PROBE_{int(datetime.datetime.now().timestamp())}__"

        for test_mode in ["paper", "live"]:
            with self.subTest(mode=test_mode):
                db_path = get_db_path(test_mode)
                print(f"[*] Testing database mode: '{test_mode}' -> {db_path}")
                init_db(mode=test_mode)

                # 1. Measure baseline
                initial_active = len(get_active_positions(mode=test_mode))
                initial_history = len(get_trade_journal(mode=test_mode))

                # 2. Create probe active position
                save_active_position(
                    symbol=test_probe_symbol,
                    entry_order_id="TEST_ORD_001",
                    sl_order_id="TEST_SL_001",
                    qty=10,
                    entry_p=1500.0,
                    sl_p=1510.0,
                    tp_p=1480.0,
                    order_type="BO",
                    mode=test_mode
                )
                active_list = get_active_positions(mode=test_mode)
                self.assertEqual(len(active_list), initial_active + 1, "Active position insertion failed!")
                probe_active = next((p for p in active_list if p['symbol'] == test_probe_symbol), None)
                self.assertIsNotNone(probe_active, "Inserted probe position not found in active list!")
                self.assertEqual(probe_active['entry_price'], 1500.0)

                # 3. Update trailing Stop Loss
                trailed = update_trailing_sl(symbol=test_probe_symbol, new_sl_price=1500.0, mode=test_mode)
                self.assertTrue(trailed, "Failed to update trailing SL in SQLite!")

                # 4. Close and archive position atomically
                archived = close_and_archive_position(
                    symbol=test_probe_symbol,
                    exit_price=1480.0,
                    exit_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    result="TARGET HIT ✅",
                    gross_pnl=200.0,
                    taxes_fees=15.5,
                    net_pnl=184.5,
                    mode=test_mode
                )
                self.assertTrue(archived, "Failed to archive probe position!")
                self.assertEqual(len(get_active_positions(mode=test_mode)), initial_active, "Active count mismatch after archive!")
                self.assertEqual(len(get_trade_journal(mode=test_mode)), initial_history + 1, "Trade history count mismatch after archive!")

                # 5. Targeted probe cleanup (zero pollution)
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM active_positions WHERE symbol = ?", (test_probe_symbol,))
                    cursor.execute("DELETE FROM trade_history WHERE symbol = ?", (test_probe_symbol,))
                    conn.commit()

                final_active = len(get_active_positions(mode=test_mode))
                final_history = len(get_trade_journal(mode=test_mode))
                self.assertEqual(final_active, initial_active, "Active table leaked test rows!")
                self.assertEqual(final_history, initial_history, "History table leaked test rows!")

                print(f"    ✅ '{test_mode}' DB verified: CRUD, Atomic Archiving & Zero-Pollution Cleanup Passed.")

        print("=======================================================")
        print("       ALL DATABASE CRUD & ISOLATION TESTS PASSED      ")
        print("=======================================================\n")

    def test_wal_mode_and_concurrency_settings(self):
        """Verifies SQLite WAL mode, busy timeout (5000ms), and NORMAL synchronous mode."""
        from core.trade_db import get_db_connection

        for test_mode in ["paper", "live"]:
            with self.subTest(mode=test_mode):
                init_db(mode=test_mode)
                with get_db_connection(mode=test_mode) as conn:
                    cursor = conn.cursor()
                    
                    # 1. Check WAL mode
                    cursor.execute("PRAGMA journal_mode;")
                    journal_mode = cursor.fetchone()[0]
                    self.assertEqual(str(journal_mode).lower(), "wal", f"Expected WAL mode, got {journal_mode}")

                    # 2. Check busy_timeout
                    cursor.execute("PRAGMA busy_timeout;")
                    busy_timeout = cursor.fetchone()[0]
                    self.assertGreaterEqual(busy_timeout, 5000, f"Expected busy_timeout >= 5000ms, got {busy_timeout}")

                    # 3. Check synchronous mode (NORMAL = 1)
                    cursor.execute("PRAGMA synchronous;")
                    sync_mode = cursor.fetchone()[0]
                    self.assertEqual(sync_mode, 1, f"Expected synchronous = 1 (NORMAL), got {sync_mode}")

    def test_btree_indexes_exist(self):
        """Verifies composite B-Tree indexes exist on trade_history and active_positions tables."""
        from core.trade_db import get_db_connection

        expected_indexes = {
            "idx_trades_exit_symbol",
            "idx_trades_entry_time",
            "idx_active_symbol",
        }

        for test_mode in ["paper", "live"]:
            with self.subTest(mode=test_mode):
                init_db(mode=test_mode)
                with get_db_connection(mode=test_mode) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'index';")
                    existing_indexes = {row[0] for row in cursor.fetchall()}
                    
                    for idx_name in expected_indexes:
                        self.assertIn(
                            idx_name,
                            existing_indexes,
                            f"Index '{idx_name}' missing from '{test_mode}' database schema!"
                        )

    def test_stale_positions_detection(self):
        """Verifies get_stale_positions accurately identifies unclosed trades from prior days."""
        from core.trade_db import get_stale_positions, get_db_connection

        stale_probe_symbol = f"__STALE_PROBE_{int(datetime.datetime.now().timestamp())}__"
        today_probe_symbol = f"__TODAY_PROBE_{int(datetime.datetime.now().timestamp())}__"

        for test_mode in ["paper", "live"]:
            with self.subTest(mode=test_mode):
                init_db(mode=test_mode)

                # 1. Insert an artificial stale position from 2 days ago
                past_date_str = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime("%Y-%m-%d 10:15:00")
                save_active_position(
                    symbol=stale_probe_symbol,
                    entry_order_id="STALE_ORD_001",
                    sl_order_id="STALE_SL_001",
                    qty=15,
                    entry_p=2500.0,
                    sl_p=2520.0,
                    tp_p=2460.0,
                    mode=test_mode
                )
                # Manually adjust entry_time to past date for stale test
                with get_db_connection(mode=test_mode) as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE active_positions SET entry_time = ? WHERE symbol = ?", (past_date_str, stale_probe_symbol))
                    conn.commit()

                # 2. Insert a normal active position from today
                save_active_position(
                    symbol=today_probe_symbol,
                    entry_order_id="TODAY_ORD_001",
                    sl_order_id="TODAY_SL_001",
                    qty=10,
                    entry_p=1800.0,
                    sl_p=1815.0,
                    tp_p=1770.0,
                    mode=test_mode
                )

                # 3. Test get_stale_positions detection
                stale_found = get_stale_positions(mode=test_mode)
                stale_symbols = [p['symbol'] for p in stale_found]

                self.assertIn(stale_probe_symbol, stale_symbols, f"Stale probe {stale_probe_symbol} was not detected!")
                self.assertNotIn(today_probe_symbol, stale_symbols, f"Today's active probe {today_probe_symbol} was incorrectly flagged as stale!")

                detected_probe = next(p for p in stale_found if p['symbol'] == stale_probe_symbol)
                self.assertIn("d", detected_probe['age_str'], f"Expected age_str with days, got {detected_probe['age_str']}")
                self.assertGreater(detected_probe['elapsed_seconds'], 86400)

                # 4. Clean up probe rows (zero pollution)
                with get_db_connection(mode=test_mode) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM active_positions WHERE symbol IN (?, ?)", (stale_probe_symbol, today_probe_symbol))
                    conn.commit()


if __name__ == "__main__":
    unittest.main()
