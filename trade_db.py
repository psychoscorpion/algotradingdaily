import sqlite3
import datetime

DB_NAME = "trade_state.db"

def init_db():
    """Create the trade persistence table if not present"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_positions (
                symbol TEXT PRIMARY KEY,
                entry_order_id TEXT,
                sl_order_id TEXT,
                quantity INTEGER,
                entry_price REAL,
                initial_sl REAL,
                current_sl REAL,
                target_price REAL,
                status TEXT,          -- 'ACTIVE', 'TRAILING', 'CLOSED'
                entry_time TEXT
            )
        """)
        conn.commit()

def save_new_position(symbol, entry_ord_id, sl_ord_id, qty, entry_p, sl_p, tp_p):
    """Persist new trade alongside broker order IDs"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO active_positions 
            (symbol, entry_order_id, sl_order_id, quantity, entry_price, initial_sl, current_sl, target_price, status, entry_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
        """, (symbol, str(entry_ord_id), str(sl_ord_id), int(qty), float(entry_p), float(sl_p), float(sl_p), float(tp_p), datetime.datetime.now().isoformat()))
        conn.commit()

def update_sl_order(symbol, new_sl_price):
    """Update Stop Loss level when trailing to breakeven/cost"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE active_positions 
            SET current_sl = ?, status = 'TRAILING'
            WHERE symbol = ?
        """, (float(new_sl_price), symbol))
        conn.commit()

def close_position(symbol):
    """Mark position closed and remove from active list"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM active_positions WHERE symbol = ?", (symbol,))
        conn.commit()

def get_active_positions():
    """Retrieve all open trades on startup or loop check"""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM active_positions WHERE status != 'CLOSED'")
        return [dict(row) for row in cursor.fetchall()]