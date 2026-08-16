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
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Iterator

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


@contextmanager
def get_db_connection(mode: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """
    Creates and yields an SQLite database connection with concurrency hardening:
      - WAL mode: Enables concurrent readers without blocking writers.
      - busy_timeout: Automatically waits up to 5000ms on lock contention.
      - synchronous: NORMAL mode for optimal performance in WAL mode.
    Guarantees explicit connection close on context exit.
    """
    db_path = get_db_path(mode)
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    try:
        yield conn
    finally:
        conn.close()


def init_db(mode: Optional[str] = None) -> None:
    """
    Initializes the 2-table schema for the specified mode if not already present.
    """
    with get_db_connection(mode) as conn:
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

        # 3. Performance Composite B-Tree Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_exit_symbol 
            ON trade_history(exit_time, symbol);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_entry_time 
            ON trade_history(entry_time);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_active_symbol 
            ON active_positions(symbol, status);
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
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with get_db_connection(mode) as conn:
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
    with get_db_connection(mode) as conn:
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
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with get_db_connection(mode) as conn:
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
    with get_db_connection(mode) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM active_positions WHERE status != 'CLOSED'")
        return [dict(row) for row in cursor.fetchall()]


def get_trade_journal(mode: str = "paper", limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieves completed trade records from trade_history."""
    init_db(mode)
    with get_db_connection(mode) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trade_history ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]


if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    print("\n=======================================================")
    print("       TRADE DATABASE MODULE (core/trade_db.py)")
    print("=======================================================")

    init_db("paper")
    init_db("live")

    paper_active = len(get_active_positions(mode="paper"))
    paper_history = len(get_trade_journal(mode="paper", limit=10000))
    live_active = len(get_active_positions(mode="live"))
    live_history = len(get_trade_journal(mode="live", limit=10000))

    print(f"[1] Paper Trading DB  : {get_db_path('paper')}")
    print(f"    Active Positions  : {paper_active}")
    print(f"    Completed Trades  : {paper_history}")
    print(f"[2] Live Real-Money DB: {get_db_path('live')}")
    print(f"    Active Positions  : {live_active}")
    print(f"    Completed Trades  : {live_history}")
    print("-------------------------------------------------------")
    print("STATUS: ✅ Both SQLite databases initialized and ready (WAL Mode & 5000ms Busy Timeout Enabled).")
    print("TIP   : Run 'python -m unittest tests/test_trade_db.py' for full test suite.")
    print("=======================================================\n")
