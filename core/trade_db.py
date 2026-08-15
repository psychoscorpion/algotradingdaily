"""
Core Trade Persistence & Journaling Database Module.

Provides SQLite persistence layer for algorithmic trading:
  - Physical database isolation between Paper Trading (database/paper_trades.db)
    and Live Real-Money Trading (database/live_trades.db).
  - 2-Table Schema:
      1. active_positions: Open position tracking & crash recovery state.
      2. trade_history: Permanent trading journal storing completed trade PnL & fees.
  - Safe self-test probe with guaranteed zero-pollution cleanup.
"""

import os
import sys
import sqlite3
import datetime
from typing import List, Dict, Any, Optional

# Ensure workspace root is in sys.path for direct script execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from core.config import CONFIG, TradingConfig

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_DIR = os.path.join(BASE_DIR, "database")


def get_db_path(mode: Optional[str] = None) -> str:
    """Returns absolute path to the SQLite database file for the given mode (defaults to CONFIG.TRADING_MODE)."""
    selected_mode = (mode or CONFIG.TRADING_MODE).lower()
    os.makedirs(DB_DIR, exist_ok=True)
    if selected_mode == "live":
        return os.path.join(DB_DIR, "live_trades.db")
    return os.path.join(DB_DIR, "paper_trades.db")


def init_db(mode: Optional[str] = None) -> None:
    """
    Initializes the 2-table schema for the specified mode if not already present.
    """
    db_path = get_db_path(mode)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Active Positions Table (for live monitoring & crash recovery)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_positions (
                symbol TEXT PRIMARY KEY,
                order_type TEXT DEFAULT 'BO',
                entry_order_id TEXT,
                sl_order_id TEXT,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                initial_sl REAL NOT NULL,
                current_sl REAL NOT NULL,
                target_price REAL NOT NULL,
                status TEXT DEFAULT 'ACTIVE',
                entry_time TEXT NOT NULL
            )
        """)
        
        # 2. Trade History Table (Permanent closed-trade journal)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                order_type TEXT DEFAULT 'BO',
                entry_time TEXT NOT NULL,
                exit_time TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                result TEXT NOT NULL,
                gross_pnl REAL NOT NULL,
                taxes_fees REAL NOT NULL,
                net_pnl REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def save_active_position(
    symbol: str,
    entry_order_id: Optional[str],
    sl_order_id: Optional[str],
    qty: int,
    entry_p: float,
    sl_p: float,
    tp_p: float,
    order_type: str = "BO",
    mode: str = "paper"
) -> None:
    """Persists a newly opened position in active_positions table."""
    init_db(mode)
    db_path = get_db_path(mode)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO active_positions 
            (symbol, order_type, entry_order_id, sl_order_id, quantity, entry_price, initial_sl, current_sl, target_price, status, entry_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
        """, (
            symbol, order_type, str(entry_order_id or ""), str(sl_order_id or ""),
            int(qty), float(entry_p), float(sl_p), float(sl_p), float(tp_p), now_str
        ))
        conn.commit()


def update_trailing_sl(symbol: str, new_sl_price: float, mode: str = "paper") -> bool:
    """Updates Stop Loss level when trailing to breakeven."""
    init_db(mode)
    db_path = get_db_path(mode)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE active_positions 
            SET current_sl = ?, status = 'TRAILING'
            WHERE symbol = ?
        """, (float(new_sl_price), symbol))
        conn.commit()
        return cursor.rowcount > 0


def close_and_archive_position(
    symbol: str,
    exit_price: float,
    exit_time: str,
    result: str,
    gross_pnl: float,
    taxes_fees: float,
    net_pnl: float,
    mode: str = "paper"
) -> bool:
    """
    Atomically closes an active position and inserts the completed trade
    into the trade_history journal.
    """
    init_db(mode)
    db_path = get_db_path(mode)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Fetch active position details
        cursor.execute("SELECT * FROM active_positions WHERE symbol = ?", (symbol,))
        pos = cursor.fetchone()
        
        if not pos:
            return False
            
        pos_dict = dict(pos)
        
        # 2. Insert into permanent trade_history
        cursor.execute("""
            INSERT INTO trade_history 
            (symbol, order_type, entry_time, exit_time, entry_price, exit_price, quantity, result, gross_pnl, taxes_fees, net_pnl, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol,
            pos_dict.get("order_type", "BO"),
            pos_dict.get("entry_time", now_str),
            exit_time,
            float(pos_dict.get("entry_price", 0.0)),
            float(exit_price),
            int(pos_dict.get("quantity", 1)),
            result,
            float(gross_pnl),
            float(taxes_fees),
            float(net_pnl),
            now_str
        ))
        
        # 3. Delete from active_positions
        cursor.execute("DELETE FROM active_positions WHERE symbol = ?", (symbol,))
        conn.commit()
        return True


def get_active_positions(mode: str = "paper") -> List[Dict[str, Any]]:
    """Retrieves all open trades on startup or health check."""
    init_db(mode)
    db_path = get_db_path(mode)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM active_positions WHERE status != 'CLOSED'")
        return [dict(row) for row in cursor.fetchall()]


def get_trade_journal(mode: str = "paper", limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieves completed trade records from trade_history."""
    init_db(mode)
    db_path = get_db_path(mode)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trade_history ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]


if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    print("\n=======================================================")
    print("       RUNNING TRADE_DB ISOLATED VERIFICATION TEST")
    print("=======================================================\n")
    
    test_probe_symbol = f"__TEST_PROBE_{int(datetime.datetime.now().timestamp())}__"
    
    for test_mode in ["paper", "live"]:
        print(f"[*] Testing database mode: '{test_mode}' -> {get_db_path(test_mode)}")
        init_db(mode=test_mode)
        
        # 1. Measure baseline
        initial_active = len(get_active_positions(mode=test_mode))
        initial_history = len(get_trade_journal(mode=test_mode))
        
        # 2. Create probe position
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
        assert len(get_active_positions(mode=test_mode)) == initial_active + 1, "Failed to insert probe active position"
        
        # 3. Update trailing SL
        trailed = update_trailing_sl(symbol=test_probe_symbol, new_sl_price=1500.0, mode=test_mode)
        assert trailed, "Failed to update trailing SL"
        
        # 4. Close and archive position
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
        assert archived, "Failed to archive probe position"
        assert len(get_active_positions(mode=test_mode)) == initial_active, "Active positions count mismatch after close"
        assert len(get_trade_journal(mode=test_mode)) == initial_history + 1, "Trade history count mismatch after archive"
        
        # 5. Targeted probe cleanup (zero pollution)
        db_path = get_db_path(test_mode)
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM active_positions WHERE symbol = ?", (test_probe_symbol,))
            cursor.execute("DELETE FROM trade_history WHERE symbol = ?", (test_probe_symbol,))
            conn.commit()
            
        final_active = len(get_active_positions(mode=test_mode))
        final_history = len(get_trade_journal(mode=test_mode))
        assert final_active == initial_active, f"Active table leaked rows! ({final_active} != {initial_active})"
        assert final_history == initial_history, f"History table leaked rows! ({final_history} != {initial_history})"
        
        print(f"    ✅ '{test_mode}' DB verified: CRUD, Atomic Archiving & Zero-Pollution Cleanup Passed.")
        
    print("\n=======================================================")
    print("       ALL DATABASE CRUD & ISOLATION TESTS PASSED")
    print("=======================================================\n")
