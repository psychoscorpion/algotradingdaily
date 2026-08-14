import os
import time
import datetime
import pyotp
import requests
import io
import pandas as pd
import pandas_ta as ta
from dotenv import load_dotenv
from NorenRestApiPy.NorenApi import NorenApi

import trade_db  # Imports our SQLite database module

load_dotenv()
USER = os.getenv("SHOONYA_USER")
PWD = os.getenv("SHOONYA_PWD")
API_KEY = os.getenv("SHOONYA_API_KEY")
VENDOR_CODE = os.getenv("SHOONYA_VENDOR_CODE")
TOTP_KEY = os.getenv("SHOONYA_TOTP_KEY")
IMEI = os.getenv("SHOONYA_IMEI", "shoonya_algo_desktop")

class ShoonyaLiveBot(NorenApi):
    def __init__(self, max_concurrent=2, per_trade_capital=5000, leverage=5):
        super().__init__(
            host='https://api.shoonya.com/NorenWSTScript/', 
            websocket='wss://api.shoonya.com/NorenWSTScript/'
        )
        self.max_concurrent = max_concurrent
        self.per_trade_capital = per_trade_capital
        self.leverage = leverage
        self.active_positions = {}  # In-memory dictionary for fast checks

    def authenticate(self):
        """Perform TOTP automated login"""
        try:
            totp = pyotp.TOTP(TOTP_KEY).now()
            res = self.login(
                userid=USER, password=PWD, twoFA=totp,
                vendor_code=VENDOR_CODE, api_secret=API_KEY, imei=IMEI
            )
            if res and res.get('stat') == 'Ok':
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ Authenticated to Shoonya API.")
                return True
            print("❌ Authentication Failed:", res)
            return False
        except Exception as e:
            print("❌ Login Exception:", e)
            return False

    def sync_state_from_db(self):
        """Restore active state from SQLite on startup/restart"""
        trade_db.init_db()
        saved = trade_db.get_active_positions()
        for pos in saved:
            self.active_positions[pos['symbol']] = pos
        print(f"🔄 State synchronized: {len(self.active_positions)} active position(s) loaded from DB.")

    def get_nifty50_symbols(self):
        url = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            if res.status_code == 200:
                df = pd.read_csv(io.StringIO(res.text))
                return [f"{s}-EQ" for s in df['Symbol'].tolist()]
        except Exception:
            pass
        return ["RELIANCE-EQ", "TCS-EQ", "INFY-EQ", "HDFCBANK-EQ", "ICICIBANK-EQ"]

    def get_nifty_intraday_pct(self):
        """Fetch current Nifty 50 Index percentage change from day open"""
        try:
            quote = self.get_quotes(exchange='NSE', token='26000') # Nifty 50 Index token
            if quote and quote.get('stat') == 'Ok':
                ltp = float(quote.get('lp', 0))
                day_open = float(quote.get('open', 0))
                if day_open > 0:
                    return (ltp - day_open) / day_open
        except Exception:
            pass
        return None

    def evaluate_15m_signal(self, df, nifty_pct=None):
        """Verify 15-minute breakdown criteria with Relative Weakness"""
        if len(df) < 20:
            return False, 0, 0
        
        stoch = ta.stochrsi(df['Close'], length=14, rsi_length=14, k=3, d=3)
        adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
        vwap = ta.vwap(df['High'], df['Low'], df['Close'], df['Volume'])

        k_prev = stoch['STOCHRSIk_14_14_3_3'].iloc[-2]
        k_curr = stoch['STOCHRSIk_14_14_3_3'].iloc[-1]
        adx_curr = adx['ADX_14'].iloc[-1]
        close_curr = df['Close'].iloc[-1]
        vwap_curr = vwap.iloc[-1]

        # 1. Technical Momentum Breakdown
        signal = (k_prev >= 80) and (k_curr < 80) and (adx_curr > 25) and (close_curr < vwap_curr)
        if not signal:
            return False, 0, 0

        # 2. Relative Weakness Filter: Stock must underperform Nifty 50
        if nifty_pct is not None and 'Open' in df.columns:
            stock_open = df['Open'].iloc[0]
            stock_pct = (close_curr - stock_open) / stock_open
            if stock_pct >= nifty_pct:
                return False, 0, 0  # Skip: Stock is stronger than Nifty
        
        entry_p = close_curr
        swing_high = df.iloc[-4:-1]['High'].max()
        sl_p = max(swing_high * 1.0005, entry_p * 1.002)
        risk = sl_p - entry_p
        tp_p = entry_p - (2 * risk)
        return True, sl_p, tp_p

    def enter_short_position(self, symbol, current_price, sl_price, tp_price):
        """Execute Short MIS + Protection SL-LMT Order"""
        exposure = self.per_trade_capital * self.leverage
        qty = max(int(exposure // current_price), 1)

        print(f"\n🚀 Placing SHORT order for {symbol} | Qty: {qty} | Entry: ~{current_price} | SL: {sl_price:.2f} | TP: {tp_price:.2f}")

        # 1. Main Entry: Short Sell Market Order
        entry_res = self.place_order(
            buy_or_sell='S',
            product_type='I',        # 'I' = MIS Intraday
            exchange='NSE',
            tradingsymbol=symbol,
            quantity=qty,
            discloseqty=0,
            price_type='MKT',
            price=0,
            remarks='STOCH_SHORT_ENTRY'
        )

        if not entry_res or entry_res.get('stat') != 'Ok':
            print(f"❌ Entry order failed for {symbol}:", entry_res)
            return

        entry_order_id = entry_res.get('norenordno')

        # 2. Protection: Stop-Loss Limit Buy Order placed on OMS
        sl_res = self.place_order(
            buy_or_sell='B',
            product_type='I',
            exchange='NSE',
            tradingsymbol=symbol,
            quantity=qty,
            discloseqty=0,
            price_type='SL-LMT',
            price=round(sl_price + 0.50, 2),        # Limit buffer
            trigger_price=round(sl_price, 2),       # Trigger price
            remarks='STOCH_SL_PROTECT'
        )

        sl_order_id = sl_res.get('norenordno') if sl_res else "MANUAL_SL"

        # 3. Save to In-Memory and SQLite Database
        pos_data = {
            'symbol': symbol,
            'entry_order_id': entry_order_id,
            'sl_order_id': sl_order_id,
            'quantity': qty,
            'entry_price': current_price,
            'initial_sl': sl_price,
            'current_sl': sl_price,
            'target_price': tp_price,
            'status': 'ACTIVE'
        }
        self.active_positions[symbol] = pos_data
        trade_db.save_new_position(symbol, entry_order_id, sl_order_id, qty, current_price, sl_price, tp_price)
        print(f"✅ Position established and recorded in DB for {symbol}.")

    def check_and_trail_stoploss(self, symbol, ltp):
        """Move SL to cost/breakeven when trade reaches +1R in profit"""
        pos = self.active_positions.get(symbol)
        if not pos or pos.get('status') == 'TRAILING':
            return

        entry_p = pos['entry_price']
        initial_sl = pos['initial_sl']
        risk = initial_sl - entry_p
        
        # +1R profit threshold reached on Short
        if ltp <= (entry_p - risk):
            print(f"\n🎯 [TRAILING TRIGGER] {symbol} reached +1R gain! Modifying SL to Breakeven (₹{entry_p:.2f})...")
            try:
                # Modify pending Stop-Loss order on Shoonya OMS
                mod_res = self.modify_order(
                    orderno=pos['sl_order_id'],
                    exchange='NSE',
                    tradingsymbol=symbol,
                    newquantity=pos['quantity'],
                    newprice_type='SL-LMT',
                    newprice=round(entry_p + 0.30, 2),
                    newtrigger_price=round(entry_p, 2)
                )
                if mod_res and mod_res.get('stat') == 'Ok':
                    print(f"✅ SL modified to breakeven on exchange for {symbol}.")
                    pos['status'] = 'TRAILING'
                    pos['current_sl'] = entry_p
                    trade_db.update_sl_order(symbol, entry_p)
                else:
                    print("⚠️ SL modification response:", mod_res)
            except Exception as e:
                print(f"❌ Error modifying SL for {symbol}: {e}")

    def square_off_all_positions(self):
        """Hard 3:00 PM Square-Off across all active trades"""
        print("\n⏱️ [3:00 PM REACHED] Closing all open intraday positions...")
        for sym, data in list(self.active_positions.items()):
            try:
                # Cancel pending protection SL order first
                if data.get('sl_order_id'):
                    self.cancel_order(orderno=data['sl_order_id'])
                
                # Place Market Buy to Cover
                self.place_order(
                    buy_or_sell='B',
                    product_type='I',
                    exchange='NSE',
                    tradingsymbol=sym,
                    quantity=data['quantity'],
                    discloseqty=0,
                    price_type='MKT',
                    price=0,
                    remarks='3PM_AUTO_EXIT'
                )
                trade_db.close_position(sym)
                print(f"✅ Squared off and closed {sym}")
            except Exception as e:
                print(f"❌ Error during 3PM square-off for {sym}: {e}")
        self.active_positions.clear()

    def run_live_scanner(self):
        """Main market scanning and position management loop"""
        print("\n📡 Shoonya Algo Engine Online. Listening for market intervals...")
        symbols = self.get_nifty50_symbols()
        self.sync_state_from_db()

        while True:
            now = datetime.datetime.now()

            # 1. Hard 3:00 PM Exit
            if now.hour == 15 and now.minute >= 0:
                self.square_off_all_positions()
                print("🏁 Intraday session ended. Bot shutting down.")
                break

            # 2. Check Trailing SL for open positions
            # (In production, substitute with real-time WebSocket tick feeds)
            for sym in list(self.active_positions.keys()):
                # Placeholder: check latest LTP against trailing rules
                pass

            # 3. New Entry Scan Window: 10:00 AM - 1:30 PM
            is_entry_time = (now.hour >= 10) and ((now.hour < 13) or (now.hour == 13 and now.minute <= 30))
            
            # Run at the close of every 15-minute candle (:00, :15, :30, :45)
            if now.minute in [0, 15, 30, 45] and now.second < 5:
                if is_entry_time and len(self.active_positions) < self.max_concurrent:
                    print(f"\n[{now.strftime('%H:%M:%S')}] 🔍 Scanning Nifty 50 for 15m Signals (Slots: {len(self.active_positions)}/{self.max_concurrent})...")
                    for sym in symbols:
                        if len(self.active_positions) >= self.max_concurrent:
                            break
                        if sym in self.active_positions:
                            continue

                        # When live, pull completed 15m historical series from get_time_price_series
                        # sig, sl_p, tp_p = self.evaluate_15m_signal(candle_df)
                        # if sig:
                        #     self.enter_short_position(sym, current_price, sl_p, tp_p)

                time.sleep(10)  # Avoid duplicate executions within the same 5-second interval
            
            time.sleep(1)

if __name__ == "__main__":
    bot = ShoonyaLiveBot(max_concurrent=2, per_trade_capital=5000, leverage=5)
    # bot.authenticate()
    # bot.run_live_scanner()
    print("Files ready. Activate when credentials are set.")