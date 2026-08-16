# Shoonya Algorithmic Trading Bot & Simulation Engine

An automated intraday trading execution engine and portfolio simulator built in Python for Shoonya (Finvasia).

---

## 📈 Strategy Overview: VWAP-Stoch Breakdown

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

## 📊 Backtest Performance (Simulation)

| Metric | Simulated Result |
| :--- | :--- |
| **Simulation Period** | **2026-05-25 to 2026-08-14 (56 Trading Days)** |
| **Initial Capital** | ₹10,000.00 |
| **Per-Trade Exposure** | ₹25,000.00 (₹5,000 margin x 5 MIS) |
| **Total Trades Taken** | 131 (59 Wins / 72 Losses) |
| **Win Rate** | **45.04%** |
| **Gross Profit (Pre-Tax)** | **₹5,736.69 (+57.37%)** |
| **Total Statutory Taxes & Brokerage** | **₹2,699.70** |
| **Total Net Profit** | **+₹3,036.99 (Post-All Charges)** |
| **Net Return** | **+30.37%** |
| **Ending Capital Balance** | **₹13,036.99** |

---

## 📁 Repository Structure

```text
shoonya_algo/
├── core/                  # Pure math, indicators, config & regulatory fee calculators
│   ├── config.py          # Centralized TradingConfig dataclass & .env overrides
│   ├── trade_db.py        # Isolated SQLite trade journals & crash recovery state
│   ├── indicators.py      # Stoch RSI, ADX, VWAP, Relative Weakness formulas
│   └── charges.py         # Shoonya STT, GST, brokerage & friction math
│
├── strategies/            # Trading strategies layer (one module per strategy)
│   └── vwap_stoch_breakdown.py # Rules, entry/exit criteria & single-trade lifecycle
│
├── data_pipeline/         # Market data gateway & historical caching
│   ├── data_feed.py       # Smart local caching & fallback data loader
│   └── shoonya_loader.py  # Shoonya 1-year historical downloader
│
├── backtesting/           # Historical simulation & scanning engines
│   ├── portfolio_sim.py   # Chronological multi-stock portfolio simulator
│   └── scanner.py         # Unconstrained single-stock indicator scanner
│
├── live_trading/          # Execution engines
│   ├── base_engine.py     # Common scheduler, candle aggregator & trailing SL
│   ├── paper_trader.py    # Risk-free virtual paper trading
│   └── live_trader.py     # Real-money Shoonya OMS order placement
│
├── market_data/           # Local candle cache CSVs (git-ignored)
├── database/              # SQLite trade journals (git-ignored)
├── .env                   # Broker credentials
└── README.md
```

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

### 4. Configure System & Broker Settings
System defaults are centrally defined in [`core/config.py`](core/config.py). You only need to provide your broker credentials in `.env`. Any strategy or portfolio setting can optionally be overridden in `.env` without editing Python code:

Create a `.env` file in the root directory:
```env
# -------------------------------------------------------------
# 1. Mandatory Broker Credentials (Finvasia Shoonya)
# -------------------------------------------------------------
SHOONYA_USER=your_user_id
SHOONYA_PWD=your_password
SHOONYA_API_KEY=your_api_key
SHOONYA_VENDOR_CODE=your_vendor_code
SHOONYA_TOTP_KEY=your_totp_secret_key
SHOONYA_IMEI=shoonya_algo_desktop

# -------------------------------------------------------------
# 2. Optional Overrides (Defaults are active in core/config.py)
# -------------------------------------------------------------
# TRADING_MODE=paper              # Default: paper (paper_trades.db) | live (live_trades.db)
# ORDER_TYPE=BO                   # Default: BO (Bracket Order) | MIS (Standard Margin)
# INITIAL_CAPITAL=10000.0         # Default: ₹10,000.00
# MAX_CONCURRENT_POSITIONS=2      # Default: 2 open trade slots
# LEVERAGE_MIS=5                  # Default: 5x intraday MIS leverage
```

---

## 💻 Usage

### Run Portfolio Simulation (₹10,000 Capital, 2 Slots):
```bash
python -m backtesting.portfolio_sim
```

### Run Unconstrained Strategy Scanner:
```bash
python -m backtesting.scanner
```

### Run Live Market Paper Trading Engine (Safe Simulation):
```bash
python -m live_trading.paper_trader
```
* **Real-time 15m candle loop**: Evaluates breakdown signals on every bar close (:00, :15, :30, :45) during the active window (10:00 AM – 1:30 PM).
* **+1R Trailing SL**: Automatically moves stop loss to Breakeven in real-time.
* **3:00 PM Auto-Squareoff**: Automatically exits open positions at 15:00 IST and saves all records to `database/paper_trades.db`.
* **Daily EOD Performance Report**: Prints an itemized performance summary table on market close or daemon exit.

### Run Live Real-Money Execution Engine:
```bash
python -m live_trading.live_trader
```
