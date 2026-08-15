# Shoonya Algorithmic Trading Bot & Simulation Engine

An automated intraday trading execution engine and portfolio simulator built in Python for Shoonya (Finvasia).

---

## 📈 Strategy Overview

* **Universe:** NIFTY 50 Constituents (NSE)
* **Timeframe:** 15-Minute Candles
* **Entry Window:** 10:00 AM – 1:30 PM IST
* **Direction:** Short Breakdown
* **Core Technical Indicators:**
  * **Stochastic RSI (14, 14, 3, 3):** Identifies breakdown momentum (crossing below 80 from overbought).
  * **ADX (14):** Trend strength filter (`ADX > 25`).
  * **VWAP:** Intraday bias confirmation (`Close < VWAP`).
  * **NIFTY 50 Relative Weakness:** Stock intraday % return must underperform NIFTY 50 intraday % return (`Stock % < Nifty %`).

---

## 🛡️ Risk Management & Execution Rules

* **Capital Allocation:** ₹10,000 baseline (Max 2 concurrent positions, ₹5,000 margin / 5x MIS leverage).
* **Dynamic Stop Loss:** 3-bar swing high (min 0.2% buffer).
* **Profit Target:** Dynamic 1:2 Risk-to-Reward (2R).
* **Trailing SL:** Once trade reaches **+1R profit**, Stop-Loss automatically trails to **Breakeven (₹0 risk)**.
* **Auto-Squareoff:** Mandatory hard exit at **15:00 IST (3:00 PM)**.
* **Fee Modeling:** Full Shoonya regulatory friction modeled (STT, GST, Exchange Txn, Stamp Duty, SEBI turnover fees).

---

## 📊 Backtest Performance (60-Day Simulation)

| Metric | Simulated Result |
| :--- | :--- |
| **Initial Capital** | ₹10,000.00 |
| **Per-Trade Exposure** | ₹25,000.00 (₹5,000 margin x 5 MIS) |
| **Total Trades Taken** | 131 (59 Wins / 72 Losses) |
| **Win Rate** | **45.04%** |
| **Gross Profit (Pre-Tax)** | **₹5,736.69 (+57.37%)** |
| **Total Statutory Taxes & Brokerage** | **₹2,699.70** |
| **Total Net Profit** | **+₹3,036.99 (Post-All Charges)** |
| **60-Day Net Return** | **+30.37%** |
| **Ending Capital Balance** | **₹13,036.99** |

---

## 📁 Repository Structure

* `shoonya_engine.py`: Live execution daemon connecting to Shoonya API with order placement & trailing SL.
* `portfolio_sim.py`: Chronological 60-day portfolio simulator factoring in broker friction & STT.
* `backtest.py`: Standalone single-stock technical indicator scan.
* `trade_db.py`: SQLite state tracking database for position persistence and recovery across restarts.

---

## 🚀 Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/vaibhavreddys/algotradingdaily.git
cd algotradingdaily
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate # Linux/macOS
```

### 3. Install dependencies
```bash
pip install yfinance pandas pandas-ta requests python-dotenv pyotp NorenRestApiPy
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory:
```env
SHOONYA_USER=your_user_id
SHOONYA_PWD=your_password
SHOONYA_API_KEY=your_api_key
SHOONYA_VENDOR_CODE=your_vendor_code
SHOONYA_TOTP_KEY=your_totp_secret_key
SHOONYA_IMEI=shoonya_algo_desktop
```

---

## 💻 Usage

### Run 60-Day Portfolio Simulation:
```bash
python portfolio_sim.py
```

### Run Live Execution Engine:
```bash
python shoonya_engine.py
```
